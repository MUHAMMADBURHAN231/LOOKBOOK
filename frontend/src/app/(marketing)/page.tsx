import Link from "next/link";
import { LandingStory } from "@/components/marketing/LandingStory";
import { Glyph } from "@/components/ui/Glyph";

export default function HomePage() {
  return (
    <>
      <div id="how" className="scroll-mt-14">
        <LandingStory />
      </div>

      <section className="bg-bone text-ink-950">
        <div className="mx-auto grid max-w-[1440px] gap-12 px-5 py-24 md:grid-cols-2 md:px-8 md:py-32">
          <div>
            <p className="label text-ink-800">For stores</p>
            <h2 className="display-md mt-5 text-[clamp(2rem,4.5vw,3.6rem)]">A fitting room on every product page.</h2>
          </div>
          <div className="space-y-6 text-lg leading-relaxed text-ink-800">
            <p>
              Add one script tag and a data attribute to any button. Shoppers open their camera and see the item on
              themselves before they buy.
            </p>
            <pre className="overflow-x-auto border border-bone-deep bg-ink-950 p-5 font-mono text-sm leading-relaxed text-frost">
              <code>{`<script src="https://lookbook.app/widget.js" async></script>\n<button data-lookbook-garment="tailored navy blazer"\n        data-lookbook-key="pk_live_...">Try it on</button>`}</code>
            </pre>
            <Link href="/business" className="btn border-ink-950 bg-ink-950 text-frost hover:bg-signal hover:text-ink-950">
              See the store integration <Glyph name="arrow" className="arrow-nudge size-4" />
            </Link>
          </div>
        </div>
      </section>

      <section className="px-5 py-28 md:px-8 md:py-40">
        <div className="mx-auto max-w-[1440px]">
          <h2 className="display-xl max-w-[14ch] text-[clamp(2.6rem,8vw,7rem)]">Try on the thing you keep thinking about.</h2>
          <div className="mt-12 flex flex-wrap gap-3">
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
