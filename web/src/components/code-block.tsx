export function CodeBlock({ children, label }: { children: string; label?: string }) {
  return (
    <figure className="overflow-hidden rounded-md border border-border bg-surface">
      {label && (
        <figcaption className="border-b border-border px-4 py-1.5 font-mono text-xs text-subtle">
          {label}
        </figcaption>
      )}
      {/* tabIndex lets keyboard users scroll long lines */}
      <pre
        tabIndex={0}
        className="overflow-x-auto px-4 py-3 font-mono text-[13px] leading-6 text-foreground"
      >
        <code>{children}</code>
      </pre>
    </figure>
  );
}
