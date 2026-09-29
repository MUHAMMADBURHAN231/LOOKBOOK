"use client";

import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Scramble } from "@/components/marketing/Scramble";
import ScrollVideo, {
  type ScrollVideoManifest,
} from "@/components/marketing/ScrollVideo";
import type { Scene3DManifest } from "@/components/three/DressingScene";

// WebGL only runs in the browser. The cloth-simulated scene is the main story; the scroll video
// stands in without WebGL, and the stylised mannequin when neither is installed.
const DressingScene = dynamic(
  () => import("@/components/three/DressingScene"),
  {
    ssr: false,
  },
);
const WomanScene = dynamic(() => import("@/components/three/WomanScene"), {
  ssr: false,
});

gsap.registerPlugin(ScrollTrigger);

/* The landing story: one continuous, scroll-scrubbed shot of a model trying on three garments,
   framed by a light heads-up layer. Corner text, a decoding garment name behind her, and a leader
   line to a spec card when each garment settles. Discrete state (which look, whether it has
   settled) is React state; continuous values (progress bar) are written straight to the DOM. */

type Look = {
  code: string;
  name: string;
  chapter: { label: string; title: string; body: string };
  spec: [string, string][];
  /** Where the leader line starts, as fractions of the frame. */
  anchor: { x: number; y: number };
};

const LOOKS: Look[] = [
  {
    code: "LB-01",
    name: "Silk blouse",
    chapter: {
      label: "Describe",
      title: "Say it the way you would to a friend.",
      body: "Type the outfit in plain words. LOOKBOOK reads the garment, colour, fabric and cut.",
    },
    spec: [
      ["Fabric", "Silk satin"],
      ["Colour", "Dusty blue"],
      ["Fit", "Relaxed, bishop sleeve"],
    ],
    anchor: { x: 0.68, y: 0.32 },
  },
  {
    code: "LB-02",
    name: "Tailored blazer",
    chapter: {
      label: "Try on",
      title: "See it on you, not on a model.",
      body: "Your photo, the new outfit, in seconds. Encrypted, and deleted on a schedule you can see.",
    },
    spec: [
      ["Fabric", "Wool crepe"],
      ["Colour", "Black"],
      ["Fit", "Single-breasted"],
    ],
    anchor: { x: 0.7, y: 0.4 },
  },
  {
    code: "LB-03",
    name: "Wool overcoat",
    chapter: {
      label: "Live",
      title: "Or just open your camera.",
      body: "Live try-on follows you as you move. A stylist checks the weather and the catalogue for you.",
    },
    spec: [
      ["Fabric", "Brushed wool"],
      ["Colour", "Camel"],
      ["Fit", "Long, notched lapel"],
    ],
    anchor: { x: 0.72, y: 0.52 },
  },
];

const pad2 = (n: number) => String(n).padStart(2, "0");

/* Scroll to video position. Each chapter is a camera move between two stations, like the reference
   sites: it eases out of the last look, travels, eases into the next and then holds there while
   the chapter text and spec card are read. Travel keeps a linear share so scrolling always moves
   something straight away. The video is re-timed at build time for even on-screen speed, so this
   curve is the whole speed profile. */
const HOLD = 0.3;
const travel = (x: number) => 0.35 * x + 0.65 * x * x * (3 - 2 * x);

function positionFor(scroll: number, marks: number[]) {
  const n = marks.length;
  const seg = Math.min(n - 1, Math.floor(scroll * n));
  const from = seg === 0 ? 0 : marks[seg - 1];
  const u = Math.min(1, (scroll * n - seg) / (1 - HOLD));
  return from + (marks[seg] - from) * travel(u);
}

export function LandingStory({
  video,
  scene3d,
}: {
  video: ScrollVideoManifest | null;
  scene3d: Scene3DManifest | null;
}) {
  const story = useRef<HTMLDivElement>(null);
  const bar = useRef<HTMLSpanElement>(null);
  const progress = useRef(0);
  const [look, setLook] = useState(-1);
  const [settled, setSettled] = useState(false);
  const [loaded, setLoaded] = useState(0);
  const [use3d, setUse3d] = useState(!!scene3d);
  const [ready, setReady] = useState(!scene3d && !video);
  const state = useRef({ look: -1, settled: false });
  const clip = use3d ? null : video;
  // Where each look is complete, as positions along the story. The 3D scene has its stations at
  // equal thirds; the video records its own.
  const marks = useMemo(
    () =>
      !use3d && clip?.marks?.length === LOOKS.length
        ? clip.marks
        : LOOKS.map((_, i) => (i + 1) / LOOKS.length),
    [use3d, clip],
  );
  // Resolution of the position, for "settled" (within about a frame of a station).
  const frames = use3d ? 390 : (clip?.count ?? 1);
  const staged = use3d || !!clip;
  const calloutRefs = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    const el = story.current;
    if (!el) return;
    const trigger = ScrollTrigger.create({
      trigger: el,
      start: "top 55%",
      end: "bottom bottom",
      onUpdate: (self) => {
        // ScrollTrigger can report NaN while the layout settles (start and end coincide).
        const p = Number.isFinite(self.progress) ? self.progress : 0;
        progress.current = staged ? positionFor(p, marks) : p;
      },
    });
    return () => trigger.kill();
  }, [staged, marks]);

  // Discrete story state follows the frame actually drawn.
  const onFrame = useCallback(
    (pos: number) => {
      if (bar.current) bar.current.style.transform = `scaleX(${pos})`;
      let i = marks.findIndex((mark) => pos <= mark + 0.001);
      if (i < 0) i = marks.length - 1;
      if (pos < 0.01) i = -1;
      // Settled once the playhead is within about a frame of the look's station.
      const s = i >= 0 && (marks[i] - pos) * (frames - 1) < 1.2;
      if (i !== state.current.look) {
        state.current.look = i;
        setLook(i);
      }
      if (s !== state.current.settled) {
        state.current.settled = s;
        setSettled(s);
      }
    },
    [marks, frames],
  );

  const onLoad = useCallback((fraction: number, coarseReady: boolean) => {
    setLoaded(fraction);
    if (coarseReady) setReady(true);
  }, []);

  // Spec cards follow points on the 3D model (written straight to the DOM every frame).
  const onAnchors = useCallback(
    (points: { x: number; y: number; visible: boolean }[]) => {
      points.forEach((pt, i) => {
        const el = calloutRefs.current[i];
        if (el) el.style.transform = `translate3d(${pt.x}px, ${pt.y}px, 0)`;
      });
    },
    [],
  );
  const onUnsupported = useCallback(() => {
    setUse3d(false);
    setReady(!video);
  }, [video]);

  // The stylised mannequin reports garments directly.
  const onGarment = useCallback(
    (i: number) => setLook(Math.min(i, LOOKS.length - 1)),
    [],
  );

  const current = look >= 0 ? LOOKS[look] : null;

  return (
    <div className="relative">
      {staged && <Loader fraction={loaded} ready={ready} />}

      <div className="sticky top-0 h-dvh w-full overflow-hidden">
        {/* Backdrop: soft vignette and a sparse dot grid. */}
        <div
          className="stage-backdrop pointer-events-none absolute inset-0"
          aria-hidden="true"
        />

        {/* Garment name, huge and faint, behind the model. */}
        <div
          className="pointer-events-none absolute inset-x-0 bottom-[20dvh] text-center font-mono text-[15vw] leading-none font-medium tracking-tight text-ink/[0.06] uppercase select-none md:top-1/2 md:bottom-auto md:left-[28%] md:-translate-y-1/2 md:text-ink/[0.05]"
          aria-hidden="true"
        >
          {current && <Scramble text={current.name} duration={900} />}
        </div>

        {use3d && scene3d ? (
          <>
            <DressingScene
              manifest={scene3d}
              progress={progress}
              onFrame={onFrame}
              onLoad={onLoad}
              onAnchors={onAnchors}
              onUnsupported={onUnsupported}
              label="A white robot mannequin being dressed in a silk blouse, a tailored blazer and a wool overcoat as you scroll. Each garment flies in as flat sewing patterns and sews itself on."
              className="absolute inset-0"
            />
            <div className="pointer-events-none absolute bottom-0 left-1/2 aspect-[9/16] h-[58dvh] -translate-x-1/2 md:top-1/2 md:bottom-auto md:left-[64%] md:h-[92dvh] md:-translate-y-1/2">
              <Brackets />
            </div>
            {LOOKS.map((l, i) => (
              <Callout
                key={l.code}
                ref={(el) => {
                  calloutRefs.current[i] = el;
                }}
                look={l}
                index={i}
                visible={look === i && settled}
              />
            ))}
          </>
        ) : clip ? (
          // Blend on this wrapper, not the canvas: the transform makes this element its own stacking
          // context, and the white backdrop must multiply into the stage behind it.
          <div className="absolute bottom-0 left-1/2 aspect-[9/16] h-[58dvh] -translate-x-1/2 mix-blend-multiply md:top-1/2 md:bottom-auto md:left-[64%] md:h-[92dvh] md:-translate-y-1/2">
            <ScrollVideo
              manifest={clip}
              progress={progress}
              onFrame={onFrame}
              onLoad={onLoad}
              label="A model trying on a silk blouse, a tailored blazer and a wool overcoat as you scroll."
              className="h-full w-full"
            />
            <Brackets />
            {LOOKS.map((l, i) => (
              <Callout
                key={l.code}
                look={l}
                index={i}
                visible={look === i && settled}
              />
            ))}
          </div>
        ) : (
          <WomanScene
            progress={progress}
            onGarment={onGarment}
            className="absolute inset-0"
          />
        )}

        {/* Heads-up corners, aligned to the same column as the nav and headings. */}
        <div className="pointer-events-none absolute inset-0 px-6 md:px-12">
          <div className="relative mx-auto h-full max-w-[1200px]">
            <div className="hud absolute top-20 left-0 hidden md:block">
              <p>{"//"} Copyright &copy; 2026</p>
              <p className="mt-2">
                LOOKBOOK Studio.
                <br />
                Every look here is generated.
              </p>
            </div>
            <div className="hud absolute top-20 right-0 hidden max-w-[17rem] text-right md:block">
              <p>{"//////"} Manifesto</p>
              <p className="mt-2 text-ink">
                No fitting room, no photoshoot, no guessing. Describe any outfit
                and see it on you.
              </p>
            </div>
            <div className="hud absolute bottom-7 left-0">
              <p className="hidden md:block">
                Scroll down to
                <br />
                discover.
              </p>
              <p className="mt-3 flex items-center gap-3 text-ink">
                <span className="tabular-nums">
                  [{look >= 0 ? pad2(look + 1) : "00"}/{pad2(LOOKS.length)}]
                </span>
                <span className="relative block h-px w-24 bg-ink/15 md:w-40">
                  <span
                    ref={bar}
                    className="absolute inset-0 origin-left scale-x-0 bg-ink"
                  />
                </span>
                <span>
                  {current ? (
                    <Scramble text={current.name} fromEmpty={false} />
                  ) : (
                    "Base look"
                  )}
                </span>
              </p>
            </div>
            <div className="hud absolute right-0 bottom-7 hidden text-right md:block">
              <p>
                {use3d
                  ? "Real-time 3D · WebGL"
                  : clip
                    ? `${clip.width} × ${clip.height} · ${clip.count} frames`
                    : "Real-time 3D"}
                <br />
                {use3d
                  ? "Cloth simulated, not keyframed."
                  : "One take, no cuts."}
              </p>
            </div>
          </div>
        </div>

        {/* One chapter at a time: top on phones (the model sits below), left of her on desktop. */}
        <div className="pointer-events-none absolute inset-x-0 top-24 px-6 md:top-1/2 md:-translate-y-1/2 md:px-12">
          <div className="grid max-w-[1200px] md:mx-auto">
            {LOOKS.map((l, i) => (
              <div
                key={l.code}
                className={`col-start-1 row-start-1 max-w-[21rem] transition-[opacity,transform] duration-500 ease-[var(--ease-out)] ${
                  look === i
                    ? "translate-y-0 opacity-100"
                    : "translate-y-3 opacity-0"
                }`}
              >
                <p className="hud text-ink">
                  [{pad2(i + 1)}] {"//"} {l.chapter.label}
                </p>
                <h2 className="display-md mt-4 text-[clamp(1.75rem,3vw,2.6rem)] text-ink">
                  {l.chapter.title}
                </h2>
                <p className="mt-4 text-base text-ink-soft md:text-lg">
                  {l.chapter.body}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="relative -mt-[100dvh]">
        <section className="flex min-h-dvh items-start px-6 pt-24 md:items-center md:px-12 md:pt-0">
          <div className="mx-auto w-full max-w-[1200px]">
            <p className="hud text-ink">
              [AI fashion designer] {"//"} Virtual try-on
            </p>
            <h1 className="display-xl mt-6 max-w-[9ch] text-[clamp(3rem,7vw,6.25rem)] text-ink">
              Describe it. Wear it.
            </h1>
            <p className="mt-5 max-w-[28ch] text-lg text-ink-soft md:text-xl">
              Upload a photo, describe any outfit in plain words, and see it on
              you.
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

        {/* Scroll distance for the story; everything above renders in the sticky layer. */}
        <div ref={story} id="how" className="h-[480dvh] scroll-mt-16" />
      </div>
    </div>
  );
}

/** Corner brackets framing the model, like a viewfinder. */
function Brackets() {
  const c = "pointer-events-none absolute size-5 border-ink/40";
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-[6%_10%_4%] hidden md:block"
    >
      <span className={`${c} top-0 left-0 border-t border-l`} />
      <span className={`${c} top-0 right-0 border-t border-r`} />
      <span className={`${c} bottom-0 left-0 border-b border-l`} />
      <span className={`${c} right-0 bottom-0 border-r border-b`} />
    </div>
  );
}

/** Leader line from the garment to a spec card, drawn when the garment settles. Desktop only:
 *  on a phone the frame fills the width and there is no room beside her. */
function Callout({
  look,
  index,
  visible,
  ref,
}: {
  look: Look;
  index: number;
  visible: boolean;
  /** With a ref the caller positions the card (a transform to a projected 3D point); without, it
   *  sits at the look's anchor within the frame. */
  ref?: React.Ref<HTMLDivElement>;
}) {
  return (
    <div
      ref={ref}
      aria-hidden={!visible}
      className="pointer-events-none absolute hidden will-change-transform md:block"
      style={
        ref
          ? { left: 0, top: 0 }
          : { left: `${look.anchor.x * 100}%`, top: `${look.anchor.y * 100}%` }
      }
    >
      <span
        className={`absolute -top-1 -left-1 size-2 rounded-full bg-ink transition-transform duration-300 ${
          visible ? "scale-100" : "scale-0"
        }`}
      />
      <svg
        className="absolute top-0 left-0 overflow-visible"
        width="1"
        height="1"
        aria-hidden="true"
      >
        <polyline
          points="0,0 44,-44 170,-44"
          fill="none"
          stroke="currentColor"
          strokeWidth="1"
          pathLength={1}
          className="text-ink/60"
          style={{
            strokeDasharray: 1,
            strokeDashoffset: visible ? 0 : 1,
            transition: `stroke-dashoffset 520ms cubic-bezier(0.23, 1, 0.32, 1) ${visible ? 120 : 0}ms`,
          }}
        />
      </svg>
      <div
        className={`hud absolute -top-[84px] left-[50px] w-44 transition-opacity duration-300 ${
          visible ? "opacity-100 delay-500" : "opacity-0"
        }`}
      >
        <p className="text-ink">
          {visible ? (
            <Scramble text={`${look.code} // ${look.name}`} />
          ) : (
            `${look.code} // ${look.name}`
          )}
        </p>
        <dl className="mt-10 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
          {look.spec.map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="text-ink-muted">{k}</dt>
              <dd className="text-ink">{v}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-2 text-ink-muted tabular-nums">
          [{pad2(index + 1)}/03]
        </p>
      </div>
    </div>
  );
}

/** Opening screen shown while the first pass of frames decodes. */
function Loader({ fraction, ready }: { fraction: number; ready: boolean }) {
  const pct = Math.round(fraction * 100);
  return (
    <div
      role="status"
      aria-live="polite"
      className={`fixed inset-0 z-[70] flex flex-col items-center justify-center bg-canvas transition-[opacity,visibility] duration-700 ease-[var(--ease-out)] ${
        ready ? "invisible opacity-0" : "visible opacity-100"
      }`}
    >
      <p className="display-md text-4xl text-ink md:text-5xl">
        LOOK<span className="text-ink-muted">/</span>BOOK
      </p>
      <p className="hud mt-6 text-ink tabular-nums">
        Loading [ {String(pct).padStart(3, "0")}% ]
      </p>
      <span className="relative mt-4 block h-px w-48 bg-ink/15">
        <span
          className="absolute inset-0 origin-left bg-ink transition-transform duration-200"
          style={{ transform: `scaleX(${Math.max(fraction, 0.02)})` }}
        />
      </span>
    </div>
  );
}
