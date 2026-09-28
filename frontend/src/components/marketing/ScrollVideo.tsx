"use client";

import { useEffect, useRef } from "react";

/* A video scrubbed by scroll, drawn frame by frame to a canvas (the technique Apple uses on its
   product pages). A <video> element can't seek smoothly on every browser, so the video is shipped
   as numbered WebP frames instead.

   Loading is progressive: the first frame first, then every 8th frame so the whole timeline is
   roughly available quickly, then the frames in between. While a frame is missing the nearest
   loaded one is drawn, so scrolling never shows a blank.

   The drawn frame eases toward the scroll position rather than jumping to it, which keeps motion
   smooth under a flick of the wheel and turns scrolling back into playing it in reverse. */

export type ScrollVideoManifest = {
  /** URL pattern with {i} for the 1-based, zero-padded frame number, e.g. "/look/frames/f-{i}.webp". */
  pattern: string;
  count: number;
  pad: number;
  width: number;
  height: number;
};

type Props = {
  manifest: ScrollVideoManifest;
  /** 0..1 across the sequence; read every frame through a ref. */
  progress: React.RefObject<number>;
  /** Called with the fractional position (0..1) actually drawn, for syncing captions. */
  onFrame?: (position: number) => void;
  className?: string;
  label: string;
};

export default function ScrollVideo({ manifest, progress, onFrame, className = "", label }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const el = canvas.current;
    const ctx = el?.getContext("2d", { alpha: false });
    if (!el || !ctx) return;
    const { count, pad, pattern } = manifest;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const url = (i: number) => pattern.replace("{i}", String(i + 1).padStart(pad, "0"));

    const frames: (HTMLImageElement | null)[] = new Array(count).fill(null);
    const loaded = new Uint8Array(count);
    let cancelled = false;
    let dirty = true;

    // Load order: first frame, a coarse pass over the timeline, then everything else.
    const order: number[] = [0];
    for (let i = 8; i < count; i += 8) order.push(i);
    order.push(count - 1);
    for (let i = 1; i < count; i++) if (i % 8 !== 0 && i !== count - 1) order.push(i);

    let next = 0;
    const PARALLEL = 6;
    const pump = () => {
      if (cancelled || next >= order.length) return;
      const i = order[next++];
      const img = new Image();
      img.decoding = "async";
      img.onload = () => {
        frames[i] = img;
        loaded[i] = 1;
        dirty = true;
        pump();
      };
      img.onerror = () => pump();
      img.src = url(i);
    };
    for (let k = 0; k < PARALLEL; k++) pump();

    const nearestLoaded = (i: number) => {
      for (let d = 0; d < count; d++) {
        if (i - d >= 0 && loaded[i - d]) return i - d;
        if (i + d < count && loaded[i + d]) return i + d;
      }
      return -1;
    };

    const resize = () => {
      const r = el.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      el.width = Math.max(1, Math.round(r.width * dpr));
      el.height = Math.max(1, Math.round(r.height * dpr));
      dirty = true;
    };
    const ro = new ResizeObserver(resize);
    ro.observe(el);
    resize();

    let shown = -1;
    let position = 0; // eased 0..1
    let raf = 0;
    const tick = () => {
      raf = requestAnimationFrame(tick);
      const target = Math.min(1, Math.max(0, progress.current ?? 0));
      position = reduced ? target : position + (target - position) * 0.18;
      if (Math.abs(target - position) < 0.0005) position = target;
      const want = Math.round(position * (count - 1));
      const i = nearestLoaded(want);
      if (i < 0 || (i === shown && !dirty)) return;
      const img = frames[i]!;
      // Cover the canvas height and centre horizontally (the frames are portrait).
      const scale = Math.max(el.width / img.naturalWidth, el.height / img.naturalHeight);
      const w = img.naturalWidth * scale;
      const h = img.naturalHeight * scale;
      ctx.fillStyle = "#F8F7F5";
      ctx.fillRect(0, 0, el.width, el.height);
      ctx.drawImage(img, (el.width - w) / 2, (el.height - h) / 2, w, h);
      shown = i;
      dirty = false;
      onFrame?.(position);
    };
    raf = requestAnimationFrame(tick);

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [manifest, progress, onFrame]);

  return <canvas ref={canvas} role="img" aria-label={label} className={className} />;
}
