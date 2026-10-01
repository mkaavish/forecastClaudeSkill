"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { DOCS_NAV } from "@/lib/site";

export function DocsNav() {
  const pathname = usePathname();
  return (
    <ul className="space-y-0.5 text-sm">
      {DOCS_NAV.map(({ href, label }) => {
        const active = pathname === href;
        return (
          <li key={href}>
            <Link
              href={href}
              aria-current={active ? "page" : undefined}
              className={`block rounded px-2.5 py-1.5 ${
                active
                  ? "bg-surface text-foreground"
                  : "text-muted hover:text-foreground"
              }`}
            >
              {label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
