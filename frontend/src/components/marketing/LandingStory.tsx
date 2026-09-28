"use client";

import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import DressingSequence, { GARMENTS } from "@/components/marketing/DressingSequence";

// Fallback when the photo set isn't installed: the 3D mannequin. WebGL only runs in the browser.
const WomanScene = dynamic(() => import("@/components/three/WomanScene"), { ssr: false });

gsap.registerPlugin(ScrollTrigger);

const CHAPTERS = [
  { title: "Describe it in your own words.", body: "LOOKBOOK reads the garment, colour, fabric and cut." },
  { title: "See it on you.", body: "Your photo, the new outfit, in seconds. Encrypted and deleted on schedule." },
  { title: "Or open your camera.", body: "Live try-on follows you as you move. Nothing is recorded." },
  { title: "Ask a stylist.", body: "It checks the weather, searches the catalogue and remembers what you like." },
] as const;

export function LandingStory({ photos }: { photos: boolean }) {
  const chapters = useRef<HTMLDivElement>(null);
  const progress = useRef(0);
  const [garment, setGarment] = useState(-1);
  const [chapter, setChapter] = useState(-1);
  const onGarment = useCallback((i: number) => setGarment(i), []);

  useEffect(() => {
    const el = chapters.current;
    if (!el) return;
    // Dressing starts as the first chapter comes up and finishes as the last one settles, so each
    // garment lands while its chapter is on screen.
    const trigger = ScrollTrigger.create({
      trigger: el,
      start: "top 55%",
      end: "bottom bottom",
      onUpdate: (self) => {
        progress.current = self.progress;
        // The first chapter waits until the hero has scrolled away.
        const next = self.progress < 0.05 ? -1 : Math.min(CHAPTERS.length - 1, Math.floor(self.progress * CHAPTERS.length));
        setChapter(next);
      },
    });
    return () => trigger.kill();
  }, []);

  return (
    <div className="relative">
      <div className="sticky top-0 h-dvh w-full overflow-hidden">
        {photos ? (
          <DressingSequence progress={progress} onGarment={onGarment} className="absolute inset-0" />
        ) : (
          <WomanScene progress={progress} onGarment={onGarment} className="absolute inset-0" />
        )}
        {/* One chapter at a time, cross-faded, in a fixed spot: top on phones (the figure sits
            below), left of the figure on wider screens. */}
        <div className="pointer-events-none absolute inset-x-0 top-24 px-6 md:top-1/2 md:-translate-y-1/2 md:px-12">
          <div className="mx-auto grid max-w-[1200px]">
            {CHAPTERS.map((c, i) => (
              <div
                key={c.title}
                className={`col-start-1 row-start-1 max-w-[22rem] transition-[opacity,transform] duration-500 ease-[var(--ease-out)] ${
                  chapter === i ? "translate-y-0 opacity-100" : "translate-y-3 opacity-0"
                }`}
              >
                <h2 className="display-md text-[clamp(1.75rem,3.2vw,2.75rem)] text-ink">{c.title}</h2>
                <p className="mt-4 text-base text-ink-soft md:text-lg">{c.body}</p>
              </div>
            ))}
          </div>
        </div>
        <p
          className={`label pointer-events-none absolute right-6 bottom-8 text-ink-soft transition-opacity duration-300 md:right-12 ${
            garment >= 0 ? "opacity-100" : "opacity-0"
          }`}
          aria-live="polite"
        >
          {garment >= 0 ? GARMENTS[garment].name : ""}
        </p>
      </div>

      <div className="relative -mt-[100dvh]">
        <section className="flex min-h-dvh items-start px-6 pt-24 md:items-center md:px-12 md:pt-0">
          <div className="mx-auto w-full max-w-[1200px]">
            <h1 className="display-xl max-w-[9ch] text-[clamp(3rem,8vw,7rem)] text-ink">Describe it. Wear it.</h1>
            <p className="mt-4 max-w-[26ch] text-lg text-ink-soft md:mt-6 md:text-xl">
              Upload a photo, describe any outfit, see it on you.
            </p>
            <div className="mt-8 flex items-center gap-6 md:mt-10">
              <Link href="/signup" className="btn-signal">
                Get started
              </Link>
              <Link href="/#how" className="link-quiet">
                How it works
              </Link>
            </div>
          </div>
        </section>

        {/* Scroll distance for the dressing sequence; the chapters render in the sticky layer. */}
        <div ref={chapters} id="how" className="h-[400dvh] scroll-mt-16" />
      </div>
    </div>
  );
}
