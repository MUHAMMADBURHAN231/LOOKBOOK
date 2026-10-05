"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Wordmark } from "@/components/ui/Wordmark";
import { useSession } from "@/lib/session";

const LINKS = [
  { href: "/#how", label: "How it works" },
  { href: "/business", label: "For stores" },
];

export function SiteNav() {
  const { user } = useSession();
  const path = usePathname();
  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 px-6 md:px-12 ${path === "/" ? "" : "bg-canvas"}`}
    >
      <div className="mx-auto flex h-16 max-w-[1200px] items-center justify-between gap-3">
        <Wordmark />

        <div className="flex items-center gap-8">
          <nav aria-label="Main" className="hidden items-center gap-8 md:flex">
            {LINKS.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                aria-current={path === l.href ? "page" : undefined}
                className={`hud uppercase transition-colors duration-150 ${path === l.href ? "text-ink" : "text-ink-soft hover:text-ink"}`}
              >
                {l.label}
              </Link>
            ))}
          </nav>
          <div className="flex items-center gap-4">
            {user ? (
              <Link href="/studio" className="btn-signal min-h-9 px-4 text-sm">
                Open studio
              </Link>
            ) : (
              <>
                <Link
                  href="/login"
                  className="hud uppercase transition-colors hover:text-ink"
                >
                  Sign in
                </Link>
                <Link
                  href="/signup"
                  className="btn-signal min-h-9 px-4 text-sm"
                >
                  Get started
                </Link>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
