"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import DecryptedText from "@/components/ui/DecryptedText";
import { Wordmark } from "@/components/ui/Wordmark";
import { useSession } from "@/lib/session";

const LINKS = [
  { href: "/#how", label: "How it works" },
  { href: "/business", label: "For stores" },
  { href: "/shop", label: "Demo store" },
];

export function SiteNav() {
  const { user } = useSession();
  const path = usePathname();
  return (
    <header className="fixed inset-x-0 top-0 z-50 border-b border-line/60 bg-ink-950">
      <div className="mx-auto flex h-14 max-w-[1440px] items-center justify-between gap-6 px-5 md:px-8">
        <Wordmark />
        <nav aria-label="Main" className="hidden items-center gap-7 md:flex">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`label transition-colors ${path === l.href ? "text-frost" : "text-mist hover:text-frost"}`}
            >
              <DecryptedText text={l.label} />
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          {user ? (
            <Link href="/studio" className="btn-signal min-h-9 px-4">
              Open studio
            </Link>
          ) : (
            <>
              <Link href="/login" className="btn-quiet min-h-9">
                Sign in
              </Link>
              <Link href="/signup" className="btn-signal min-h-9 px-4">
                Start
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
