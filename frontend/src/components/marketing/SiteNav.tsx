"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Wordmark } from "@/components/ui/Wordmark";
import { useSession } from "@/lib/session";

const LINKS = [
  { href: "/#how",      label: "How it works" },
  { href: "/business",  label: "For stores" },
  { href: "/shop",      label: "Demo store" },
];

export function SiteNav() {
  const { user } = useSession();
  const path = usePathname();
  return (
    <header className="fixed inset-x-0 top-0 z-50 border-b border-border bg-canvas">
      <div className="mx-auto flex h-14 max-w-[1440px] items-center justify-between gap-3 px-4 md:gap-6 md:px-12">
        <Wordmark />

        <nav aria-label="Main" className="hidden items-center gap-8 md:flex">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`label transition-colors duration-150 ${
                path === l.href ? "text-ink" : "text-ink-muted hover:text-ink"
              }`}
            >
              {l.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          {user ? (
            <Link href="/studio" className="btn-signal min-h-9 px-3 md:px-5">
              Open studio
            </Link>
          ) : (
            <>
              <Link href="/login" className="btn-quiet min-h-9 px-2 md:px-3">
                Sign in
              </Link>
              <Link href="/signup" className="btn-signal min-h-9 px-3 md:px-5">
                Start free
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
