export function Callout({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <aside className="rounded-md border border-warn/30 bg-warn/5 px-4 py-3 text-sm">
      <p className="font-medium text-warn">{title}</p>
      <div className="doc mt-1 text-[#cfcfd4]">{children}</div>
    </aside>
  );
}
