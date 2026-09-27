"use client";

import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { FABRICS } from "@/components/three/ClothScene";
import DecryptedText from "@/components/ui/DecryptedText";
import { Glyph } from "@/components/ui/Glyph";

gsap.registerPlugin(ScrollTrigger);

// WebGL only runs in the browser; the page renders fully without it.
const ClothScene = dynamic(() => import("@/components/three/ClothScene"), { ssr: false });

const STAGES = [
  ["Pose", "Body keypoints so the garment follows your shoulders and arms"],
  ["Mask", "The region your current clothes occupy, cut out cleanly"],
  ["Diffusion", "The new garment generated into that region with real drape"],
  ["Face", "Your face restored so it stays exactly yours"],
] as const;

export function LandingStory() {
  const story = useRef<HTMLDivElement>(null);
  const progress = useRef(0);
  const [fabric, setFabric] = useState(0);
  const onFabric = useCallback((i: number) => setFabric(i), []);

  useEffect(() => {
    const el = story.current;
    if (!el) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const ctx = gsap.context(() => {
      ScrollTrigger.create({
        trigger: el,
        start: "top top",
        end: "bottom bottom",
        onUpdate: (self) => (progress.current = self.progress),
      });
      if (!reduced) {
        // Pipeline bars fill as the Fit chapter scrolls through: the scroll explains the sequence.
        gsap.utils.toArray<HTMLElement>("[data-stage-bar]").forEach((bar, i) => {
          gsap.fromTo(
            bar,
            { scaleX: 0 },
            {
              scaleX: 1,
              ease: "none",
              scrollTrigger: { trigger: "#chapter-fit", start: `top+=${i * 12}% 75%`, end: `top+=${i * 12 + 30}% 45%`, scrub: true },
            },
          );
        });
      }
    }, el);
    return () => ctx.revert();
  }, []);

  return (
    <div ref={story} className="relative">
      <div className="sticky top-0 h-dvh w-full overflow-hidden">
        <ClothScene progress={progress} onFabric={onFabric} className="absolute inset-0" />
        <div className="label pointer-events-none absolute top-20 right-5 text-right text-mist md:right-8">
          <div className="text-fog">Fabric {String(fabric + 1).padStart(2, "0")} / {String(FABRICS.length).padStart(2, "0")}</div>
          <div className="mt-1 text-frost">{FABRICS[fabric].name}</div>
        </div>
      </div>

      <div className="relative -mt-[100dvh]">
        <Hero />
        <Chapter id="chapter-describe" index="01" kicker="Describe" title="Say it the way you'd say it to a friend.">
          <p>
            Type the outfit in plain English. The outfit interpreter turns your sentence into a structured spec: each garment,
            its colour, fabric and cut, the accessories, even the setting you want to be photographed in.
          </p>
          <SpecCard />
        </Chapter>
        <Chapter id="chapter-fit" index="02" kicker="Fit" title="Four passes between your photo and the look.">
          <p>
            Every try-on runs as a background job, and you watch each stage finish in real time. Your photo never leaves
            encrypted storage, and it is deleted on a schedule you can see.
          </p>
          <ol className="mt-8 space-y-5">
            {STAGES.map(([name, body], i) => (
              <li key={name}>
                <div className="label flex justify-between text-mist">
                  <span>
                    <span className="text-fog">{String(i + 1).padStart(2, "0")}</span> {name}
                  </span>
                </div>
                <div className="mt-2 h-px bg-line">
                  <div data-stage-bar className="h-px origin-left bg-signal" />
                </div>
                <p className="mt-2 text-sm text-mist">{body}</p>
              </li>
            ))}
          </ol>
        </Chapter>
        <Chapter id="chapter-live" index="03" kicker="Live" title="Or skip the photo and open your camera.">
          <p>
            Live try-on re-renders your camera feed with the garment on you while you move. Turn around, raise an arm, check
            the back. It streams in real time, and nothing from the camera is recorded.
          </p>
          <Link href="/live" className="btn-line mt-8">
            Try it live <Glyph name="arrow" className="arrow-nudge size-4" />
          </Link>
        </Chapter>
        <Chapter id="chapter-style" index="04" kicker="Style" title="A stylist that checks the weather first.">
          <p>
            Ask what to wear and the stylist works like a person would: it looks up the weather where you are going, searches
            the catalogue, remembers what you liked, and hands you pieces you can try on in one tap.
          </p>
          <Conversation />
        </Chapter>
      </div>
    </div>
  );
}

function Hero() {
  return (
    <section className="flex min-h-dvh flex-col justify-end px-5 pt-24 pb-10 md:px-8 md:pb-14">
      <div className="mx-auto w-full max-w-[1440px]">
        <p className="label mb-6 text-mist">
          <DecryptedText text="AI fashion designer and virtual try-on" animateOn="view" />
        </p>
        <h1 className="display-xl max-w-[12ch] text-[clamp(2.5rem,10.5vw,10.5rem)] text-frost mix-blend-difference">
          Describe it.
          <br />
          Wear it.
        </h1>
        <div className="mt-10 grid gap-8 md:grid-cols-[minmax(0,34rem)_1fr] md:items-end">
          <p className="max-w-[34rem] text-lg leading-relaxed text-mist">
            Upload a photo, write the outfit in a sentence, and LOOKBOOK shows you wearing it. From a navy blazer to a sherwani
            with gold embroidery, on you, in seconds.
          </p>
          <div className="flex flex-wrap gap-3 md:justify-end">
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

function Chapter({
  id,
  index,
  kicker,
  title,
  children,
}: {
  id: string;
  index: string;
  kicker: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="flex min-h-[115dvh] items-center px-5 py-24 md:px-8" aria-labelledby={`${id}-title`}>
      <div className="mx-auto w-full max-w-[1440px]">
        <div className="panel max-w-xl p-7 md:p-10">
          <p className="label flex items-center gap-3 text-signal">
            <span>[{index}]</span>
            <span className="h-px w-8 bg-line-strong" />
            <span className="text-mist">{kicker}</span>
          </p>
          <h2 id={`${id}-title`} className="display-md mt-6 text-[clamp(1.9rem,4vw,3.1rem)] text-frost">
            {title}
          </h2>
          <div className="mt-6 space-y-4 text-base leading-relaxed text-mist">{children}</div>
        </div>
      </div>
    </section>
  );
}

function SpecCard() {
  const rows = [
    ["Garment", "blazer"],
    ["Colour", "navy"],
    ["Fabric", "wool"],
    ["Fit", "tailored"],
    ["Details", "gold buttons"],
    ["Scene", "in front of a Ferrari"],
  ];
  return (
    <figure className="mt-8 border border-line-strong">
      <div className="border-b border-line-strong bg-ink-950 px-4 py-3 font-mono text-sm text-frost">
        <span className="text-fog">&gt;</span> a tailored navy wool blazer with gold buttons, in front of a Ferrari
      </div>
      <dl className="grid grid-cols-[7rem_1fr] font-mono text-sm">
        {rows.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="label border-b border-line px-4 py-2.5 text-fog">{k}</dt>
            <dd className="border-b border-line px-4 py-2.5 text-frost">{v}</dd>
          </div>
        ))}
      </dl>
      <figcaption className="label px-4 py-3 text-fog">Outfit interpreter output</figcaption>
    </figure>
  );
}

function Conversation() {
  return (
    <div className="mt-8 space-y-4 text-sm">
      <p className="border-l border-line-strong pl-4 text-frost">Mehndi on Saturday, outdoors in Lahore. I want colour.</p>
      <div className="flex flex-wrap gap-2">
        {["get_local_weather", "search_catalog", "search_style_notes"].map((t) => (
          <span key={t} className="label border border-line px-2 py-1 text-mist">
            {t}
          </span>
        ))}
      </div>
      <p className="border-l border-signal pl-4 text-mist">
        It will be warm, so skip heavy layers. Start with the mustard embroidered kurta, keep the trousers light, and add
        khussa. Tap the kurta to see it on you.
      </p>
    </div>
  );
}
