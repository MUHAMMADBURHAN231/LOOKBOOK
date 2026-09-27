import Link from "next/link";
import CopyButton from "@/components/CopyButton";

export const metadata = { title: "LOOKBOOK for Business — Live Virtual Try-On for Your Store" };

const SCRIPT_TAG = `<script src="https://YOUR-LOOKBOOK-HOST/widget.js" async></script>`;
const BUTTON_TAG = `<button
  data-lookbook-garment="tailored navy wool blazer with gold buttons"
  data-lookbook-name="Tailored Blazer"
  data-lookbook-image="https://yourstore.com/images/blazer.jpg">
  Try it on live
</button>`;

const STEPS = [
  {
    title: "Shopper taps “Try it on live”",
    body: "A try-on window opens right on your product page. No app, no account, no photo upload.",
  },
  {
    title: "They see themselves wearing it",
    body: "The camera feed is re-rendered in real time with your garment, following every turn and step.",
  },
  {
    title: "They buy with confidence",
    body: "Swap colours, snap a picture to share, and head to checkout without leaving the page.",
  },
];

const FEATURES = [
  ["Real-time video", "A live, moving try-on powered by a realtime video model, not a static overlay."],
  ["One line to install", "One script tag plus a data attribute on your existing buttons. Works with any platform."],
  ["Any garment", "Use your product photos as the reference, or just describe the item in words."],
  ["Private by design", "The camera stream is processed live and not stored by LOOKBOOK. Shoppers opt in every time."],
  ["Photo-quality renders", "Shoppers can turn any live frame into a high-resolution image to save or share."],
  ["AI stylist built in", "Pair try-on with LOOKBOOK's stylist chat to suggest complete outfits around a product."],
];

const USE_CASES = [
  ["Product pages", "Add a try-on button next to “Add to bag” on every item."],
  ["In-store mirrors", "Run the live view on a screen and camera for a digital fitting room."],
  ["Campaigns & social", "Link straight to a try-on of a new drop from ads and posts."],
];

const FAQ = [
  [
    "What powers the live try-on?",
    "Decart's Lucy virtual try-on realtime model, streamed over WebRTC. LOOKBOOK issues short-lived tokens from your server so your API key never reaches the browser.",
  ],
  [
    "Do shoppers need to upload a photo?",
    "No. They allow camera access in the try-on window and see results immediately. Photo upload stays available in the LOOKBOOK Studio for anyone who prefers it.",
  ],
  [
    "What garment images work best?",
    "A clean front-facing product shot on a plain background. If you don't have one, a text description alone also works.",
  ],
  [
    "Does it work on mobile?",
    "Yes. The widget opens in a responsive window and uses the front camera on phones.",
  ],
];

export default function BusinessPage() {
  return (
    <div className="space-y-20 pb-10">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-3xl bg-zinc-950 px-6 py-16 text-center text-white sm:px-12">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(236,72,153,0.35),transparent_60%)]" />
        <div className="relative mx-auto max-w-3xl space-y-6">
          <p className="text-xs font-semibold tracking-[0.3em] text-brand-200">LOOKBOOK FOR BUSINESS</p>
          <h1 className="text-4xl font-black tracking-tight sm:text-5xl">
            Live virtual try-on for your store.{" "}
            <span className="bg-linear-to-r from-brand-500 to-rose-400 bg-clip-text text-transparent">
              One line of code.
            </span>
          </h1>
          <p className="text-lg text-zinc-300">
            Your shoppers open their camera and see themselves wearing your clothes, moving, in real
            time. Not a photo upload, not a render queue.
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            <Link href="/shop" className="btn-primary px-6 py-3">
              See it on a demo store
            </Link>
            <Link href="/live" className="btn border border-white/30 px-6 py-3 text-white hover:bg-white/10">
              Try it yourself
            </Link>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="space-y-8">
        <h2 className="text-center text-2xl font-black tracking-tight">How it works</h2>
        <ol className="grid gap-4 md:grid-cols-3">
          {STEPS.map((s, i) => (
            <li key={s.title} className="card space-y-2 p-6">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-600 text-sm font-bold text-white">
                {i + 1}
              </span>
              <h3 className="font-semibold">{s.title}</h3>
              <p className="text-sm text-zinc-500">{s.body}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Features */}
      <section className="space-y-8">
        <h2 className="text-center text-2xl font-black tracking-tight">Built for fashion retail</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(([title, body]) => (
            <div key={title} className="rounded-2xl border border-brand-100 bg-brand-50/60 p-5">
              <h3 className="font-semibold text-brand-700">{title}</h3>
              <p className="mt-1 text-sm text-zinc-600">{body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Install */}
      <section id="install" className="scroll-mt-8 space-y-6">
        <div className="text-center">
          <h2 className="text-2xl font-black tracking-tight">Install in two steps</h2>
          <p className="mt-1 text-sm text-zinc-500">Shopify, WooCommerce, headless or hand-built: if it has HTML, it works.</p>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <Snippet step="1" title="Add the script once, before </body>" code={SCRIPT_TAG} />
          <Snippet step="2" title="Mark any button as a try-on trigger" code={BUTTON_TAG} />
        </div>
      </section>

      {/* Use cases */}
      <section className="grid gap-4 md:grid-cols-3">
        {USE_CASES.map(([title, body]) => (
          <div key={title} className="card p-6">
            <h3 className="font-semibold">{title}</h3>
            <p className="mt-1 text-sm text-zinc-500">{body}</p>
          </div>
        ))}
      </section>

      {/* FAQ */}
      <section className="mx-auto max-w-3xl space-y-4">
        <h2 className="text-center text-2xl font-black tracking-tight">Questions</h2>
        {FAQ.map(([q, a]) => (
          <details key={q} className="card group p-5">
            <summary className="cursor-pointer list-none font-semibold marker:hidden">
              <span className="mr-2 text-brand-600 group-open:hidden">+</span>
              <span className="mr-2 hidden text-brand-600 group-open:inline">−</span>
              {q}
            </summary>
            <p className="mt-2 text-sm text-zinc-600">{a}</p>
          </details>
        ))}
      </section>

      {/* CTA */}
      <section className="rounded-3xl bg-linear-to-r from-brand-600 to-rose-500 px-6 py-12 text-center text-white">
        <h2 className="text-3xl font-black tracking-tight">Let shoppers try before they buy.</h2>
        <p className="mt-2 text-white/80">Open the demo store and press any “Try it on live” button.</p>
        <Link href="/shop" className="btn mt-6 bg-white px-6 py-3 text-brand-700 hover:bg-brand-50">
          Open the demo store
        </Link>
      </section>
    </div>
  );
}

function Snippet({ step, title, code }: { step: string; title: string; code: string }) {
  return (
    <div className="overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-950">
      <div className="flex items-center justify-between gap-3 border-b border-zinc-800 px-4 py-2.5">
        <p className="text-xs font-semibold text-zinc-300">
          <span className="mr-2 text-brand-500">{step}</span>
          {title}
        </p>
        <CopyButton text={code} />
      </div>
      <pre className="overflow-x-auto p-4 text-xs leading-relaxed text-zinc-200">
        <code>{code}</code>
      </pre>
    </div>
  );
}
