import { DocsNav } from "@/components/docs-nav";
import { Pager } from "@/components/pager";
import { DocsMobileNav } from "@/components/docs-mobile-nav";

export default function DocsLayout({ children }: LayoutProps<"/docs">) {
  return (
    <>
      <DocsMobileNav />
      <div className="mx-auto flex max-w-6xl gap-12 px-4 sm:px-6">
        <aside className="hidden w-52 shrink-0 lg:block">
          <nav aria-label="Documentation" className="sticky top-20 py-10">
            <DocsNav />
          </nav>
        </aside>
        <article className="doc min-w-0 max-w-2xl flex-1 py-10 pb-20">{children}
          <Pager />
        </article>
      </div>
    </>
  );
}
