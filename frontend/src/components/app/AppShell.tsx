"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef } from "react";
import { Glyph, type GlyphName } from "@/components/ui/Glyph";
import { Wordmark } from "@/components/ui/Wordmark";
import { useSession } from "@/lib/session";

const NAV: { href: string; label: string; glyph: GlyphName }[] = [
  { href: "/studio", label: "Studio", glyph: "plus" },
  { href: "/live", label: "Live", glyph: "camera" },
  { href: "/stylist", label: "Stylist", glyph: "send" },
  { href: "/wardrobe", label: "Wardrobe", glyph: "check" },
  { href: "/account", label: "Account", glyph: "arrow" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, signOut } = useSession();
  const path = usePathname();
  const router = useRouter();
  const leaving = useRef(false); // set while signing out, so the guard doesn't bounce to /login

  useEffect(() => {
    if (user === null && !leaving.current) router.replace(`/login?next=${encodeURIComponent(path)}`);
  }, [user, path, router]);

  const onSignOut = async () => {
    leaving.current = true;
    await signOut();
    router.replace("/");
  };

  if (!user) {
    return (
      <div className="grid min-h-dvh place-items-center" role="status" aria-live="polite">
        <span className="label text-mist">Loading your studio</span>
      </div>
    );
  }

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[220px_1fr]">
      <aside className="sticky top-0 hidden h-dvh flex-col justify-between border-r border-line bg-ink-950 p-5 lg:flex">
        <div>
          <Wordmark href="/" />
          <nav aria-label="App" className="mt-10 space-y-1">
            {NAV.map((n) => {
              const active = path.startsWith(n.href);
              return (
                <Link
                  key={n.href}
                  href={n.href}
                  aria-current={active ? "page" : undefined}
                  className={`label flex items-center justify-between px-3 py-3 transition-colors ${
                    active ? "bg-ink-800 text-frost" : "text-mist hover:bg-ink-850 hover:text-frost"
                  }`}
                >
                  {n.label}
                  {active && <span className="size-1.5 bg-signal" aria-hidden />}
                </Link>
              );
            })}
          </nav>
        </div>
        <div className="space-y-3 border-t border-line pt-5">
          <p className="truncate text-sm text-mist" title={user.email}>
            {user.full_name || user.email}
          </p>
          <button className="btn-quiet w-full justify-start px-0" onClick={onSignOut}>
            Sign out
          </button>
        </div>
      </aside>

      <div className="pb-20 lg:pb-0">
        <header className="flex h-14 items-center justify-between border-b border-line px-5 lg:hidden">
          <Wordmark href="/" />
          <button className="btn-quiet min-h-9" onClick={onSignOut}>
            Sign out
          </button>
        </header>
        <main id="main">{children}</main>
      </div>

      <nav aria-label="App" className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t border-line bg-ink-950 lg:hidden">
        {NAV.map((n) => {
          const active = path.startsWith(n.href);
          return (
            <Link
              key={n.href}
              href={n.href}
              aria-current={active ? "page" : undefined}
              className={`flex min-h-16 flex-col items-center justify-center gap-1.5 ${active ? "text-signal" : "text-mist"}`}
            >
              <Glyph name={n.glyph} />
              <span className="label text-[10px]">{n.label}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
