"use client";

import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Link from "next/link";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import ScrollVideo, {
  type ScrollVideoManifest,
} from "@/components/marketing/ScrollVideo";

gsap.registerPlugin(ScrollTrigger);

/* The landing film: one continuous shot, scrubbed by scroll. The stage is pinned while the visitor
   scrolls through it, so scroll position is the film's timeline, forwards and backwards.

   Timeline (scroll progress through the section, 0..1):
     0.00-0.08  she stands alone; the brand line is up
     0.08-0.80  the shirt drifts in from the right, reaches her and settles on (the film)
     0.80-1.00  still; the product label appears

   Everything readable is HTML over the canvas. Continuous values (opacity, the progress line) are
   written straight to the DOM from the scroll callback, not through React state. */

const FILM_START = 0.08;
const FILM_END = 0.8;

const REDUCED = "(prefers-reduced-motion: reduce)";
const subscribeReduced = (cb: () => void) => {
  const mq = window.matchMedia(REDUCED);
  mq.addEventListener("change", cb);
  return () => mq.removeEventListener("change", cb);
};
/** The visitor's reduced-motion preference, live. False on the server. */
const useReducedMotion = () =>
  useSyncExternalStore(
    subscribeReduced,
    () => window.matchMedia(REDUCED).matches,
    () => false,
  );

const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
/** 0 before a, 1 after b, smooth in between. */
const ramp = (x: number, a: number, b: number) => {
  const t = clamp01((x - a) / (b - a));
  return t * t * (3 - 2 * t);
};

export function FashionFilm({ film }: { film: ScrollVideoManifest }) {
  const section = useRef<HTMLElement>(null);
  const progress = useRef(0);
  const intro = useRef<HTMLDivElement>(null);
  const label = useRef<HTMLDivElement>(null);
  const line = useRef<HTMLSpanElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const [drawn, setDrawn] = useState(false);
  const reduced = useReducedMotion();

  // Scroll drives the film position and the overlays.
  useEffect(() => {
    if (reduced) return;
    const el = section.current;
    if (!el) return;
    const apply = (p: number) => {
      if (!Number.isFinite(p)) return;
      progress.current = clamp01((p - FILM_START) / (FILM_END - FILM_START));
      const out = ramp(p, 0.06, 0.16);
      if (intro.current) {
        intro.current.style.opacity = String(1 - out);
        intro.current.style.transform = `translate3d(0, ${-16 * out}px, 0)`;
      }
      const inn = ramp(p, 0.82, 0.92);
      if (label.current) {
        label.current.style.opacity = String(inn);
        label.current.style.transform = `translate3d(0, ${16 * (1 - inn)}px, 0)`;
        label.current.style.pointerEvents = inn > 0.5 ? "auto" : "none";
      }
      if (line.current) line.current.style.transform = `scaleX(${p})`;
    };
    const st = ScrollTrigger.create({
      trigger: el,
      start: "top top",
      end: "bottom bottom",
      onUpdate: (self) => apply(self.progress),
      onRefresh: (self) => apply(self.progress),
    });
    apply(st.progress);
    return () => st.kill();
  }, [reduced]);

  // The pointer leans the stage a few pixels: the scene answers the visitor even between scrolls.
  useEffect(() => {
    if (reduced || !stage.current) return;
    if (!window.matchMedia("(pointer: fine)").matches) return;
    const x = gsap.quickTo(stage.current, "x", {
      duration: 1.2,
      ease: "power3.out",
    });
    const y = gsap.quickTo(stage.current, "y", {
      duration: 1.2,
      ease: "power3.out",
    });
    const move = (e: PointerEvent) => {
      x(-((e.clientX / window.innerWidth) * 2 - 1) * 8);
      y(-((e.clientY / window.innerHeight) * 2 - 1) * 5);
    };
    window.addEventListener("pointermove", move, { passive: true });
    return () => window.removeEventListener("pointermove", move);
  }, [reduced]);

  const onFrame = useCallback(() => setDrawn(true), []);
  const backdrop = film.backdrop ?? "#EBE7DC";

  if (reduced) {
    // A still, designed version with the same content: the finished look and its label.
    return (
      <section
        aria-label="The Foundation Shirt"
        className="relative min-h-dvh overflow-hidden"
        style={{ background: backdrop }}
      >
        {/* Phones: text first, then the picture. Wider screens: text beside her, over the
            empty left of the frame. */}
        {film.poster && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={film.poster.end}
            alt="A model wearing a pale blue oversized cotton shirt over a cream base layer."
            className="hidden h-full w-full object-cover md:absolute md:inset-0 md:block"
            style={{ objectPosition: "60% 50%" }}
          />
        )}
        <div className="relative flex flex-col gap-10 px-6 pt-24 pb-10 md:min-h-dvh md:justify-center md:px-12 md:pb-16">
          <Intro />
          <Label />
        </div>
        {film.poster && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={film.poster.end}
            alt=""
            className="aspect-[4/5] w-full object-cover md:hidden"
            style={{ objectPosition: "60% 50%" }}
          />
        )}
      </section>
    );
  }

  return (
    <section
      ref={section}
      aria-label="The Foundation Shirt: a shirt flies in and dresses the model as you scroll"
      className="relative h-[300dvh] md:h-[340dvh]"
      style={{ background: backdrop }}
    >
      <div className="sticky top-0 h-dvh overflow-hidden">
        <div ref={stage} className="absolute -inset-3">
          {film.poster && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={film.poster.start}
              alt=""
              fetchPriority="high"
              className={`absolute inset-x-0 bottom-0 h-full w-full object-cover transition-opacity duration-500 portrait:h-[74%] ${drawn ? "opacity-0" : "opacity-100"}`}
              style={{ objectPosition: "60% 50%" }}
            />
          )}
          <ScrollVideo
            manifest={film}
            progress={progress}
            onFrame={onFrame}
            background="#F3F0E9"
            fill={backdrop}
            portraitHeight={0.74}
            edges="bottom"
            focusX={0.6}
            follow={6}
            label="A model in a cream base layer. A pale blue cotton shirt drifts in from the right and settles onto her as you scroll."
            className={`absolute inset-0 h-full w-full transition-opacity duration-500 ${drawn ? "opacity-100" : "opacity-0"}`}
          />
        </div>

        <div
          ref={intro}
          className="absolute inset-x-6 top-20 md:inset-x-auto md:top-1/2 md:left-12 md:-translate-y-1/2"
        >
          <Intro />
        </div>

        <div
          ref={label}
          className="pointer-events-none absolute inset-x-6 top-20 opacity-0 md:inset-x-auto md:left-12 md:top-1/2 md:-translate-y-1/2"
        >
          <Label />
        </div>

        <div className="absolute inset-x-6 bottom-8 flex items-center gap-4 md:inset-x-12">
          <span className="hud text-ink">01 / The shirt</span>
          <span className="relative h-px flex-1 bg-ink/15">
            <span
              ref={line}
              className="absolute inset-0 origin-left bg-ink"
              style={{ transform: "scaleX(0)" }}
            />
          </span>
          <span className="hud hidden sm:inline">Scroll</span>
        </div>
      </div>
    </section>
  );
}

function Intro() {
  return (
    <div className="max-w-[26rem]">
      <p className="hud">Collection 01 · Autumn 26</p>
      <h1 className="display-xl mt-3 text-[clamp(2.4rem,7vw,6.5rem)] text-ink md:mt-5">
        Wear it
        <br />
        <em className="italic">before</em> you buy it.
      </h1>
      <p className="mt-3 max-w-[30ch] text-sm leading-relaxed text-ink-soft md:mt-6 md:text-[0.9375rem]">
        Describe any outfit, or pick one, and see it on you.
      </p>
    </div>
  );
}

function Label() {
  return (
    <div className="max-w-[22rem]">
      <p className="hud text-ink">01</p>
      <h2 className="display-md mt-2 text-[clamp(2rem,4.6vw,4.25rem)] text-ink md:mt-4">
        The Foundation <br className="hidden md:block" />
        Shirt
      </h2>
      <p className="mt-2 max-w-[28ch] text-sm leading-relaxed text-ink-soft md:mt-5 md:text-[0.9375rem]">
        Washed cotton poplin. Relaxed through the body, cut long.
      </p>
      <Link
        href="/signup"
        className="link-quiet mt-4 inline-flex min-h-11 items-center gap-2 md:mt-7"
      >
        Try it on you <span aria-hidden="true">↗</span>
      </Link>
    </div>
  );
}
