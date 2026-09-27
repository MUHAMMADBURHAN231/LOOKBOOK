"use client";

/* eslint-disable @next/next/no-img-element -- garment images can be any URL */
import type { RealTimeClient } from "@decartai/sdk";
import { useEffect, useRef, useState } from "react";
import Spinner from "@/components/Spinner";
import { api, mediaUrl } from "@/lib/api";
import { CATALOG, LIVE_MODEL } from "@/lib/catalog";

export type Selection = {
  label: string;
  /** Instruction for the realtime model, e.g. "Substitute the current top with ..." */
  prompt: string;
  /** Reference image: same-origin path, data URL or http(s) URL. */
  image?: string;
};

type Status = "idle" | "starting" | "connecting" | "live" | "preview" | "error";

const toSelection = (g: (typeof CATALOG)[number]): Selection => ({
  label: g.name,
  prompt: g.prompt,
  image: g.image,
});

/** Turns a free-text garment description into a realtime try-on instruction. */
export const promptFor = (description: string) =>
  `Substitute the current top with ${description.trim().replace(/\.$/, "")}`;

export default function LiveTryOn({
  initial,
  compact = false,
}: {
  initial?: Selection;
  compact?: boolean;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const rt = useRef<RealTimeClient | null>(null);

  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [queue, setQueue] = useState<number | null>(null);
  const [selection, setSelection] = useState<Selection>(initial ?? toSelection(CATALOG[0]));
  const [custom, setCustom] = useState("");

  // Release the camera and the realtime session when leaving the page.
  useEffect(
    () => () => {
      rt.current?.disconnect();
      stream.current?.getTracks().forEach((t) => t.stop());
    },
    [],
  );

  async function start() {
    setError(null);
    setStatus("starting");
    try {
      const { createDecartClient, models } = await import("@decartai/sdk");
      const model = models.realtime(LIVE_MODEL);
      stream.current = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: "user", frameRate: model.fps, width: model.width, height: model.height },
      });

      const tokenRes = await fetch("/api/live/token");
      const token = await tokenRes.json();
      if (!tokenRes.ok) throw new Error(token.error ?? "Could not start a live session");

      if (token.mock) {
        attach(stream.current);
        setStatus("preview");
        return;
      }

      setStatus("connecting");
      const client = createDecartClient({ apiKey: token.apiKey });
      rt.current = await client.realtime.connect(stream.current, {
        model,
        mirror: true,
        onRemoteStream: attach,
        initialState: {
          prompt: { text: selection.prompt, enhance: false },
          ...(selection.image ? { image: await referenceImage(selection.image) } : {}),
        },
      });
      rt.current.on("queuePosition", (q) => setQueue(q.position));
      rt.current.on("connectionChange", (state) => {
        if (state === "generating" || state === "connected") {
          setQueue(null);
          setStatus("live");
        }
        if (state === "disconnected") setStatus((s) => (s === "live" ? "idle" : s));
      });
      rt.current.on("error", (e) => fail(e.message));
      rt.current.on("sessionEnded", () => {
        setError("Session ended. Press start to try more.");
        stop();
      });
      setStatus("live");
    } catch (e) {
      const err = e as Error;
      fail(
        err.name === "NotAllowedError"
          ? "Camera access was blocked. Allow the camera in your browser to try clothes on live."
          : err.message,
      );
    }
  }

  function attach(s: MediaStream) {
    if (video.current) {
      video.current.srcObject = s;
      video.current.play().catch(() => {});
    }
  }

  function stop() {
    rt.current?.disconnect();
    rt.current = null;
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    if (video.current) video.current.srcObject = null;
    setQueue(null);
    setStatus((s) => (s === "error" ? s : "idle"));
  }

  function fail(message: string) {
    stop();
    setError(message);
    setStatus("error");
  }

  async function choose(next: Selection) {
    setSelection(next);
    if (!rt.current) return;
    try {
      await rt.current.set({
        prompt: next.prompt,
        enhance: false,
        image: next.image ? await referenceImage(next.image) : null,
      });
    } catch (e) {
      setError((e as Error).message);
    }
  }

  function onUpload(file: File) {
    const reader = new FileReader();
    reader.onload = () =>
      choose({
        label: file.name,
        prompt: promptFor(custom || "the garment shown in the reference image"),
        image: reader.result as string,
      });
    reader.readAsDataURL(file);
  }

  const running = status === "live" || status === "preview" || status === "connecting";
  const busy = status === "starting" || status === "connecting";

  return (
    <div className={compact ? "flex h-full flex-col gap-3" : "grid gap-6 lg:grid-cols-[1fr_20rem]"}>
      <div className="space-y-3">
        <div className="relative aspect-video overflow-hidden rounded-2xl bg-zinc-900">
          <video
            ref={video}
            playsInline
            muted
            className={`h-full w-full object-cover ${status === "preview" ? "-scale-x-100" : ""}`}
          />

          {status === "preview" && selection.image && (
            <img
              src={selection.image}
              alt=""
              className="pointer-events-none absolute top-[38%] left-1/2 w-[26%] -translate-x-1/2 opacity-80 mix-blend-multiply"
            />
          )}

          {!running && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 p-6 text-center text-white">
              {busy ? (
                <Spinner className="h-8 w-8" />
              ) : (
                <>
                  <p className="text-lg font-semibold">See it on you, live.</p>
                  <p className="max-w-sm text-sm text-zinc-300">
                    Turn on your camera and the {selection.label} appears on you in real time as you move.
                  </p>
                  <button className="btn-primary" onClick={start}>
                    📷 Start live try-on
                  </button>
                </>
              )}
            </div>
          )}

          <div className="absolute top-3 left-3 flex gap-2">
            {status === "live" && <Badge className="bg-red-600">● LIVE</Badge>}
            {status === "preview" && <Badge className="bg-amber-500">Preview mode</Badge>}
            {status === "connecting" && (
              <Badge className="bg-zinc-700">
                {queue ? `In queue · #${queue}` : "Connecting…"}
              </Badge>
            )}
          </div>
          {running && (
            <button onClick={stop} className="btn-ghost absolute top-3 right-3 px-3 py-1.5 text-xs">
              Stop
            </button>
          )}
        </div>

        {status === "preview" && (
          <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
            Preview mode: no DECART_API_KEY is set, so the garment is overlaid instead of rendered by
            the live AI model. Add a key in frontend/.env.local for real-time try-on.
          </p>
        )}
        {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        {!compact && running && <Snapshot video={video} selection={selection} mirrored={status === "preview"} />}
      </div>

      {!compact && (
        <aside className="space-y-4">
          <div>
            <h2 className="mb-2 text-sm font-semibold text-zinc-700">Pick a piece</h2>
            <div className="grid grid-cols-3 gap-2">
              {CATALOG.map((g) => (
                <button
                  key={g.id}
                  onClick={() => choose(toSelection(g))}
                  className={`overflow-hidden rounded-xl border-2 bg-white transition ${
                    selection.label === g.name ? "border-brand-500" : "border-transparent hover:border-brand-200"
                  }`}
                  title={g.name}
                >
                  <img src={g.image} alt={g.name} className="aspect-[3/4] w-full object-contain p-1" />
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-2">
            <h2 className="text-sm font-semibold text-zinc-700">…or describe anything</h2>
            <form
              className="flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (custom.trim()) choose({ label: custom.trim(), prompt: promptFor(custom) });
              }}
            >
              <input
                value={custom}
                onChange={(e) => setCustom(e.target.value)}
                placeholder="a green bomber jacket"
                className="min-w-0 flex-1 rounded-xl border border-zinc-200 px-3 text-sm outline-none focus:border-brand-500"
              />
              <button className="btn-ghost px-3 text-xs" disabled={!custom.trim()}>
                Apply
              </button>
            </form>
            <label className="btn-ghost w-full cursor-pointer text-xs">
              ⬆ Upload a garment photo
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && onUpload(e.target.files[0])}
              />
            </label>
          </div>
          <p className="text-xs text-zinc-400">
            Now wearing: <span className="font-medium text-zinc-600">{selection.label}</span>
          </p>
        </aside>
      )}
    </div>
  );
}

function Badge({ children, className }: { children: React.ReactNode; className: string }) {
  return <span className={`rounded-full px-2.5 py-1 text-xs font-bold text-white ${className}`}>{children}</span>;
}

/** Capture the current frame; optionally re-render it at photo quality through the backend. */
function Snapshot({
  video,
  selection,
  mirrored,
}: {
  video: React.RefObject<HTMLVideoElement | null>;
  selection: Selection;
  mirrored: boolean;
}) {
  const [consent, setConsent] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function capture(): Promise<Blob | null> {
    const v = video.current;
    if (!v || !v.videoWidth) return Promise.resolve(null);
    const canvas = document.createElement("canvas");
    canvas.width = v.videoWidth;
    canvas.height = v.videoHeight;
    const ctx = canvas.getContext("2d")!;
    if (mirrored) {
      ctx.translate(canvas.width, 0);
      ctx.scale(-1, 1);
    }
    ctx.drawImage(v, 0, 0);
    return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.92));
  }

  async function download() {
    const blob = await capture();
    if (!blob) return;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "lookbook-snapshot.jpg";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  async function render() {
    const blob = await capture();
    if (!blob) return;
    setRendering(true);
    setError(null);
    try {
      const description = selection.prompt.replace(/^Substitute the current (top|outfit) with /i, "");
      const gen = await api.generate({
        description: `Wearing ${description}`,
        photo: new File([blob], "snapshot.jpg", { type: "image/jpeg" }),
      });
      setResult(mediaUrl(gen.image_url));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRendering(false);
    }
  }

  return (
    <div className="card space-y-3 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <button className="btn-ghost text-xs" onClick={download}>
          📸 Save snapshot
        </button>
        <button className="btn-ghost text-xs" onClick={render} disabled={!consent || rendering}>
          {rendering ? <Spinner /> : "✨"} Photo-quality render
        </button>
        <label className="flex items-center gap-1.5 text-xs text-zinc-500">
          <input
            type="checkbox"
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
            className="accent-brand-600"
          />
          OK to upload this frame for rendering
        </label>
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
      {result && <img src={result} alt="Rendered look" className="max-h-96 rounded-xl" />}
    </div>
  );
}

/**
 * Same-origin images are fetched here (SVGs rasterized to PNG), since Decart can't reach e.g.
 * localhost. Data URLs and other sites' public image URLs are passed through for Decart to fetch.
 */
async function referenceImage(src: string): Promise<Blob | string> {
  if (src.startsWith("data:")) return src;
  if (/^https?:\/\//.test(src) && new URL(src).origin !== location.origin) return src;
  const blob = await (await fetch(src)).blob();
  if (blob.type !== "image/svg+xml") return blob;

  const img = new Image();
  img.src = URL.createObjectURL(blob);
  await img.decode();
  const canvas = document.createElement("canvas");
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  canvas.getContext("2d")!.drawImage(img, 0, 0);
  URL.revokeObjectURL(img.src);
  return new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("Could not prepare image"))), "image/png"),
  );
}
