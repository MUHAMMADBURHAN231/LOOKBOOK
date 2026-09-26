"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Studio" },
  { href: "/stylist", label: "AI Stylist" },
  { href: "/wardrobe", label: "Wardrobe" },
];

export default function Nav() {
  const path = usePathname();
  return (
    <header className="bg-linear-to-r from-brand-600 to-rose-500 text-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4">
        <Link href="/" className="text-xl font-black tracking-tight">
          LOOKBOOK
        </Link>
        <nav className="flex gap-1 text-sm font-medium">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`rounded-lg px-3 py-1.5 transition ${
                path === l.href ? "bg-white/25" : "hover:bg-white/15"
              }`}
            >
              {l.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
