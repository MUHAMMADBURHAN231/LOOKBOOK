"use client";

import gsap from "gsap";
import { useEffect, useRef } from "react";

/* A video scrubbed by scroll, drawn frame by frame to a canvas (the technique Apple uses on its
   product pages). A <video> element can't seek smoothly on every browser, so the video is shipped
   as numbered WebP frames instead, built by scripts/build_scroll_video.py: motion-interpolated and
   re-timed so equal scroll gives equal on-screen change.

   What keeps it smooth:
   - The playhead eases toward the scroll position (frame-rate independent), on top of Lenis's own
     smoothing, so motion ramps up and settles like a camera instead of following each wheel tick.
   - The position is fractional and neighbouring frames (already close together) are blended, so
     motion is continuous between frames.
   - Every frame is available from the start as a small proxy (a few sprite sheets, under 1 MB), so
     the picture never freezes waiting for a download or decode; it is briefly soft instead, which
     reads as motion blur while scrolling fast.
   - Full frames stay compressed in memory and are decoded off the main thread just ahead of the
     playhead, at the frames it will actually land on given its speed (the screen shows at most one
     per refresh, so at speed most frames are skipped). Holding every frame decoded would take over
     a gigabyte and stall phones.
   - Drawing runs on GSAP's ticker right after Lenis updates the scroll, in the same frame, and the
     soft edge is painted in the canvas, so the browser doesn't re-mask a layer every frame.

   Full frames come in more than one width; the smallest that is sharp at the canvas's pixel size
   is used. */

export type ScrollVideoManifest = {
  count: number;
  /** The film's backdrop colour, measured from its frame borders. */
  backdrop?: string;
  /** First and last frames, for the instant first paint and the reduced-motion page. */
  poster?: { start: string; end: string };
  pad: number;
  width: number;
  height: number;
  /** Positions (0..1) where each look is complete. */
  marks: number[];
  /** One frame set per width; pattern has {i} for the 1-based, zero-padded frame number. */
  tiers: { width: number; pattern: string }[];
  /** Every frame, small, in sprite sheets of cols x rows, row by row; pattern has {i} (1-based). */
  proxy?: {
    pattern: string;
    width: number;
    height: number;
    cols: number;
    rows: number;
    sheets: number;
  };
};

type Frame = ImageBitmap | HTMLImageElement;

type Props = {
  manifest: ScrollVideoManifest;
  /** Target position, 0..1 across the sequence; read every frame through a ref. */
  progress: React.RefObject<number>;
  /** Called with the position (0..1) drawn, when it changes, for syncing captions. */
  onFrame?: (position: number) => void;
  /** Loading progress (0..1) toward being able to draw the whole timeline, and whether it can. */
  onLoad?: (fraction: number, ready: boolean) => void;
  className?: string;
  label: string;
  /** Colour the frame's edges fade into. White suits a canvas blended with mix-blend-mode: multiply. */
  background?: string;
  /** How quickly the playhead catches up with the scroll, per second. Higher is tighter. */
  follow?: number;
  /** Which edges fade into `background`: all four (a framed clip) or only the bottom (a
   *  full-bleed film that hands over to the page below). */
  edges?: "all" | "bottom";
  /** Horizontal anchor (0..1) when the frame is cropped, like CSS object-position, so a phone crop
   *  stays on the subject and a poster with the same object-position lines up exactly. */
  focusX?: number;
  /** On a portrait canvas, draw the frame this tall (fraction of the canvas height), resting on
   *  the bottom, with `fill` above it: room for text on a phone. Omit to always cover. */
  portraitHeight?: number;
  /** Colour behind and above the frame (the film's own backdrop). Defaults to `background`. */
  fill?: string;
};

const LOOK_AHEAD = 8;
const KEEP_DECODED = 24;
const MAX_DECODING = 4;
const MAX_FETCHING = 6;

async function decodeBlob(b: Blob): Promise<Frame> {
  if ("createImageBitmap" in window) return createImageBitmap(b);
  const img = new Image();
  img.src = URL.createObjectURL(b);
  await img.decode();
  return img;
}

function release(f: Frame) {
  if ("close" in f) f.close();
  else URL.revokeObjectURL(f.src);
}

export default function ScrollVideo({
  manifest,
  progress,
  onFrame,
  onLoad,
  className = "",
  label,
  background = "#FFFFFF",
  follow = 5,
  edges = "all",
  focusX = 0.5,
  portraitHeight,
  fill,
}: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const el = canvas.current;
    const ctx = el?.getContext("2d", { alpha: false });
    if (!el || !ctx) return;
    const reduced = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    const { count, pad, proxy } = manifest;
    let cancelled = false;
    let dirty = true;

    // Edge fade into the page colour, rendered once per size.
    const edge = document.createElement("canvas");
    const paintEdge = () => {
      edge.width = el.width;
      edge.height = el.height;
      const g = edge.getContext("2d")!;
      const { width: w, height: h } = edge;
      const band = (
        x0: number,
        y0: number,
        x1: number,
        y1: number,
        rx: number,
        ry: number,
        rw: number,
        rh: number,
      ) => {
        const grad = g.createLinearGradient(x0, y0, x1, y1);
        grad.addColorStop(0, background);
        grad.addColorStop(1, `${background}00`);
        g.fillStyle = grad;
        g.fillRect(rx, ry, rw, rh);
      };
      if (edges === "all") {
        band(0, 0, w * 0.16, 0, 0, 0, w * 0.16, h);
        band(w, 0, w * 0.84, 0, w * 0.84, 0, w * 0.16, h);
        band(0, 0, 0, h * 0.06, 0, 0, w, h * 0.06);
      }
      band(0, h, 0, h * 0.92, 0, h * 0.92, w, h * 0.08);
      if (portraitHeight && h > w) {
        // Blend the top of a portrait-fitted frame into the fill above it.
        const top = h * (1 - portraitHeight);
        const c = fill ?? background;
        const grad = g.createLinearGradient(0, top, 0, top + h * 0.06);
        grad.addColorStop(0, c);
        grad.addColorStop(1, `${c}00`);
        g.fillStyle = grad;
        g.fillRect(0, top, w, h * 0.06);
      }
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

    // The smallest full-frame set that is at least ~90% of the canvas height in pixels.
    const tiers = [...manifest.tiers].sort((a, b) => a.width - b.width);
    const tier =
      tiers.find(
        (t) => (t.width * manifest.height) / manifest.width >= el.height * 0.9,
      ) ?? tiers[tiers.length - 1];
    const url = (i: number) =>
      tier.pattern.replace("{i}", String(i + 1).padStart(pad, "0"));

    // Playhead in frames (-1 until the first tick), its speed in frames per tick, and direction.
    let shown = -1;
    let velocity = 0;
    let direction = 1;
    const at = () => Math.max(0, Math.floor(shown));

    // --- Proxies: every frame, small. Ready to scrub once they're in.
    const sheets: (Frame | null)[] = new Array(proxy?.sheets ?? 0).fill(null);
    let sheetsDone = 0;
    const report = () => {
      if (cancelled) return;
      if (proxy)
        onLoad?.(sheetsDone / proxy.sheets, sheetsDone >= proxy.sheets);
      else onLoad?.(decoded.size > 0 ? 1 : 0, decoded.size > 0);
    };
    sheets.forEach((_, s) => {
      fetch(proxy!.pattern.replace("{i}", String(s + 1)))
        .then((r) =>
          r.ok ? r.blob() : Promise.reject(new Error(String(r.status))),
        )
        .then(decodeBlob)
        .then((f) => {
          if (cancelled) return release(f);
          sheets[s] = f;
          dirty = true;
        })
        .catch(() => {})
        .finally(() => {
          sheetsDone++;
          report();
        });
    });

    // --- Full frames: downloaded nearest the playhead first, kept compressed.
    const blobs: (Blob | null)[] = new Array(count).fill(null);
    const fetching = new Set<number>();
    const failed = new Set<number>();
    const nextFetch = () => {
      const c = at();
      for (let d = 0; d < count; d++) {
        for (const i of [c + d * direction, c - d * direction]) {
          if (
            i >= 0 &&
            i < count &&
            !blobs[i] &&
            !fetching.has(i) &&
            !failed.has(i)
          )
            return i;
        }
      }
      return -1;
    };
    const pumpFetch = () => {
      while (!cancelled && fetching.size < MAX_FETCHING) {
        const i = nextFetch();
        if (i < 0) return;
        fetching.add(i);
        fetch(url(i))
          .then((r) =>
            r.ok ? r.blob() : Promise.reject(new Error(String(r.status))),
          )
          .then((b) => {
            blobs[i] = b;
          })
          .catch(() => failed.add(i))
          .finally(() => {
            fetching.delete(i);
            pumpFetch();
          });
      }
    };

    // --- Decoding: the frames the playhead will land on next, given its speed.
    const decoded = new Map<number, Frame>();
    const decoding = new Set<number>();
    const wanted = () => {
      const c = at();
      const speed = Math.abs(velocity);
      const step = Math.max(1, Math.round(speed));
      const list = [c, c + 1];
      for (let k = 1; k <= LOOK_AHEAD; k++) list.push(c + direction * step * k);
      if (speed < 1.5) list.push(c - direction, c + 2 * direction);
      return list.filter(
        (i, n) => i >= 0 && i < count && list.indexOf(i) === n,
      );
    };
    const pumpDecode = () => {
      const want = wanted();
      for (const i of want) {
        if (decoding.size >= MAX_DECODING) break;
        if (decoded.has(i) || decoding.has(i) || !blobs[i]) continue;
        decoding.add(i);
        decodeBlob(blobs[i]!)
          .then((f) => {
            if (cancelled) return release(f);
            decoded.set(i, f);
            dirty = true;
            if (!proxy && decoded.size === 1) report();
          })
          .catch(() => {})
          .finally(() => decoding.delete(i));
      }
      if (decoded.size > KEEP_DECODED) {
        const c = at();
        const far = [...decoded.keys()]
          .filter((i) => !want.includes(i))
          .sort((a, b) => Math.abs(b - c) - Math.abs(a - c));
        for (const i of far.slice(0, decoded.size - KEEP_DECODED)) {
          release(decoded.get(i)!);
          decoded.delete(i);
        }
      }
    };

    // --- Drawing.
    // Cover the canvas; when the frame is wider than the canvas, keep focusX in view. On a
    // portrait canvas with portraitHeight, the frame is shorter than the canvas and rests on the
    // bottom, with `fill` above it.
    const portrait = () => !!portraitHeight && el.height > el.width;
    const place = (w: number, h: number) => {
      const s = portrait()
        ? (el.height * portraitHeight!) / h
        : Math.max(el.width / w, el.height / h);
      // Same rule as CSS object-position: focusX of the frame lines up with focusX of the canvas.
      const x = (el.width - w * s) * focusX;
      const y = portrait() ? el.height - h * s : (el.height - h * s) / 2;
      return [x, y, w * s, h * s] as const;
    };
    const drawFull = (f: Frame) =>
      ctx.drawImage(f, ...place(f.width, f.height));
    const per = proxy ? proxy.cols * proxy.rows : 1;
    const drawProxy = (i: number) => {
      const sheet = proxy && sheets[Math.floor(i / per)];
      if (!sheet) return false;
      const k = i % per;
      const { width: pw, height: ph, cols } = proxy;
      ctx.imageSmoothingQuality = "high";
      ctx.drawImage(
        sheet,
        (k % cols) * pw,
        Math.floor(k / cols) * ph,
        pw,
        ph,
        ...place(pw, ph),
      );
      return true;
    };

    let drawn = -1;
    let reported = -1;
    const tick = (_time: number, deltaMs: number) => {
      // The target is a whole frame, so the playhead always comes to rest on one frame rather than
      // a blend of two (a double edge on a moving garment); it still glides between frames.
      // NaN-proof: a NaN here would stick in the eased playhead for good.
      const raw = progress.current ?? 0;
      const target = Math.round(
        (Number.isFinite(raw) ? Math.min(1, Math.max(0, raw)) : 0) *
          (count - 1),
      );
      const before = shown;
      if (shown < 0 || !Number.isFinite(shown) || reduced) {
        shown = target;
      } else if (shown !== target) {
        const k = 1 - Math.exp(-(Math.min(deltaMs, 100) / 1000) * follow);
        shown += (target - shown) * k;
        if (Math.abs(target - shown) < 0.002) shown = target;
      }
      velocity = before < 0 ? 0 : shown - before;
      if (velocity) direction = velocity > 0 ? 1 : -1;
      pumpFetch();
      pumpDecode();

      if (!dirty && Math.abs(shown - drawn) < 0.004) return;
      const i0 = Math.floor(shown);
      const t = shown - i0;
      ctx.globalAlpha = 1;
      ctx.fillStyle = fill ?? background;
      ctx.fillRect(0, 0, el.width, el.height);
      const full = decoded.get(i0);
      const next = decoded.get(i0 + 1);
      if (full) {
        drawFull(full);
        // Blend toward the next frame for sub-frame motion.
        if (t > 0.02 && next) {
          ctx.globalAlpha = t;
          drawFull(next);
        }
      } else if (next && t > 0.5) {
        drawFull(next);
      } else if (drawProxy(i0)) {
        if (t > 0.02 && i0 + 1 < count) {
          ctx.globalAlpha = t;
          drawProxy(i0 + 1);
        }
      } else {
        return;
      }
      ctx.globalAlpha = 1;
      ctx.drawImage(edge, 0, 0);
      drawn = shown;
      dirty = false;
      const p = count > 1 ? shown / (count - 1) : 0;
      if (onFrame && Math.abs(p - reported) > 0.0005) {
        reported = p;
        onFrame(p);
      }
    };
    gsap.ticker.add(tick);

    return () => {
      cancelled = true;
      gsap.ticker.remove(tick);
      ro.disconnect();
      decoded.forEach(release);
      decoded.clear();
      sheets.forEach((f) => f && release(f));
    };
  }, [
    manifest,
    progress,
    onFrame,
    onLoad,
    background,
    follow,
    edges,
    focusX,
    portraitHeight,
    fill,
  ]);

  return (
    <canvas ref={canvas} role="img" aria-label={label} className={className} />
  );
}
