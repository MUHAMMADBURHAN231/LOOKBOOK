"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Glyph } from "@/components/ui/Glyph";
import { useTryOnSocket } from "@/hooks/useTryOnSocket";
import { api } from "@/lib/api";
import type { Meta } from "@/lib/types";
import { useTryOnStore } from "@/stores/useTryOnStore";
import { useWardrobeStore } from "@/stores/useWardrobeStore";
import { CanvasViewport } from "./components/CanvasViewport";
import { PhotoUploader } from "./components/PhotoUploader";
import { WardrobeDrawer } from "./components/WardrobeDrawer";

export default function StudioPage() {
  const s = useTryOnStore();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [enhanceFace, setEnhanceFace] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  useTryOnSocket(s.currentTaskId);

  useEffect(() => {
    api.meta().then(setMeta).catch(() => {});
  }, []);

  const running = s.status === "QUEUED" || s.status === "PROCESSING";
  const ready = Boolean(s.photo && (s.garment || s.prompt.trim().length >= 3));

  async function generate() {
    if (!s.photo) return;
    setSubmitting(true);
    s.reset();
    try {
      const task = await api.execute({
        user_photo_id: s.photo.id,
        garment_id: s.garment?.id,
        prompt: s.garment ? undefined : s.prompt.trim(),
        enhance_face: enhanceFace,
      });
      s.setTask(task);
    } catch (e) {
      s.setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="grid gap-8 p-5 md:p-8 xl:grid-cols-[400px_1fr]">
      <div className="space-y-10">
        <div>
          <h1 className="display-md text-3xl">Studio</h1>
          <p className="mt-2 text-sm text-mist">Photo, outfit, generate. Results arrive live as each stage finishes.</p>
        </div>
        {meta?.mock && (
          <p className="border border-line-strong px-4 py-3 text-sm text-mist">
            <span className="label mr-2 text-signal">Demo mode</span>
            No AI provider keys are configured, so results are simulated. Add keys on the server for real try-ons.
          </p>
        )}
        <PhotoUploader />
        <WardrobeDrawer />
        <div className="space-y-4">
          <label className="flex items-center gap-3 text-sm text-mist">
            <input
              type="checkbox"
              className="size-4 accent-[var(--color-signal)]"
              checked={enhanceFace}
              onChange={(e) => setEnhanceFace(e.target.checked)}
            />
            Restore face details after fitting
          </label>
          <button className="btn-signal w-full" disabled={!ready || running || submitting} onClick={generate}>
            {running || submitting ? "Generating" : "Generate look"} <Glyph name="arrow" className="arrow-nudge size-4" />
          </button>
          {s.errorMessage && (
            <p role="alert" className="border border-danger/40 px-4 py-3 text-sm text-danger">
              {s.errorMessage}
            </p>
          )}
        </div>
      </div>

      <div className="space-y-5">
        <CanvasViewport />
        {s.status === "COMPLETED" && s.task && <ResultActions />}
        {s.task?.outfit_spec && s.status === "COMPLETED" && (
          <dl className="mx-auto grid max-w-xl grid-cols-[7rem_1fr] border border-line font-mono text-sm">
            {s.task.outfit_spec.garments.map((g, i) => (
              <div key={i} className="contents">
                <dt className="label border-b border-line px-4 py-2.5 text-fog">{g.category.replace("_", " ")}</dt>
                <dd className="border-b border-line px-4 py-2.5 text-frost">
                  {[g.fit, g.color, g.material, g.type].filter(Boolean).join(" ")}
                </dd>
              </div>
            ))}
            {s.task.outfit_spec.scene && (
              <>
                <dt className="label px-4 py-2.5 text-fog">scene</dt>
                <dd className="px-4 py-2.5 text-frost">{s.task.outfit_spec.scene}</dd>
              </>
            )}
          </dl>
        )}
      </div>
    </div>
  );
}

function ResultActions() {
  const task = useTryOnStore((s) => s.task)!;
  const save = useWardrobeStore((s) => s.save);
  const [collection, setCollection] = useState("");
  const [state, setState] = useState<"idle" | "saving" | "saved" | "error">("idle");

  async function onSave() {
    setState("saving");
    try {
      await save(task.task_id, collection);
      setState("saved");
    } catch {
      setState("error");
    }
  }

  return (
    <div className="mx-auto flex max-w-xl flex-wrap items-center gap-2">
      <label htmlFor="collection" className="sr-only">
        Collection
      </label>
      <input
        id="collection"
        className="field min-w-0 flex-1"
        placeholder="Collection (optional)"
        maxLength={60}
        value={collection}
        onChange={(e) => setCollection(e.target.value)}
      />
      <button className="btn-line" onClick={onSave} disabled={state === "saving" || state === "saved"}>
        {state === "saved" ? "Saved" : state === "error" ? "Retry save" : "Save to wardrobe"}
      </button>
      {task.result_url && (
        <a className="btn-quiet" href={task.result_url} download={`lookbook-${task.task_id}.webp`}>
          <Glyph name="download" /> Download
        </a>
      )}
      {state === "saved" && (
        <Link href="/wardrobe" className="label w-full pt-1 text-mist hover:text-frost">
          View wardrobe
        </Link>
      )}
    </div>
  );
}
