export function CodeBlock({ children, label }: { children: string; label?: string }) {
  return (
    <figure className="overflow-hidden rounded-lg border border-border bg-surface">
      {label && (
        <figcaption className="border-b border-border px-4 py-2 font-mono text-xs text-subtle">
          {label}
        </figcaption>
      )}
      <pre
        tabIndex={0}
        className="overflow-x-auto px-4 py-3.5 font-mono text-[13px] leading-6 text-foreground"
      >
        <code>{children}</code>
      </pre>
    </figure>
  );
}
