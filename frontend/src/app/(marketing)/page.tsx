import Link from "next/link";
import { LandingStory } from "@/components/marketing/LandingStory";
import { Glyph } from "@/components/ui/Glyph";

export default function HomePage() {
  return (
    <>
      {/* ── Scroll-driven 3-D story ── */}
      <div id="how" className="scroll-mt-14">
        <LandingStory />
      </div>

      {/* ── For Stores section ── */}
      <section className="border-t border-border bg-surface">
        <div className="mx-auto grid max-w-[1440px] gap-14 px-6 py-24 md:grid-cols-2 md:px-12 md:py-36">
          <div>
            <p className="label text-ink-muted">For stores</p>
            <h2 className="mt-6 font-display text-[clamp(2rem,5vw,3.8rem)] font-700 leading-[0.92] tracking-tight text-ink">
              A fitting room on every product page.
            </h2>
          </div>
          <div className="flex flex-col justify-between gap-8">
            <p className="text-lg font-light leading-relaxed text-ink-soft">
              Add one script tag and a data attribute to any button. Shoppers open their camera
              and see the item on themselves before they buy.
            </p>
            <pre className="overflow-x-auto border border-border bg-surface-alt px-5 py-4 font-mono text-xs leading-relaxed text-ink">
              <code>{`<script src="https://lookbook.app/widget.js" async></script>\n<button data-lookbook-garment="tailored navy blazer"\n        data-lookbook-key="pk_live_...">Try it on</button>`}</code>
            </pre>
            <Link
              href="/business"
              className="btn-line self-start"
            >
              See the store integration <Glyph name="arrow" className="arrow-nudge size-4" />
            </Link>
          </div>
        </div>
      </section>

      {/* ── Final CTA ── */}
      <section className="px-6 py-32 md:px-12 md:py-44">
        <div className="mx-auto max-w-[1440px]">
          <h2 className="display-xl max-w-[14ch] text-[clamp(2.8rem,9vw,8rem)] text-ink">
            Try on the thing you keep thinking about.
          </h2>
          <div className="mt-14 flex flex-wrap gap-4">
            <Link href="/signup" className="btn-signal">
              Create your account <Glyph name="arrow" className="arrow-nudge size-4" />
            </Link>
            <Link href="/login" className="btn-line">
              I have an account
            </Link>
          </div>
        </div>
      </section>
    </>
  );
}
