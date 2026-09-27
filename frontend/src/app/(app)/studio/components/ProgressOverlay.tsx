"use client";

import { useTryOnStore } from "@/stores/useTryOnStore";

const LABELS: Record<string, string> = {
  QUEUED: "Waiting for a worker",
  INIT: "Waiting for a worker",
  PREPARING_INPUTS: "Preparing your photo",
  SAFETY_CHECK: "Checking the photo",
  PREPROCESSING_POSE: "Reading your pose",
  PREPROCESSING_MASK: "Masking the garment region",
  GENERATING_GARMENT: "Drafting the garment",
  DIFFUSION_WARP: "Fitting the garment",
  POSTPROCESSING_FACE: "Restoring your face",
  UPLOADING: "Saving the result",
  RETRYING: "The model is busy, retrying",
};

/** Live stage + progress for the running job, fed by the WebSocket through the store. */
export function ProgressOverlay() {
  const status = useTryOnStore((s) => s.status);
  const stage = useTryOnStore((s) => s.stage);
  const progress = useTryOnStore((s) => s.progress);
  if (status !== "QUEUED" && status !== "PROCESSING") return null;
  return (
    <div className="absolute inset-x-0 bottom-0 border-t border-line bg-ink-950 p-5" role="status" aria-live="polite">
      <div className="label flex items-center justify-between text-mist">
        <span className="text-frost">{LABELS[stage] ?? stage.replaceAll("_", " ").toLowerCase()}</span>
        <span className="tabular-nums">{String(progress).padStart(3, "0")}%</span>
      </div>
      <div className="mt-3 h-px bg-line">
        <div
          className="h-px origin-left bg-signal transition-transform duration-500 ease-[var(--ease-out)]"
          style={{ transform: `scaleX(${progress / 100})` }}
        />
      </div>
    </div>
  );
}
