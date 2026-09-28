/* eslint-disable @next/next/no-img-element -- static demo assets */
import Link from "next/link";
import Script from "next/script";
import { headers } from "next/headers";

export const metadata = { title: "Demo store" };

const PRODUCTS = [
  { slug: "tailored-blazer-navy", name: "Tailored Blazer", price: 249, description: "a tailored navy wool blazer with gold buttons, worn open" },
  { slug: "merino-turtleneck-black", name: "Merino Turtleneck", price: 89, description: "a sleek fitted black merino wool turtleneck sweater" },
  { slug: "trucker-jacket-denim", name: "Trucker Jacket", price: 129, description: "a mid-blue denim trucker jacket with contrast stitching" },
  { slug: "camel-overcoat", name: "Double-Breasted Overcoat", price: 380, description: "a camel double-breasted wool overcoat with peaked lapels" },
  { slug: "sherwani-ivory-gold", name: "Embroidered Sherwani", price: 420, description: "an ivory sherwani with gold embroidery and gold buttons" },
  { slug: "slip-dress-emerald", name: "Satin Slip Dress", price: 210, description: "an emerald green satin midi slip dress" },
];

/** A pretend retailer page wired up exactly as a real store would be: one script tag + data attributes. */
export default async function ShopPage() {
  const nonce = (await headers()).get("x-nonce") ?? undefined;
  return (
    <div className="bg-canvas pt-16 text-ink">
      <Script src="/widget.js" data-lookbook-key="pk_demo_northwind" strategy="afterInteractive" nonce={nonce} />
      <div className="mx-auto max-w-[1440px] px-5 py-16 md:px-8">
        <div className="flex flex-wrap items-end justify-between gap-6 border-b border-border pb-10">
          <div>
            <p className="label text-ink-soft">Demo store, not a real shop</p>
            <h1 className="display-xl mt-4 text-[clamp(2.4rem,6vw,5rem)]">Northwind Atelier</h1>
          </div>
          <p className="max-w-md text-ink-soft">
            Every &ldquo;Try it on&rdquo; button here comes from the LOOKBOOK widget, exactly as it would on your store.{" "}
            <Link href="/business#install" className="underline underline-offset-4">
              See how to install it
            </Link>
            .
          </p>
        </div>
        <ul className="grid gap-x-6 gap-y-12 pt-12 sm:grid-cols-2 lg:grid-cols-3">
          {PRODUCTS.map((p) => (
            <li key={p.slug}>
              <img src={`/demo/${p.slug}.webp`} alt={p.name} width={600} height={800} className="aspect-[3/4] w-full rounded-xl bg-surface-alt object-contain" />
              <div className="mt-4 flex items-baseline justify-between">
                <h2 className="text-lg font-semibold">{p.name}</h2>
                <span className="text-sm tabular-nums">${p.price}</span>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-2">
                <button className="btn-line">Add to bag</button>
                <button
                  className="btn-signal"
                  data-lookbook-garment={p.description}
                  data-lookbook-name={p.name}
                  data-lookbook-image={`/demo/${p.slug}.webp`}
                >
                  Try it on
                </button>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
