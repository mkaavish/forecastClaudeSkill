export function Callout({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <aside className="border-l-2 border-warn bg-surface py-3 pl-4 pr-4 text-sm">
      <p className="eyebrow !text-warn">{title}</p>
      <div className="doc mt-1.5">{children}</div>
    </aside>
  );
}
