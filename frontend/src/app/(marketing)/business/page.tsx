import Link from "next/link";
import { CopyButton } from "@/components/ui/CopyButton";
import { Glyph } from "@/components/ui/Glyph";

export const metadata = { title: "For stores" };

const SCRIPT_TAG = `<script src="https://YOUR-LOOKBOOK-HOST/widget.js"
        data-lookbook-key="pk_live_your_store_key" async></script>`;
const BUTTON_TAG = `<button data-lookbook-garment="tailored navy wool blazer with gold buttons"
        data-lookbook-name="Tailored Blazer"
        data-lookbook-image="https://yourstore.com/images/blazer.jpg">
  Try it on
</button>`;

const STEPS = [
  ["Shopper taps Try it on", "A try-on window opens over your product page. No app, no account, no photo upload."],
  ["They see themselves wearing it", "Their camera feed is re-rendered with your garment in real time, following every turn."],
  ["They decide with confidence", "Close the window and they are back on your product page, one step from checkout."],
];

const DETAILS = [
  ["Your key, your domains", "Publishable keys only work on the origins you register. The try-on window refuses to load inside any other site."],
  ["No camera footage kept", "The live stream is processed in real time and not recorded or stored by LOOKBOOK."],
  ["Any product image", "Use your existing product photos as the reference, or describe the garment in words."],
  ["Capped usage", "Each store has a daily session limit and per-visitor rate limits, so a scraper can't run up your bill."],
];

const FAQ = [
  ["What runs the live try-on?", "A realtime video model for virtual try-on, streamed over WebRTC. Your server key never reaches the browser: the page receives a short-lived token scoped to one model and a five-minute session."],
  ["Which platforms does it work on?", "Anything that renders HTML: Shopify themes, WooCommerce, headless storefronts or hand-built sites. It adds no dependencies to your page."],
  ["What product photos work best?", "A clean, front-facing shot of the garment on a plain background. A text description alone also works."],
  ["Does it work on phones?", "Yes. The window is responsive and uses the front camera."],
];

export default function BusinessPage() {
  return (
    <div className="pt-14">
      <section className="border-b border-line px-5 py-24 md:px-8 md:py-32">
        <div className="mx-auto max-w-[1440px]">
          <p className="label text-mist">For stores</p>
          <h1 className="display-xl mt-6 max-w-[15ch] text-[clamp(2.8rem,8vw,7.5rem)]">A fitting room on every product page.</h1>
          <div className="mt-10 grid gap-8 md:grid-cols-[minmax(0,34rem)_1fr] md:items-end">
            <p className="text-lg leading-relaxed text-mist">
              Shoppers open their camera and see your clothes on themselves, moving, in real time. You add one script tag and
              one attribute.
            </p>
            <div className="flex flex-wrap gap-3 md:justify-end">
              <Link href="/shop" className="btn-signal">
                Open the demo store <Glyph name="arrow" className="arrow-nudge size-4" />
              </Link>
              <Link href="#install" className="btn-line">
                Install guide
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section className="px-5 py-24 md:px-8">
        <ol className="mx-auto grid max-w-[1440px] gap-px bg-line md:grid-cols-3">
          {STEPS.map(([title, body], i) => (
            <li key={title} className="bg-ink-900 p-8">
              <span className="label text-signal">[{String(i + 1).padStart(2, "0")}]</span>
              <h2 className="mt-6 text-xl font-semibold text-frost">{title}</h2>
              <p className="mt-3 leading-relaxed text-mist">{body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section id="install" className="scroll-mt-20 bg-bone px-5 py-24 text-ink-950 md:px-8">
        <div className="mx-auto max-w-[1440px]">
          <h2 className="display-md text-[clamp(2rem,4vw,3.2rem)]">Install in two steps</h2>
          <div className="mt-12 grid gap-6 lg:grid-cols-2">
            <Snippet step="01" title="Add the script once, before </body>" code={SCRIPT_TAG} />
            <Snippet step="02" title="Mark any button as a try-on trigger" code={BUTTON_TAG} />
          </div>
        </div>
      </section>

      <section className="px-5 py-24 md:px-8">
        <dl className="mx-auto grid max-w-[1440px] gap-x-12 gap-y-10 md:grid-cols-2">
          {DETAILS.map(([title, body]) => (
            <div key={title} className="border-t border-line pt-6">
              <dt className="text-lg font-semibold text-frost">{title}</dt>
              <dd className="mt-2 leading-relaxed text-mist">{body}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="border-t border-line px-5 py-24 md:px-8">
        <div className="mx-auto max-w-3xl">
          <h2 className="display-md text-3xl">Questions</h2>
          <div className="mt-8 divide-y divide-line border-y border-line">
            {FAQ.map(([q, a]) => (
              <details key={q} className="group py-5">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-6 text-frost">
                  {q}
                  <Glyph name="plus" className="size-4 shrink-0 transition-transform duration-200 group-open:rotate-45" />
                </summary>
                <p className="mt-3 leading-relaxed text-mist">{a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

function Snippet({ step, title, code }: { step: string; title: string; code: string }) {
  return (
    <figure className="border border-ink-950 bg-ink-950 text-frost">
      <figcaption className="flex items-center justify-between gap-4 border-b border-line px-5 py-3">
        <span className="label text-mist">
          <span className="text-signal">{step}</span> {title}
        </span>
        <CopyButton text={code} />
      </figcaption>
      <pre className="overflow-x-auto p-5 font-mono text-sm leading-relaxed">
        <code>{code}</code>
      </pre>
    </figure>
  );
}
