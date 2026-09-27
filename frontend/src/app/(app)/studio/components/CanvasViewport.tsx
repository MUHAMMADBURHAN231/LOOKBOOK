"use client";

/* eslint-disable @next/next/no-img-element -- signed, short-lived storage URLs */
import { useCallback, useRef, useState } from "react";
import { useTryOnStore } from "@/stores/useTryOnStore";
import { ProgressOverlay } from "./ProgressOverlay";

/**
 * Shows the photo, then the result with a before/after divider you can drag (or move with the
 * arrow keys). The divider is a clip-path over two stacked images, so it costs no re-layout.
 */
export function CanvasViewport() {
  const photo = useTryOnStore((s) => s.photo);
  const result = useTryOnStore((s) => s.resultImageUrl);
  const status = useTryOnStore((s) => s.status);
  const [split, setSplit] = useState(100);
  const box = useRef<HTMLDivElement>(null);

  const fromPointer = useCallback((clientX: number) => {
    const r = box.current?.getBoundingClientRect();
    if (r) setSplit(Math.max(0, Math.min(100, ((clientX - r.left) / r.width) * 100)));
  }, []);

  const showResult = status === "COMPLETED" && result;

  return (
    <div
      ref={box}
      className="relative mx-auto aspect-[3/4] max-h-[calc(100dvh-10rem)] w-full max-w-xl overflow-hidden border border-line bg-ink-950 select-none"
    >
      {!photo && (
        <div className="absolute inset-0 grid place-items-center p-10 text-center">
          <div>
            <p className="display-md text-2xl text-frost">Start with a photo</p>
            <p className="mt-3 text-sm text-mist">Upload one on the left, then pick or describe an outfit.</p>
          </div>
        </div>
      )}
      {photo && <img src={photo.url} alt="Your photo" className="absolute inset-0 size-full object-contain" draggable={false} />}
      {showResult && (
        <>
          <img
            src={result}
            alt="You wearing the generated outfit"
            className="absolute inset-0 size-full object-contain"
            style={{ clipPath: `inset(0 ${100 - split}% 0 0)` }}
            draggable={false}
          />
          <div
            role="slider"
            tabIndex={0}
            aria-label="Compare original and result"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(split)}
            aria-valuetext={`${Math.round(split)}% result`}
            onKeyDown={(e) => {
              if (e.key === "ArrowLeft") setSplit((s) => Math.max(0, s - 5));
              if (e.key === "ArrowRight") setSplit((s) => Math.min(100, s + 5));
            }}
            onPointerDown={(e) => {
              e.currentTarget.setPointerCapture(e.pointerId);
              fromPointer(e.clientX);
            }}
            onPointerMove={(e) => e.buttons === 1 && fromPointer(e.clientX)}
            className="absolute inset-y-0 w-10 -translate-x-1/2 cursor-ew-resize touch-none"
            style={{ left: `${split}%` }}
          >
            <div className="mx-auto h-full w-px bg-frost" />
            <div className="label absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-frost px-2 py-1 text-ink-950">
              Drag
            </div>
          </div>
          <span className="label absolute top-3 left-3 bg-ink-950 px-2 py-1 text-frost">Result</span>
          <span className="label absolute top-3 right-3 bg-ink-950 px-2 py-1 text-mist">Original</span>
        </>
      )}
      <ProgressOverlay />
    </div>
  );
}
