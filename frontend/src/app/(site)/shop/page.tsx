/* eslint-disable @next/next/no-img-element -- static demo assets */
import Link from "next/link";
import Script from "next/script";
import { CATALOG, describe } from "@/lib/catalog";

export const metadata = { title: "Demo Store — LOOKBOOK" };

/** A pretend retailer page that integrates LOOKBOOK exactly like a real store would. */
export default function ShopPage() {
  return (
    <div className="space-y-8">
      <Script src="/widget.js" strategy="afterInteractive" />

      <div className="rounded-2xl bg-zinc-900 px-6 py-10 text-white">
        <p className="text-xs font-semibold tracking-[0.3em] text-zinc-400">DEMO STORE</p>
        <h1 className="mt-2 text-3xl font-black tracking-tight">NORTHWIND ATELIER</h1>
        <p className="mt-2 max-w-xl text-sm text-zinc-300">
          A fictional shop showing the LOOKBOOK widget in place. Every &ldquo;Try it on live&rdquo;
          button below comes from one script tag. See the{" "}
          <Link href="/business#install" className="underline">
            install guide
          </Link>
          .
        </p>
      </div>

      <div className="grid grid-cols-2 gap-5 md:grid-cols-3">
        {CATALOG.map((g) => (
          <article key={g.id} className="group space-y-3">
            <div className="overflow-hidden rounded-xl bg-zinc-100">
              <img
                src={g.image}
                alt={g.name}
                className="aspect-[3/4] w-full object-contain p-6 transition group-hover:scale-105"
              />
            </div>
            <div className="flex items-baseline justify-between gap-2">
              <h2 className="text-sm font-semibold">{g.name}</h2>
              <span className="text-sm text-zinc-500">${g.price}</span>
            </div>
            <div className="flex gap-2">
              <button className="btn flex-1 bg-zinc-900 text-white hover:bg-zinc-700">Add to bag</button>
              <button
                className="btn-primary flex-1"
                data-lookbook-garment={describe(g)}
                data-lookbook-name={g.name}
                data-lookbook-image={g.image}
              >
                Try it on live
              </button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
