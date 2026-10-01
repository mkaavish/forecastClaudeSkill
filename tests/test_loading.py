import numpy as np
import pandas as pd
import pytest

from forecast.loading import (
    clean_numeric,
    detect_date_candidates,
    detect_target_candidates,
    infer_frequency,
    load_series,
    parse_dates,
    read_table,
)
from forecast.schema import NeedsInputError, RefusedError
from tests import synthetic


def write(tmp_path, text, name="data.csv"):
    p = tmp_path / name
    p.write_text(text)
    return p


def write_df(tmp_path, df, name="data.csv", **kw):
    p = tmp_path / name
    df.to_csv(p, index=False, **kw)
    return p


def kinds(exc_info):
    return {a.kind for a in exc_info.value.ambiguities}


# ------------------------------------------------------------ date + target detection (CSV shapes)


def test_shape_simple_iso_daily(tmp_path):
    p = write(
        tmp_path, "date,sales\n" + "\n".join(f"2026-01-{d:02d},{18000 + d}" for d in range(1, 29))
    )
    s = load_series(p)
    assert (s.report.date_column, s.report.target_column) == ("date", "sales")
    assert s.freq == "D" and s.report.frequency_name == "daily" and s.report.n_obs == 28


def test_shape_us_dates_resolved_by_day_over_12(tmp_path):
    dates = pd.date_range("2024-01-01", periods=30)
    s = load_series(
        write(
            tmp_path, "Date,Revenue\n" + "\n".join(f"{d:%m/%d/%Y},{i}" for i, d in enumerate(dates))
        )
    )
    assert s.report.target_column == "Revenue" and s.freq == "D"
    assert s.data["ds"].iloc[-1] == pd.Timestamp("2024-01-30")


def test_shape_dmy_resolved_by_day_over_12(tmp_path):
    dates = pd.date_range("2024-01-01", periods=30)
    p = write(
        tmp_path, "date,units\n" + "\n".join(f"{d:%d/%m/%Y},{i}" for i, d in enumerate(dates))
    )
    s = load_series(p)
    assert s.freq == "D" and s.data["ds"].iloc[0] == pd.Timestamp("2024-01-01")
    assert s.data["ds"].iloc[-1] == pd.Timestamp("2024-01-30")


def test_shape_ambiguous_numeric_dates_ask(tmp_path):
    dates = pd.date_range("2024-01-02", periods=10)  # 02/01 .. 11/01: day and month both <= 12
    p = write(
        tmp_path, "date,sales\n" + "\n".join(f"{d:%d/%m/%Y},{i}" for i, d in enumerate(dates))
    )
    with pytest.raises(NeedsInputError) as e:
        load_series(p)
    assert "date_format" in kinds(e)
    s = load_series(p, date_order="dmy")
    assert s.freq == "D" and s.data["ds"].iloc[1] == pd.Timestamp("2024-01-03")


def test_shape_timestamp_with_times_and_other_name(tmp_path):
    ts = pd.date_range("2024-03-01 09:00", periods=48, freq="h")
    p = write_df(tmp_path, pd.DataFrame({"timestamp": ts, "visits": np.arange(48) + 100}))
    s = load_series(p)
    assert s.report.date_column == "timestamp" and s.freq == "h"


def test_shape_year_month_strings_monthly(tmp_path):
    p = write(
        tmp_path,
        "month,mrr\n"
        + "\n".join(
            f"{d:%Y-%m},{1000 + i * 10}"
            for i, d in enumerate(pd.date_range("2022-01-01", periods=30, freq="MS"))
        ),
    )
    s = load_series(p)
    assert s.freq == "MS" and s.report.frequency_name == "monthly"


def test_shape_integer_years(tmp_path):
    p = write(tmp_path, "year,revenue\n" + "\n".join(f"{2000 + i},{50 + i * 2}" for i in range(15)))
    s = load_series(p)
    assert s.freq == "YS-JAN" and s.report.date_column == "year" and s.report.n_obs == 15


def test_shape_semicolon_delimiter_and_bom(tmp_path):
    p = tmp_path / "x.csv"
    p.write_bytes(
        ("﻿date;sales\n" + "\n".join(f"2024-02-{d:02d};{d}" for d in range(1, 21))).encode("utf-8")
    )
    assert load_series(p).report.n_obs == 20


def test_shape_pandas_index_column_is_ignored(tmp_path):
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=30), "sales": range(30)})
    p = write_df(tmp_path, df)
    p.write_text(
        "".join(f"{i},{l}" if i else f",{l}" for i, l in enumerate(p.read_text().splitlines(True)))
    )
    assert load_series(p).report.target_column == "sales"


def test_shape_multicolumn_store_product_needs_series_choice(tmp_path):
    rows = ["date,store,product,units_sold,inventory,price"]
    for d in pd.date_range("2024-01-01", periods=20):
        for store in ("A", "B"):
            for product in ("x", "y"):
                rows.append(f"{d:%Y-%m-%d},{store},{product},{10},{500},{9.99}")
    p = write(tmp_path, "\n".join(rows))
    with pytest.raises(NeedsInputError) as e:
        load_series(p)
    (amb,) = e.value.ambiguities
    assert amb.kind == "series"
    flags = [o.cli_args[0] for o in amb.options]
    assert flags.count("--agg") == 2 and flags.count("--where") == 2  # store, product
    assert {"store", "product"} == {
        o.label.split()[1] for o in amb.options if o.cli_args[0] == "--where"
    }


def test_target_autoselected_with_alternatives_noted(tmp_path):
    df = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=30),
            "units_sold": range(30),
            "inventory": range(30, 60),
            "price": [9.99] * 30,
        }
    )
    s = load_series(write_df(tmp_path, df))
    assert s.report.target_column == "units_sold"
    assert any(n.code == "TARGET_AUTO_SELECTED" for n in s.report.notices)


def test_target_ambiguous_when_names_equally_plausible(tmp_path):
    df = pd.DataFrame(
        {"date": pd.date_range("2024-01-01", periods=30), "sales": range(30), "visits": range(30)}
    )
    with pytest.raises(NeedsInputError) as e:
        load_series(write_df(tmp_path, df))
    assert kinds(e) == {"target"}
    assert load_series(write_df(tmp_path, df), target="visits").report.target_column == "visits"


def test_id_column_is_not_a_target(tmp_path):
    df = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=30),
            "order_id": range(1000, 1030),
            "sales": np.arange(30) * 3 % 7,
        }
    )
    cands = detect_target_candidates(read_table(write_df(tmp_path, df)), exclude={"date"})
    assert [c.name for c in cands] == ["sales"]


def test_price_numbers_are_not_dates(tmp_path):
    df = pd.DataFrame(
        {
            "price": [1999, 2005, 2010, 2020] * 5,
            "date": pd.date_range("2024-01-01", periods=20),
            "sales": range(20),
        }
    )
    assert [c.name for c in detect_date_candidates(read_table(write_df(tmp_path, df)))] == ["date"]


def test_two_date_columns_ask(tmp_path):
    d = pd.date_range("2024-01-01", periods=30)
    df = pd.DataFrame(
        {"order_date": d, "ship_date": d + pd.to_timedelta(2, unit="D"), "sales": range(30)}
    )
    with pytest.raises(NeedsInputError) as e:
        load_series(write_df(tmp_path, df))
    assert "date" in kinds(e)


def test_no_date_column_refused(tmp_path):
    with pytest.raises(RefusedError) as e:
        load_series(write(tmp_path, "a,b\n1,2\n3,4\n5,6\n"))
    assert e.value.code == "NO_DATE_COLUMN"


def test_unsorted_input_is_sorted(tmp_path):
    df = synthetic.linear_trend(40).sample(frac=1, random_state=1)
    s = load_series(write_df(tmp_path, df))
    assert s.data["ds"].is_monotonic_increasing and s.freq == "D"


# ------------------------------------------------------------ numeric cleaning / invalid values


def test_clean_numeric_formats():
    v, bad = clean_numeric(pd.Series(["$1,234", "(5)", "7.5", "abc", None, "1e3"]))
    assert (
        v.iloc[:3].tolist() == [1234.0, -5.0, 7.5] and np.isnan(v.iloc[3]) and np.isnan(v.iloc[4])
    )
    assert v.iloc[5] == 1000.0 and bad == 1


def test_clean_numeric_decimal_comma():
    v, bad = clean_numeric(pd.Series(["1.234,5", "7,25", "0,5"]))
    assert v.tolist() == [1234.5, 7.25, 0.5] and bad == 0


def test_invalid_target_values_become_missing_with_notice(tmp_path):
    p = write(
        tmp_path,
        "date,sales\n"
        + "\n".join(f"2024-01-{d:02d},{'oops' if d == 10 else d}" for d in range(1, 31)),
    )
    s = load_series(p)
    assert s.report.n_missing_values == 1 and s.report.n_imputed == 1
    assert any(n.code == "INVALID_VALUES" for n in s.report.notices)
    assert s.data.loc[s.data["imputed"], "y"].iloc[0] == pytest.approx(
        10.0 - 1 + 1
    )  # linear between 9 and 11


# ------------------------------------------------------------ frequency inference


@pytest.mark.parametrize(
    "freq,expected",
    [
        ("h", "h"),
        ("D", "D"),
        ("B", "B"),
        ("W-SUN", "W-SUN"),
        ("W-WED", "W-WED"),
        ("MS", "MS"),
        ("ME", "ME"),
        ("QS-JAN", "QS-JAN"),
        ("QE-DEC", "QE-DEC"),
        ("YS-JAN", "YS-JAN"),
    ],
)
def test_infer_frequency_regular(freq, expected):
    ts = pd.date_range("2020-01-01", periods=40, freq=freq)
    alias, missing = infer_frequency(ts)
    assert missing == 0 and ts.equals(pd.date_range(ts[0], periods=40, freq=alias))  # same calendar
    assert alias.split("-")[0] == expected.split("-")[0]


def test_infer_frequency_counts_missing_timestamps():
    ts = pd.date_range("2024-01-01", periods=60, freq="D").delete([10, 11, 30])
    alias, missing = infer_frequency(ts)
    assert (alias, missing) == ("D", 3)


def test_infer_frequency_monthly_with_gap():
    ts = pd.date_range("2020-01-01", periods=36, freq="MS").delete([7])
    assert infer_frequency(ts) == ("MS", 1)


def test_irregular_sampling_refused(tmp_path):
    rng = np.random.default_rng(3)
    days = np.sort(rng.choice(np.arange(400), size=60, replace=False))
    df = pd.DataFrame(
        {
            "date": pd.Timestamp("2024-01-01") + pd.to_timedelta(days, "D"),
            "value": rng.normal(size=60),
        }
    )
    with pytest.raises(RefusedError) as e:
        load_series(write_df(tmp_path, df))
    assert e.value.code == "IRREGULAR_SAMPLING"


def test_too_few_timestamps_refused(tmp_path):
    with pytest.raises(RefusedError) as e:
        load_series(write(tmp_path, "date,sales\n2024-01-01,1\n2024-01-02,2\n"))
    assert e.value.code == "INSUFFICIENT_DATA"


# ------------------------------------------------------------ regularization / fill policy


def test_missing_timestamps_are_inserted_and_keep_seasonal_phase(tmp_path):
    full = synthetic.weekly_seasonality(125, noise=0.0)
    gappy = synthetic.with_missing_timestamps(full, drop_every=20)
    s = load_series(write_df(tmp_path, gappy))
    assert len(s.data) == 125  # calendar restored; without this the weekly phase would shift
    assert s.report.n_missing_timestamps == 6 and s.report.n_imputed == 6
    observed = s.data.loc[~s.data["imputed"]].set_index("ds")["y"]
    truth = full.set_index("date")["value"]
    np.testing.assert_allclose(observed.to_numpy(), truth.loc[observed.index].to_numpy())


def test_interpolate_fills_linearly(tmp_path):
    df = synthetic.linear_trend(60, slope=2.0, noise=0.0)
    gappy = synthetic.with_missing_values(df, [10, 11, 12])
    s = load_series(write_df(tmp_path, gappy))
    np.testing.assert_allclose(s.data["y"].to_numpy(), df["value"].to_numpy())
    assert s.report.longest_gap == 3


def test_zero_fill_policy(tmp_path):
    df = synthetic.linear_trend(60, noise=0.0)
    gappy = synthetic.with_missing_timestamps(df, drop_every=30)
    s = load_series(write_df(tmp_path, gappy), fill="zero")
    assert s.data.loc[s.data["imputed"], "y"].eq(0.0).all() and s.report.fill_policy == "zero"


def test_too_much_missing_is_refused(tmp_path):
    df = synthetic.with_missing_values(synthetic.linear_trend(100), list(range(10, 40)))
    with pytest.raises(RefusedError) as e:
        load_series(write_df(tmp_path, df))
    assert e.value.code == "MISSING_DATA_HIGH"


def test_leading_and_trailing_missing_values_are_trimmed_not_extrapolated(tmp_path):
    df = synthetic.with_missing_values(synthetic.linear_trend(60), [0, 1, 58, 59])
    s = load_series(write_df(tmp_path, df))
    assert len(s.data) == 56 and not s.data["imputed"].any()
    assert any(n.code == "EDGES_TRIMMED" for n in s.report.notices)


# ------------------------------------------------------------ duplicates / series selection


def test_exact_duplicate_rows_dropped(tmp_path):
    df = synthetic.linear_trend(30)
    dup = pd.concat([df, df.iloc[[5, 6]]])
    s = load_series(write_df(tmp_path, dup))
    assert s.report.n_obs == 30 and any(
        n.code == "DUPLICATE_ROWS_DROPPED" for n in s.report.notices
    )


def test_conflicting_duplicate_timestamps_need_a_decision(tmp_path):
    df = synthetic.linear_trend(30)
    conflicting = pd.concat([df, df.iloc[[5]].assign(value=999.0)])
    p = write_df(tmp_path, conflicting)
    with pytest.raises(NeedsInputError) as e:
        load_series(p)
    assert kinds(e) == {"duplicates"}
    s = load_series(p, agg="sum")
    assert s.data["y"].iloc[5] == pytest.approx(df["value"].iloc[5] + 999.0)


def _panel(tmp_path, drop_one=False):
    rows = []
    for d in pd.date_range("2024-01-01", periods=30):
        for store, base in (("A", 10), ("B", 100)):
            if drop_one and store == "B" and d.day == 15:
                continue
            rows.append({"date": d, "store": store, "sales": base})
    return write_df(tmp_path, pd.DataFrame(rows))


def test_where_selects_one_slice(tmp_path):
    s = load_series(_panel(tmp_path), where={"store": "B"})
    assert s.data["y"].eq(100).all() and s.report.where == {"store": "B"}


def test_agg_sum_totals_all_slices(tmp_path):
    s = load_series(_panel(tmp_path), agg="sum")
    assert s.data["y"].eq(110).all() and s.report.agg == "sum"


def test_agg_mean(tmp_path):
    assert load_series(_panel(tmp_path), agg="mean").data["y"].eq(55).all()


def test_unbalanced_panel_warns_when_aggregating(tmp_path):
    s = load_series(_panel(tmp_path, drop_one=True), agg="sum")
    assert any(n.code == "UNBALANCED_PANEL" and n.severity == "warn" for n in s.report.notices)


def test_where_with_no_match_refused(tmp_path):
    with pytest.raises(RefusedError) as e:
        load_series(_panel(tmp_path), where={"store": "Z"})
    assert e.value.code == "WHERE_NO_MATCH"


def test_where_on_non_dimension_refused(tmp_path):
    with pytest.raises(RefusedError) as e:
        load_series(_panel(tmp_path), where={"sales": "10"})
    assert e.value.code == "BAD_ARGUMENT"


def test_explicit_bad_target_refused(tmp_path):
    with pytest.raises(RefusedError) as e:
        load_series(write_df(tmp_path, synthetic.linear_trend(30)), target="nope")
    assert e.value.code == "BAD_ARGUMENT"


def test_synthetic_generators_load_with_expected_frequency(tmp_path):
    for name in (
        "linear_trend",
        "weekly_seasonality",
        "trend_seasonality",
        "white_noise",
        "random_walk",
        "zero_heavy",
        "level_shift",
    ):
        s = load_series(write_df(tmp_path, getattr(synthetic, name)(), name=f"{name}.csv"))
        assert s.freq == "D" and s.report.n_imputed == 0, name


def test_report_validates_and_round_trips(tmp_path):
    s = load_series(write_df(tmp_path, synthetic.trend_seasonality(80)))
    from forecast.schema import LoadReport

    assert LoadReport.model_validate_json(s.report.model_dump_json()) == s.report


def test_parse_dates_reports_rate():
    p = parse_dates(pd.Series(["2024-01-01", "nope", "2024-01-03", None]))
    assert p.rate == pytest.approx(2 / 3)
