type Status = "early" | "planned" | "soon";

const LABELS: Record<Status, string> = {
  early: "Early development",
  planned: "Planned for V1",
  soon: "Coming soon",
};

export function StatusBadge({ status, label }: { status: Status; label?: string }) {
  const tone =
    status === "early"
      ? "border-warn/40 text-warn"
      : "border-border text-muted";
  return (
    <span
      className={`inline-block whitespace-nowrap rounded-full border px-2 py-0.5 align-middle font-mono text-[11px] font-normal leading-4 ${tone}`}
    >
      {label ?? LABELS[status]}
    </span>
  );
}
