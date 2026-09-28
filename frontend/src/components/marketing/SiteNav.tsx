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
    <header className="fixed inset-x-0 top-0 z-50 border-b border-border/70 bg-canvas/90 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-[1440px] items-center justify-between gap-6 px-6 md:px-12">
        <Wordmark />

        <nav aria-label="Main" className="hidden items-center gap-8 md:flex">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`label text-[10px] tracking-widest transition-colors duration-150 ${
                path === l.href ? "text-ink" : "text-ink-muted hover:text-ink"
              }`}
            >
              {l.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          {user ? (
            <Link href="/studio" className="btn-signal min-h-9 px-5 text-[10px]">
              Open studio
            </Link>
          ) : (
            <>
              <Link href="/login" className="btn-quiet min-h-9 text-[10px]">
                Sign in
              </Link>
              <Link href="/signup" className="btn-signal min-h-9 px-5 text-[10px]">
                Start free
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
