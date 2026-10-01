"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { DOCS_NAV } from "@/lib/site";

export function Pager() {
  const pathname = usePathname();
  const i = DOCS_NAV.findIndex((d) => d.href === pathname);
  const prev = DOCS_NAV[i - 1];
  const next = DOCS_NAV[i + 1];
  return (
    <nav aria-label="Pagination" className="mt-16 grid grid-cols-2 gap-4 border-t border-border pt-6 text-sm">
      <div>
        {prev && (
          <Link href={prev.href} className="!no-underline">
            <span className="eyebrow block">Previous</span>
            <span className="text-foreground">{prev.label}</span>
          </Link>
        )}
      </div>
      <div className="text-right">
        {next && (
          <Link href={next.href} className="!no-underline">
            <span className="eyebrow block">Next</span>
            <span className="text-foreground">{next.label}</span>
          </Link>
        )}
      </div>
    </nav>
  );
}
