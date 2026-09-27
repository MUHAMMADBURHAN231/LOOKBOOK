import Link from "next/link";
import { Wordmark } from "@/components/ui/Wordmark";

const COLUMNS = [
  { title: "Product", links: [["Studio", "/studio"], ["Live try-on", "/live"], ["Stylist", "/stylist"], ["Wardrobe", "/wardrobe"]] },
  { title: "Stores", links: [["For stores", "/business"], ["Demo store", "/shop"], ["Widget install", "/business#install"]] },
  { title: "Trust", links: [["Privacy", "/privacy"], ["Your data", "/account"]] },
];

export function SiteFooter() {
  return (
    <footer className="border-t border-line bg-ink-950">
      <div className="mx-auto grid max-w-[1440px] gap-12 px-5 py-16 md:grid-cols-[1.4fr_repeat(3,1fr)] md:px-8">
        <div className="space-y-4">
          <Wordmark />
          <p className="max-w-xs text-sm leading-relaxed text-mist">
            Portraits are encrypted, never used for training, and deleted automatically after 14 days.
          </p>
        </div>
        {COLUMNS.map((col) => (
          <div key={col.title}>
            <h2 className="label mb-4 text-fog">{col.title}</h2>
            <ul className="space-y-3">
              {col.links.map(([label, href]) => (
                <li key={href}>
                  <Link href={href} className="text-sm text-mist transition-colors hover:text-frost">
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t border-line">
        <div className="label mx-auto flex max-w-[1440px] justify-between px-5 py-5 text-fog md:px-8">
          <span>LOOKBOOK</span>
          <span>Built for try-on, not for tracking</span>
        </div>
      </div>
    </footer>
  );
}
