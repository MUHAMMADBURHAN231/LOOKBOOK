"use client";

import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { GARMENTS } from "@/components/three/WomanScene";
import { Glyph } from "@/components/ui/Glyph";
import DecryptedText from "@/components/ui/DecryptedText";

gsap.registerPlugin(ScrollTrigger);

// WebGL only runs in the browser; the page renders fully without it.
const WomanScene = dynamic(() => import("@/components/three/WomanScene"), { ssr: false });

const CHAPTERS = [
  {
    id: "chapter-describe",
    index: "01",
    kicker: "Describe",
    title: "Say it the way\nyou'd say it\nto a friend.",
    body: "Type the outfit in plain English. The outfit interpreter turns your sentence into a structured spec: each garment, its colour, fabric and cut, the accessories, even the setting.",
  },
  {
    id: "chapter-fit",
    index: "02",
    kicker: "Fit",
    title: "Four passes\nbetween your\nphoto and the look.",
    body: "Every try-on runs as a background job and you watch each stage in real time. Your photo never leaves encrypted storage, and it is deleted on a schedule you can see.",
  },
  {
    id: "chapter-live",
    index: "03",
    kicker: "Live",
    title: "Skip the photo.\nOpen your\ncamera.",
    body: "Live try-on re-renders your camera feed with the garment on you while you move. Turn around, raise an arm, check the back. Nothing is recorded.",
  },
  {
    id: "chapter-style",
    index: "04",
    kicker: "Style",
    title: "A stylist that\nchecks the\nweather first.",
    body: "Ask what to wear and the stylist works like a person would: looks up the weather, searches the catalogue, remembers what you liked, hands you pieces you can try on in one tap.",
  },
] as const;

export function LandingStory() {
  const story  = useRef<HTMLDivElement>(null);
  const progress = useRef(0);
  const [garment, setGarment] = useState(0);
  const onGarment = useCallback((i: number) => setGarment(i), []);

  useEffect(() => {
    const el = story.current;
    if (!el) return;

    const ctx = gsap.context(() => {
      ScrollTrigger.create({
        trigger: el,
        start: "top top",
        end: "bottom bottom",
        onUpdate: (self) => (progress.current = self.progress),
      });
    }, el);

    return () => ctx.revert();
  }, []);

  return (
    <div ref={story} className="relative">
      {/* ── Sticky 3-D canvas ── */}
      <div className="sticky top-0 h-dvh w-full overflow-hidden">
        <WomanScene
          progress={progress}
          onGarment={onGarment}
          className="absolute inset-0"
        />

        {/* Garment label — top-right */}
        <div className="pointer-events-none absolute top-20 right-6 text-right md:right-10">
          <p className="label text-[10px] tracking-widest text-ink-muted">
            {String(garment + 1).padStart(2, "0")} / {String(GARMENTS.length).padStart(2, "0")}
          </p>
          <p className="mt-0.5 font-mono text-[11px] tracking-wider text-ink-soft">
            {GARMENTS[garment].name}
          </p>
        </div>

        {/* Scroll hint — bottom-centre, fades as you scroll */}
        <div className="pointer-events-none absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 opacity-60">
          <span className="label text-[9px] tracking-[0.22em] text-ink-muted">Scroll</span>
          <span className="block h-8 w-px bg-ink-muted/40" />
        </div>
      </div>

      {/* ── Scrollable content layer ── */}
      <div className="relative -mt-[100dvh]">
        <Hero />

        {CHAPTERS.map((ch, i) => (
          <Chapter key={ch.id} chapter={ch} garmentName={GARMENTS[i]?.name} />
        ))}
      </div>
    </div>
  );
}

/* ── Hero ─────────────────────────────────────────── */
function Hero() {
  return (
    <section className="flex min-h-dvh flex-col justify-end px-6 pt-28 pb-12 md:px-12 md:pb-16">
      <div className="mx-auto w-full max-w-[1440px]">
        {/* Eyebrow */}
        <p className="label mb-8 text-ink-muted">
          <DecryptedText text="AI fashion designer · virtual try-on" animateOn="view" />
        </p>

        {/* Headline — left half, large */}
        <h1 className="display-xl max-w-[10ch] text-[clamp(3rem,11vw,10rem)] leading-[0.88] text-ink">
          Describe it.{" "}
          <span className="text-accent">Wear it.</span>
        </h1>

        {/* Sub-copy + CTAs */}
        <div className="mt-10 flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <p className="max-w-[36ch] text-lg font-light leading-relaxed text-ink-soft">
            Upload a photo, write the outfit in a sentence, and LOOKBOOK shows you wearing it,
            from a navy blazer to a sherwani with gold embroidery, in seconds.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link href="/signup" className="btn-signal">
              Try on your first look <Glyph name="arrow" className="arrow-nudge size-4" />
            </Link>
            <Link href="/#how" className="btn-line">
              How it works
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ── Chapter ──────────────────────────────────────── */
type ChapterDef = (typeof CHAPTERS)[number];

function Chapter({ chapter, garmentName }: { chapter: ChapterDef; garmentName?: string }) {
  return (
    <section
      id={chapter.id}
      className="flex min-h-[110dvh] items-center px-6 py-24 md:px-12"
      aria-labelledby={`${chapter.id}-title`}
    >
      <div className="mx-auto w-full max-w-[1440px]">
        <div className="max-w-[38rem]">
          {/* Index + kicker */}
          <p className="label flex items-center gap-4 text-ink-muted">
            <span className="tabular-nums">[{chapter.index}]</span>
            <span className="h-px w-8 bg-border-strong" />
            <span>{chapter.kicker}</span>
            {garmentName && (
              <>
                <span className="h-px w-8 bg-border-strong" />
                <span className="text-accent">{garmentName}</span>
              </>
            )}
          </p>

          {/* Title */}
          <h2
            id={`${chapter.id}-title`}
            className="mt-8 font-display text-[clamp(2.2rem,5.5vw,4.5rem)] font-bold leading-[0.92] tracking-tight text-ink"
            style={{ whiteSpace: "pre-line" }}
          >
            {chapter.title}
          </h2>

          {/* Body */}
          <p className="mt-8 text-base font-light leading-relaxed text-ink-soft md:text-lg">
            {chapter.body}
          </p>

          {/* Chapter-specific extras */}
          {chapter.id === "chapter-describe" && <SpecCard />}
          {chapter.id === "chapter-fit"      && <PipelineList />}
          {chapter.id === "chapter-live"     && (
            <Link href="/live" className="btn-line mt-10 inline-flex">
              Try it live <Glyph name="arrow" className="arrow-nudge size-4" />
            </Link>
          )}
          {chapter.id === "chapter-style"    && <Conversation />}
        </div>
      </div>
    </section>
  );
}

/* ── SpecCard ─────────────────────────────────────── */
function SpecCard() {
  const rows = [
    ["Garment", "blazer"],
    ["Colour",  "navy"],
    ["Fabric",  "wool"],
    ["Fit",     "tailored"],
    ["Details", "gold buttons"],
    ["Scene",   "in front of a Ferrari"],
  ];
  return (
    <figure className="mt-10 border border-border">
      <div className="border-b border-border bg-surface-alt px-4 py-3 font-mono text-sm text-ink">
        <span className="text-ink-muted">&gt;</span>{" "}
        a tailored navy wool blazer with gold buttons, in front of a Ferrari
      </div>
      <dl className="grid grid-cols-[7rem_1fr] font-mono text-sm">
        {rows.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="label border-b border-border px-4 py-2.5 text-ink-muted">{k}</dt>
            <dd className="border-b border-border px-4 py-2.5 text-ink">{v}</dd>
          </div>
        ))}
      </dl>
      <figcaption className="label px-4 py-3 text-ink-muted">Outfit interpreter output</figcaption>
    </figure>
  );
}

/* ── PipelineList ─────────────────────────────────── */
const STAGES = [
  ["Pose",      "Body keypoints so the garment follows your shoulders and arms"],
  ["Mask",      "The region your current clothes occupy, cut out cleanly"],
  ["Diffusion", "The new garment generated into that region with real drape"],
  ["Face",      "Your face restored so it stays exactly yours"],
] as const;

function PipelineList() {
  return (
    <ol className="mt-10 space-y-5">
      {STAGES.map(([name, body], i) => (
        <li key={name}>
          <div className="label flex items-center gap-3 text-ink-muted">
            <span className="tabular-nums text-ink-muted/60">{String(i + 1).padStart(2, "0")}</span>
            <span className="text-ink">{name}</span>
          </div>
          <div className="mt-2 h-px bg-border" />
          <p className="mt-2 text-sm font-light text-ink-soft">{body}</p>
        </li>
      ))}
    </ol>
  );
}

/* ── Conversation ─────────────────────────────────── */
function Conversation() {
  return (
    <div className="mt-10 space-y-5 text-sm">
      <p className="font-light text-ink">
        <span className="label mr-3 text-ink-muted">You</span>
        Mehndi on Saturday, outdoors in Lahore. I want colour.
      </p>
      <div className="flex flex-wrap gap-2">
        {["get_local_weather", "search_catalog", "search_style_notes"].map((t) => (
          <span key={t} className="label border border-border px-2 py-1 text-ink-muted">
            {t}
          </span>
        ))}
      </div>
      <p className="font-light text-ink-soft">
        <span className="label mr-3 text-accent">Stylist</span>
        It will be warm, so skip heavy layers. Start with the mustard embroidered kurta,
        keep the trousers light, and add khussa. Tap the kurta to see it on you.
      </p>
    </div>
  );
}
