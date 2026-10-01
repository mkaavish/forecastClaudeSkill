type Status = "early" | "planned" | "soon";

const LABELS: Record<Status, string> = {
  early: "Early development",
  planned: "Planned for V1",
  soon: "Coming soon",
};

export function StatusBadge({ status, label }: { status: Status; label?: string }) {
  const dot = status === "early" ? "bg-warn" : "bg-subtle";
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap align-middle font-mono text-[11px] font-normal uppercase leading-4 tracking-wide text-muted">
      <span aria-hidden className={`size-1.5 rounded-full ${dot}`} />
      {label ?? LABELS[status]}
    </span>
  );
}
