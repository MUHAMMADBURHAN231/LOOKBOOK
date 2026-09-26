"use client";

/* eslint-disable @next/next/no-img-element -- images come from the API server */
import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import SpecView from "@/components/SpecView";
import Spinner from "@/components/Spinner";
import { api, mediaUrl, type Generation, type Health, type Pipeline } from "@/lib/api";
import { setSourceFile, sourceFileFromUrl, useSourceFile } from "@/lib/photo";

const EXAMPLES = [
  "Wearing a sleek black turtleneck with a tailored navy blazer, aviator sunglasses, standing in front of a Ferrari",
  "Traditional Pakistani sherwani with gold embroidery",
  "Full astronaut suit on the moon",
  "Streetwear — oversized hoodie, cargo pants, Jordan 4s",
];

export default function StudioPage() {
  return (
    <Suspense>
      <Studio />
    </Suspense>
  );
}

function Studio() {
  const params = useSearchParams();
  const storedSource = useSourceFile();
  const fileInput = useRef<HTMLInputElement>(null);

  const [health, setHealth] = useState<Health | null>(null);
  const [photo, setPhoto] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [consent, setConsent] = useState(false);
  const [description, setDescription] = useState(params.get("prompt") ?? "");
  const [pipeline, setPipeline] = useState<Pipeline>("edit");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Generation | null>(null);
  const [showOriginal, setShowOriginal] = useState(false);

  useEffect(() => {
    api
      .health()
      .then((h) => {
        setHealth(h);
        setPipeline(h.default_pipeline);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  function choosePhoto(file: File | null) {
    if (preview) URL.revokeObjectURL(preview);
    setPhoto(file);
    setPreview(file ? URL.createObjectURL(file) : null);
  }

  const shownPhoto = preview ?? (storedSource ? mediaUrl(`/media/${storedSource}`) : null);
  const canGenerate = !!shownPhoto && consent && description.trim().length >= 3 && !busy;

  async function onGenerate() {
    setBusy(true);
    setError(null);
    try {
      const gen = await api.generate({
        description,
        pipeline,
        ...(photo ? { photo } : { sourceFile: storedSource ?? undefined }),
      });
      setResult(gen);
      setShowOriginal(false);
      setSourceFile(sourceFileFromUrl(gen.source_url));
      choosePhoto(null); // later generations reuse the stored copy
    } catch (e) {
      const msg = (e as Error).message;
      if (msg.includes("Upload a photo")) setSourceFile(null); // stored photo expired
      setError(msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <section className="text-center">
        <h1 className="text-3xl font-black tracking-tight sm:text-4xl">
          Describe any outfit. <span className="text-brand-600">See yourself in it.</span>
        </h1>
        <p className="mt-2 text-zinc-500">
          Upload a photo, type what you want to wear in plain English, and LOOKBOOK dresses you up.
        </p>
        {health?.mock && (
          <p className="mx-auto mt-3 max-w-xl rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
            Mock mode: no GEMINI_API_KEY is set, so results are placeholders. Add a key in
            backend/.env for real generations.
          </p>
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Input */}
        <section className="card space-y-5 p-5">
          <div>
            <h2 className="mb-2 text-sm font-semibold text-zinc-700">1 · Your photo</h2>
            <button
              type="button"
              onClick={() => fileInput.current?.click()}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                const f = e.dataTransfer.files[0];
                if (f) choosePhoto(f);
              }}
              className="flex aspect-[3/4] max-h-96 w-full items-center justify-center overflow-hidden rounded-xl border-2 border-dashed border-brand-200 bg-brand-50/50 transition hover:border-brand-500"
            >
              {shownPhoto ? (
                <img src={shownPhoto} alt="Your photo" className="h-full w-full object-contain" />
              ) : (
                <span className="px-6 text-sm text-zinc-500">
                  Click or drop a photo here
                  <br />
                  <span className="text-xs text-zinc-400">
                    Full body or waist-up, facing the camera, good lighting
                  </span>
                </span>
              )}
            </button>
            <input
              ref={fileInput}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && choosePhoto(e.target.files[0])}
            />
            <label className="mt-3 flex items-start gap-2 text-xs text-zinc-600">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                className="mt-0.5 accent-brand-600"
              />
              I consent to LOOKBOOK processing this photo to generate images of me. It is stored
              privately, never used for training, and deleted after{" "}
              {health?.retention_days ?? 30} days.
            </label>
          </div>

          <div>
            <h2 className="mb-2 text-sm font-semibold text-zinc-700">2 · Describe the outfit</h2>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              maxLength={1000}
              placeholder="e.g. a cream linen suit with a white shirt and tan loafers, on a beach at sunset"
              className="w-full resize-none rounded-xl border border-zinc-200 p-3 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
            />
            <div className="mt-2 flex flex-wrap gap-1.5">
              {EXAMPLES.map((ex) => (
                <button key={ex} type="button" className="chip hover:bg-brand-100" onClick={() => setDescription(ex)}>
                  {ex.length > 42 ? `${ex.slice(0, 40)}…` : ex}
                </button>
              ))}
            </div>
          </div>

          {health?.vton_available && (
            <div className="flex items-center gap-3 text-xs text-zinc-600">
              <span className="font-semibold">Engine</span>
              {(["edit", "vton"] as const).map((p) => (
                <label key={p} className="flex items-center gap-1">
                  <input
                    type="radio"
                    name="pipeline"
                    checked={pipeline === p}
                    onChange={() => setPipeline(p)}
                    className="accent-brand-600"
                  />
                  {p === "edit" ? "Fast (Gemini, supports scenes)" : "Try-on (IDM-VTON)"}
                </label>
              ))}
            </div>
          )}

          <button className="btn-primary w-full" disabled={!canGenerate} onClick={onGenerate}>
            {busy ? (
              <>
                <Spinner /> Designing your look…
              </>
            ) : (
              "✨ Generate my look"
            )}
          </button>
          {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        </section>

        {/* Result */}
        <section className="card flex flex-col p-5">
          <h2 className="mb-2 text-sm font-semibold text-zinc-700">3 · Your look</h2>
          {result ? (
            <ResultView
              key={result.id}
              result={result}
              showOriginal={showOriginal}
              onToggle={() => setShowOriginal((v) => !v)}
            />
          ) : (
            <div className="flex flex-1 items-center justify-center rounded-xl bg-zinc-50 p-10 text-center text-sm text-zinc-400">
              {busy ? <Spinner className="h-8 w-8 text-brand-500" /> : "Your generated look will appear here."}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function ResultView({
  result,
  showOriginal,
  onToggle,
}: {
  result: Generation;
  showOriginal: boolean;
  onToggle: () => void;
}) {
  const [collection, setCollection] = useState("");
  const [saved, setSaved] = useState<"idle" | "saving" | "saved" | "error">("idle");

  async function save() {
    setSaved("saving");
    try {
      await api.saveLook(result.id, "", collection);
      setSaved("saved");
    } catch {
      setSaved("error");
    }
  }

  return (
    <div className="space-y-4">
      <div className="relative overflow-hidden rounded-xl bg-zinc-100">
        <img
          src={mediaUrl(showOriginal ? result.source_url : result.image_url)}
          alt={showOriginal ? "Original photo" : result.spec.summary}
          className="max-h-[32rem] w-full object-contain"
        />
        <button onClick={onToggle} className="btn-ghost absolute top-3 right-3 px-3 py-1.5 text-xs">
          {showOriginal ? "Show look" : "Show original"}
        </button>
      </div>
      <p className="text-xs text-zinc-400">
        {(result.elapsed_ms / 1000).toFixed(1)}s · {result.pipeline === "edit" ? "Gemini edit" : "IDM-VTON"}
        {result.mock && " · mock"}
      </p>
      <SpecView spec={result.spec} />
      <div className="flex gap-2 border-t border-zinc-100 pt-4">
        <input
          value={collection}
          onChange={(e) => setCollection(e.target.value)}
          placeholder="Collection (optional)"
          maxLength={60}
          className="flex-1 rounded-xl border border-zinc-200 px-3 text-sm outline-none focus:border-brand-500"
        />
        <button className="btn-ghost" onClick={save} disabled={saved === "saving" || saved === "saved"}>
          {saved === "saved" ? "✓ Saved" : saved === "error" ? "Retry save" : "Save to wardrobe"}
        </button>
      </div>
    </div>
  );
}
