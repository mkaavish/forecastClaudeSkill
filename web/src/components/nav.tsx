import Link from "next/link";
import { GithubIcon } from "./github-icon";
import { REPO_URL } from "@/lib/site";

export function Nav() {
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/85 backdrop-blur-md">
      <nav
        aria-label="Primary"
        className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:px-6"
      >
        <Link href="/" className="font-mono text-[15px] font-semibold tracking-tight">
          <span className="text-accent">/</span>forecast
        </Link>
        <ul className="flex items-center gap-1 text-sm text-muted">
          <li>
            <Link href="/docs" className="rounded px-3 py-1.5 hover:text-foreground">
              Docs
            </Link>
          </li>
          <li>
            <a
              href={REPO_URL}
              className="inline-flex items-center gap-2 rounded px-3 py-1.5 hover:text-foreground"
            >
              <GithubIcon className="size-4" />
              GitHub
            </a>
          </li>
        </ul>
      </nav>
    </header>
  );
}
