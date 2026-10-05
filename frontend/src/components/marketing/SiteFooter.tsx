import Link from "next/link";
import { Wordmark } from "@/components/ui/Wordmark";

const LINKS = [
  ["For stores", "/business"],
  ["Demo store", "/shop"],
  ["Privacy", "/privacy"],
  ["Sign in", "/login"],
] as const;

export function SiteFooter() {
  return (
    <footer className="border-t border-border px-6 md:px-12">
      <div className="mx-auto flex max-w-[1200px] flex-col gap-8 py-12 md:flex-row md:items-center md:justify-between">
        <Wordmark />
        <nav aria-label="Footer" className="flex flex-wrap gap-x-8 gap-y-3">
          {LINKS.map(([label, href]) => (
            <Link
              key={href}
              href={href}
              className="text-sm text-ink-soft transition-colors hover:text-ink"
            >
              {label}
            </Link>
          ))}
        </nav>
        <p className="text-sm text-ink-muted">
          Photos are encrypted and deleted after 14 days.
        </p>
      </div>
    </footer>
  );
}
