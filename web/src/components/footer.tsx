import Link from "next/link";
import { REPO_URL } from "@/lib/site";

export function Footer() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-10 text-sm text-muted sm:flex-row sm:items-start sm:justify-between sm:px-6">
        <div>
          <p className="font-mono font-semibold text-foreground">
            <span className="text-accent">/</span>forecast
          </p>
          <p className="mt-2">Claude understands the problem. Python does the math.</p>
        </div>
        <ul className="flex gap-6">
          <li>
            <a href={REPO_URL} className="hover:text-foreground">
              GitHub
            </a>
          </li>
          <li>
            <Link href="/docs" className="hover:text-foreground">
              Documentation
            </Link>
          </li>
        </ul>
      </div>
    </footer>
  );
}
