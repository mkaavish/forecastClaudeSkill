import json
from pathlib import Path

from forecast.schema import CONTRACTS, export_schemas

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"


def test_exported_schemas_match_committed_files(tmp_path):
    export_schemas(tmp_path)
    for name in CONTRACTS:
        fresh = (tmp_path / f"{name}.schema.json").read_text()
        committed = (SCHEMA_DIR / f"{name}.schema.json").read_text()
        assert json.loads(fresh) == json.loads(committed), (
            f"{name} schema changed; run `python -m forecast.schema schemas`"
        )


def test_every_contract_is_strict():
    for model in CONTRACTS.values():
        assert model.model_json_schema().get("additionalProperties") is False
