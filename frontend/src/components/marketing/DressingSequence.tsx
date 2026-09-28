"use client";
/* eslint-disable @next/next/no-img-element -- stacked, scroll-driven layers; next/image adds wrappers we can't animate */

import { useEffect, useRef } from "react";

/* Scroll-driven dressing sequence for the landing page, built from photographs.

   Five photos of the same model in the same pose: the base look and one per garment, each adding a
   layer. For garment i, its flat-lay cut-out enters from the right and travels onto her body; as it
   lands, the photo of her wearing it is revealed from the shoulders down behind a soft edge while
   the flat-lay fades into it. Everything is a pure function of scroll progress, so scrolling back
   takes the clothes off again. */

export type Garment = {
  name: string;
  /** Where the flat-lay lands, as fractions of the photo box. */
  target: { top: number; height: number };
};

export const GARMENTS: Garment[] = [
  { name: "Silk blouse", target: { top: 0.19, height: 0.3 } },
  { name: "Wide-leg trousers", target: { top: 0.43, height: 0.5 } },
  { name: "Tailored blazer", target: { top: 0.18, height: 0.36 } },
  { name: "Wool overcoat", target: { top: 0.17, height: 0.58 } },
];

const STATES = ["/look/state-0.webp", "/look/state-1.webp", "/look/state-2.webp", "/look/state-3.webp", "/look/state-4.webp"];
const FLATLAYS = ["/look/garment-1.webp", "/look/garment-2.webp", "/look/garment-3.webp", "/look/garment-4.webp"];

type Props = {
  /** 0..1 across the dressing sequence; read every frame through a ref. */
  progress: React.RefObject<number>;
  /** Index of the garment being put on, or -1 before the first one arrives. */
  onGarment?: (index: number) => void;
  className?: string;
};

const clamp01 = (v: number) => Math.min(1, Math.max(0, v));
const easeInOut = (v: number) => {
  const t = clamp01(v);
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
};

export default function DressingSequence({ progress, onGarment, className = "" }: Props) {
  const states = useRef<(HTMLImageElement | null)[]>([]);
  const flats = useRef<(HTMLImageElement | null)[]>([]);
  const stage = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const N = GARMENTS.length;
    let raf = 0;
    let last = -2;
    let lastP = -1;

    const tick = () => {
      raf = requestAnimationFrame(tick);
      const P = clamp01(progress.current ?? 0);
      if (P === lastP) return;
      lastP = P;
      const box = stage.current?.getBoundingClientRect();
      // Flat-lays start just past the right edge of the viewport.
      const enter = box ? window.innerWidth - box.left + 40 : 800;

      let current = -1;
      for (let i = 0; i < N; i++) {
        const s = clamp01(P * N - i);
        if (s > 0.25) current = i;
        const travel = easeInOut(s / 0.5);
        const reveal = easeInOut((s - 0.42) / 0.45);

        const flat = flats.current[i];
        if (flat) {
          const away = 1 - travel;
          flat.style.visibility = s <= 0.001 || reveal >= 1 ? "hidden" : "visible";
          flat.style.opacity = String(1 - reveal);
          flat.style.transform = reduced
            ? "none"
            : `translate3d(${enter * away}px, ${-40 * away}px, 0) rotate(${8 * away}deg) scale(${1 + 0.08 * away - 0.04 * reveal})`;
        }

        // Photo i+1 is her wearing garment i. Reveal it top-down with a feathered edge.
        const photo = states.current[i + 1];
        if (photo) {
          const edge = -12 + reveal * 124; // percent, from above the frame to below it
          const mask = `linear-gradient(to bottom, #000 ${edge - 12}%, transparent ${edge}%)`;
          photo.style.visibility = reveal <= 0 ? "hidden" : "visible";
          photo.style.maskImage = mask;
          photo.style.webkitMaskImage = mask;
        }
      }
      if (current !== last) {
        last = current;
        onGarment?.(current);
      }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [progress, onGarment]);

  return (
    <div className={className}>
      {/* Photo box: right of centre on wide screens, lower and centred on phones. */}
      <div
        ref={stage}
        className="absolute bottom-0 left-1/2 aspect-[2/3] h-[60dvh] -translate-x-1/2 md:top-1/2 md:bottom-auto md:left-[64%] md:h-[92dvh] md:-translate-y-1/2"
      >
        {/* Photos fade out at their edges so their backdrop melts into the page colour. */}
        <div
          className="absolute inset-0"
          style={{
            maskImage:
              "linear-gradient(to right, transparent, #000 14%, #000 86%, transparent), linear-gradient(to bottom, transparent, #000 5%, #000 95%, transparent)",
            maskComposite: "intersect",
            WebkitMaskImage:
              "linear-gradient(to right, transparent, #000 14%, #000 86%, transparent), linear-gradient(to bottom, transparent, #000 5%, #000 95%, transparent)",
            WebkitMaskComposite: "source-in",
          }}
        >
        {STATES.map((src, i) => (
          <img
            key={src}
            ref={(el) => {
              states.current[i] = el;
            }}
            src={src}
            alt={
              i === 0
                ? "A model in a white T-shirt and trousers, dressed layer by layer as you scroll: silk blouse, wide-leg trousers, tailored blazer and wool overcoat."
                : ""
            }
            aria-hidden={i === 0 ? undefined : true}
            width={1360}
            height={2048}
            decoding="async"
            fetchPriority={i === 0 ? "high" : "low"}
            className="absolute inset-0 h-full w-full object-contain select-none"
            style={i === 0 ? undefined : { visibility: "hidden" }}
            draggable={false}
          />
        ))}
        </div>
        {FLATLAYS.map((src, i) => {
          const t = GARMENTS[i].target;
          return (
            <img
              key={src}
              ref={(el) => {
                flats.current[i] = el;
              }}
              src={src}
              alt=""
              aria-hidden
              decoding="async"
              fetchPriority="low"
              className="pointer-events-none absolute left-1/2 w-auto -translate-x-1/2 drop-shadow-[0_18px_24px_rgba(17,17,17,0.12)] will-change-transform select-none"
              style={{ top: `${t.top * 100}%`, height: `${t.height * 100}%`, visibility: "hidden" }}
              draggable={false}
            />
          );
        })}
      </div>
    </div>
  );
}
