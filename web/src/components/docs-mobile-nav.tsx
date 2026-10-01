"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { DocsNav } from "./docs-nav";

// Native <details> keeps this tiny; the effect just closes it after navigating.
export function DocsMobileNav() {
  const ref = useRef<HTMLDetailsElement>(null);
  const pathname = usePathname();
  useEffect(() => {
    ref.current?.removeAttribute("open");
  }, [pathname]);
  return (
    <details ref={ref} className="group border-b border-border lg:hidden">
      <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3 text-sm text-muted sm:px-6 [&::-webkit-details-marker]:hidden">
        Documentation menu
        <span aria-hidden className="font-mono text-subtle group-open:rotate-90">
          ›
        </span>
      </summary>
      <nav aria-label="Documentation" className="px-2 pb-3 sm:px-4">
        <DocsNav />
      </nav>
    </details>
  );
}
