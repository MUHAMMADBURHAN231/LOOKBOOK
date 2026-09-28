"use client";

import gsap from "gsap";
import { useEffect, useRef } from "react";

/* A video scrubbed by scroll, drawn frame by frame to a canvas (the technique Apple uses on its
   product pages). A <video> element can't seek smoothly on every browser, so the video is shipped
   as numbered WebP frames instead.

   Smoothness comes from four things:
   - Frames are fetched and decoded off the main thread (createImageBitmap) before they're needed,
     so drawing never waits on a decode.
   - The position is fractional and the two neighbouring frames are blended, so motion is
     continuous between the 24 frames per second of the source instead of stepping.
   - Drawing runs on GSAP's ticker right after Lenis updates the scroll, in the same frame, so the
     picture never lags a frame behind the page.
   - The soft edge is painted in the canvas, so the browser doesn't re-mask a layer every frame.

   Loading is progressive: the first frame, then every 8th frame, then the rest. While a frame is
   missing the nearest decoded one is drawn. */

export type ScrollVideoManifest = {
  /** URL pattern with {i} for the 1-based, zero-padded frame number, e.g. "/look/frames/f-{i}.webp". */
  pattern: string;
  count: number;
  pad: number;
  width: number;
  height: number;
};

type Frame = ImageBitmap | HTMLImageElement;

type Props = {
  manifest: ScrollVideoManifest;
  /** 0..1 across the sequence; read every frame through a ref. */
  progress: React.RefObject<number>;
  /** Called with the position (0..1) drawn, when it changes, for syncing captions. */
  onFrame?: (position: number) => void;
  className?: string;
  label: string;
  /** Page colour the frame's edges fade into. */
  background?: string;
};

export default function ScrollVideo({ manifest, progress, onFrame, className = "", label, background = "#F8F7F5" }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const el = canvas.current;
    const ctx = el?.getContext("2d", { alpha: false });
    if (!el || !ctx) return;
    const { count, pad, pattern } = manifest;
    const url = (i: number) => pattern.replace("{i}", String(i + 1).padStart(pad, "0"));

    const frames: (Frame | null)[] = new Array(count).fill(null);
    let cancelled = false;
    let dirty = true;

    const decode = async (i: number): Promise<Frame> => {
      if ("createImageBitmap" in window) {
        const res = await fetch(url(i));
        return createImageBitmap(await res.blob());
      }
      const img = new Image();
      img.src = url(i);
      await img.decode();
      return img;
    };

    const order: number[] = [0];
    for (let i = 8; i < count; i += 8) order.push(i);
    order.push(count - 1);
    for (let i = 1; i < count; i++) if (i % 8 !== 0 && i !== count - 1) order.push(i);

    let next = 0;
    const pump = async () => {
      while (!cancelled && next < order.length) {
        const i = order[next++];
        try {
          frames[i] = await decode(i);
          dirty = true;
        } catch {
          /* skip a frame that failed; neighbours cover it */
        }
      }
    };
    for (let k = 0; k < 6; k++) void pump();

    const nearest = (i: number) => {
      for (let d = 0; d < count; d++) {
        if (i - d >= 0 && frames[i - d]) return i - d;
        if (i + d < count && frames[i + d]) return i + d;
      }
      return -1;
    };

    // Edge fade into the page colour, rendered once per size.
    const edge = document.createElement("canvas");
    const paintEdge = () => {
      edge.width = el.width;
      edge.height = el.height;
      const g = edge.getContext("2d")!;
      const { width: w, height: h } = edge;
      const band = (x0: number, y0: number, x1: number, y1: number, rx: number, ry: number, rw: number, rh: number) => {
        const grad = g.createLinearGradient(x0, y0, x1, y1);
        grad.addColorStop(0, background);
        grad.addColorStop(1, `${background}00`);
        g.fillStyle = grad;
        g.fillRect(rx, ry, rw, rh);
      };
      band(0, 0, w * 0.16, 0, 0, 0, w * 0.16, h);
      band(w, 0, w * 0.84, 0, w * 0.84, 0, w * 0.16, h);
      band(0, 0, 0, h * 0.06, 0, 0, w, h * 0.06);
      band(0, h, 0, h * 0.92, 0, h * 0.92, w, h * 0.08);
    };

    const resize = () => {
      const r = el.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      el.width = Math.max(1, Math.round(r.width * dpr));
      el.height = Math.max(1, Math.round(r.height * dpr));
      paintEdge();
      dirty = true;
    };
    const ro = new ResizeObserver(resize);
    ro.observe(el);
    resize();

    const place = (f: Frame) => {
      const fw = f.width;
      const fh = f.height;
      const s = Math.max(el.width / fw, el.height / fh);
      return [(el.width - fw * s) / 2, (el.height - fh * s) / 2, fw * s, fh * s] as const;
    };

    let drawn = -1;
    let reported = -1;
    const draw = () => {
      const p = Math.min(1, Math.max(0, progress.current ?? 0));
      const f = p * (count - 1);
      if (!dirty && Math.abs(f - drawn) < 0.01) return;
      const i0 = Math.floor(f);
      const a = nearest(i0);
      if (a < 0) return;
      ctx.globalAlpha = 1;
      ctx.fillStyle = background;
      ctx.fillRect(0, 0, el.width, el.height);
      ctx.drawImage(frames[a]!, ...place(frames[a]!));
      // Blend toward the next frame for sub-frame motion.
      const t = f - i0;
      const b = i0 + 1;
      if (a === i0 && t > 0.02 && b < count && frames[b]) {
        ctx.globalAlpha = t;
        ctx.drawImage(frames[b]!, ...place(frames[b]!));
        ctx.globalAlpha = 1;
      }
      ctx.drawImage(edge, 0, 0);
      drawn = f;
      dirty = false;
      if (onFrame && Math.abs(p - reported) > 0.002) {
        reported = p;
        onFrame(p);
      }
    };
    gsap.ticker.add(draw);

    return () => {
      cancelled = true;
      gsap.ticker.remove(draw);
      ro.disconnect();
      frames.forEach((fr) => fr && "close" in fr && fr.close());
    };
  }, [manifest, progress, onFrame, background]);

  return <canvas ref={canvas} role="img" aria-label={label} className={className} />;
}
