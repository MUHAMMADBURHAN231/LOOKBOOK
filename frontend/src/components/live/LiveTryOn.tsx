"use client";

/* eslint-disable @next/next/no-img-element -- garment images can be any URL */
import type { RealTimeClient } from "@decartai/sdk";
import { useEffect, useRef, useState } from "react";
import { Glyph } from "@/components/ui/Glyph";
import type { LiveToken } from "@/lib/types";

export type Selection = {
  label: string;
  /** Instruction for the realtime model, e.g. "Substitute the current top with ..." */
  prompt: string;
  /** Reference image: same-origin path, data URL or http(s) URL. */
  image?: string;
};

type Status = "idle" | "starting" | "connecting" | "live" | "preview" | "error";

export const promptFor = (description: string) =>
  `Substitute the current top with ${description.trim().replace(/\.$/, "")}`;

/**
 * Camera -> Decart realtime virtual try-on (WebRTC) -> re-rendered video. The token comes from our
 * API (the Decart key never reaches the browser). Without a server key it runs in preview mode:
 * your camera with the garment image laid over it, clearly labelled.
 */
export default function LiveTryOn({
  selection,
  getToken,
  compact = false,
}: {
  selection: Selection;
  getToken: () => Promise<LiveToken>;
  compact?: boolean;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const rt = useRef<RealTimeClient | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [queue, setQueue] = useState<number | null>(null);

  useEffect(
    () => () => {
      rt.current?.disconnect();
      stream.current?.getTracks().forEach((t) => t.stop());
    },
    [],
  );

  // Swap the garment on the live session when the selection changes.
  useEffect(() => {
    const client = rt.current;
    if (!client) return;
    (async () => {
      try {
        await client.set({ prompt: selection.prompt, enhance: false, image: selection.image ? await referenceImage(selection.image) : null });
      } catch (e) {
        setError((e as Error).message);
      }
    })();
  }, [selection]);

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

  async function start() {
    setError(null);
    setStatus("starting");
    try {
      const { createDecartClient, models } = await import("@decartai/sdk");
      const token = await getToken();
      const model = models.realtime(token.model as "lucy-vton-latest");
      stream.current = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: "user", frameRate: model.fps, width: model.width, height: model.height },
      });
      if (token.mock || !token.api_key) {
        attach(stream.current);
        setStatus("preview");
        return;
      }
      setStatus("connecting");
      const client = createDecartClient({ apiKey: token.api_key });
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
      });
      rt.current.on("error", (e) => fail(e.message));
      rt.current.on("sessionEnded", () => {
        stop();
        setError("The live session ended. Start again to keep trying things on.");
      });
      setStatus("live");
    } catch (e) {
      const err = e as Error;
      fail(err.name === "NotAllowedError" ? "Camera access was blocked. Allow the camera in your browser settings." : err.message);
    }
  }

  const running = status === "live" || status === "preview" || status === "connecting";

  return (
    <div className="space-y-3">
      <div className={`relative overflow-hidden border border-line bg-ink-950 ${compact ? "aspect-[4/3]" : "aspect-video"}`}>
        <video ref={video} playsInline muted className={`size-full object-cover ${status === "preview" ? "-scale-x-100" : ""}`} />
        {status === "preview" && selection.image && (
          <img
            src={selection.image}
            alt=""
            className="pointer-events-none absolute top-[38%] left-1/2 w-[24%] -translate-x-1/2 opacity-85 mix-blend-multiply"
          />
        )}
        {!running && (
          <div className="absolute inset-0 grid place-items-center p-6 text-center">
            <div className="max-w-sm space-y-4">
              <p className="display-md text-2xl text-frost">{status === "starting" ? "Opening camera" : "See it on you, live"}</p>
              {status !== "starting" && (
                <>
                  <p className="text-sm text-mist">Nothing from your camera is recorded. You can stop at any time.</p>
                  <button className="btn-signal" onClick={start}>
                    <Glyph name="camera" /> Start camera
                  </button>
                </>
              )}
            </div>
          </div>
        )}
        <div className="absolute top-3 left-3 flex gap-2">
          {status === "live" && <span className="label bg-signal px-2 py-1 text-ink-950">Live</span>}
          {status === "preview" && <span className="label bg-frost px-2 py-1 text-ink-950">Preview</span>}
          {status === "connecting" && (
            <span className="label bg-ink-800 px-2 py-1 text-frost">{queue ? `In queue ${queue}` : "Connecting"}</span>
          )}
        </div>
        {running && (
          <button onClick={stop} className="btn-line absolute top-3 right-3 min-h-9 bg-ink-950">
            Stop
          </button>
        )}
      </div>
      {status === "preview" && (
        <p className="text-sm text-mist">
          Preview mode: the server has no live try-on key yet, so the garment is overlaid rather than rendered by the model.
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

/** Same-origin and API-signed images are fetched here (Decart can't reach localhost); other public URLs
 *  and data URLs are passed through for Decart to fetch. SVGs are rasterized to PNG. */
async function referenceImage(src: string): Promise<Blob | string> {
  if (src.startsWith("data:")) return src;
  const url = new URL(src, location.href);
  const apiOrigin = new URL(process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").origin;
  if (url.origin !== location.origin && url.origin !== apiOrigin) return url.href;
  const blob = await (await fetch(url, { credentials: "omit" })).blob();
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
