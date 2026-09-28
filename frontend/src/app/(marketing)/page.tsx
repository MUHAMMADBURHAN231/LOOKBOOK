import Link from "next/link";
import { LandingStory } from "@/components/marketing/LandingStory";

export default function HomePage() {
  return (
    <>
      <LandingStory />

      <section className="px-6 py-40 md:px-12 md:py-56">
        <div className="mx-auto grid max-w-[1200px] gap-10 md:grid-cols-2 md:items-end">
          <h2 className="display-md text-[clamp(2rem,4.5vw,3.5rem)] text-ink">A fitting room on every product page.</h2>
          <div className="min-w-0 md:justify-self-end">
            <p className="max-w-[30ch] text-lg text-ink-soft">
              One script tag adds live try-on to any online store.
            </p>
            <Link href="/business" className="link-quiet mt-6 inline-flex">
              For stores
            </Link>
          </div>
        </div>
      </section>

      <section className="px-6 pt-20 pb-48 md:px-12 md:pb-64">
        <div className="mx-auto flex max-w-[1200px] flex-col items-start gap-10">
          <h2 className="display-xl max-w-[12ch] text-[clamp(2.6rem,7vw,6rem)] text-ink">Try it on.</h2>
          <Link href="/signup" className="btn-signal">
            Create an account
          </Link>
        </div>
      </section>
    </>
  );
}
