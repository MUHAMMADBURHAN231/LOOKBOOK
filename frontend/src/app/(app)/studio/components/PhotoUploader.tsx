"use client";

/* eslint-disable @next/next/no-img-element -- signed, short-lived storage URLs */
import { useEffect, useRef, useState } from "react";
import { ConsentDialog } from "@/components/app/ConsentDialog";
import { Glyph } from "@/components/ui/Glyph";
import { usePresignedUpload } from "@/hooks/usePresignedUpload";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { Photo } from "@/lib/types";
import { useTryOnStore } from "@/stores/useTryOnStore";

export function PhotoUploader() {
  const { user } = useSession();
  const photo = useTryOnStore((s) => s.photo);
  const setPhoto = useTryOnStore((s) => s.setPhoto);
  const { upload, uploading, progress, error } = usePresignedUpload();
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [consentOpen, setConsentOpen] = useState(false);
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const pending = useRef<File | null>(null);

  useEffect(() => {
    api
      .photos()
      .then((list) => {
        setPhotos(list);
        if (!useTryOnStore.getState().photo && list[0]) setPhoto(list.find((p) => p.is_primary) ?? list[0]);
      })
      .catch(() => {});
  }, [setPhoto]);

  async function handle(file: File) {
    if (!user?.biometric_consent_granted) {
      pending.current = file;
      setConsentOpen(true);
      return;
    }
    const uploaded = await upload(file);
    if (uploaded) {
      setPhotos((p) => [uploaded, ...p]);
      setPhoto(uploaded);
    }
  }

  async function remove(p: Photo) {
    if (!confirm("Delete this photo and every try-on made from it?")) return;
    await api.deletePhoto(p.id).catch(() => {});
    setPhotos((list) => list.filter((x) => x.id !== p.id));
    if (photo?.id === p.id) setPhoto(null);
  }

  return (
    <section aria-labelledby="photo-heading" className="space-y-4">
      <div className="flex items-baseline justify-between">
        <h2 id="photo-heading" className="label text-mist">
          01 / Your photo
        </h2>
        {photos.length > 0 && <span className="label text-fog">{photos.length} saved</span>}
      </div>

      <button
        type="button"
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const f = e.dataTransfer.files[0];
          if (f) handle(f);
        }}
        disabled={uploading}
        className={`flex w-full items-center gap-4 border border-dashed px-4 py-4 text-left transition-colors ${
          dragging ? "border-signal bg-ink-800" : "border-line-strong hover:border-mist"
        }`}
      >
        <span className="grid size-10 shrink-0 place-items-center border border-line-strong text-mist">
          <Glyph name="upload" />
        </span>
        <span className="min-w-0">
          <span className="block text-sm text-frost">{uploading ? `Uploading ${progress}%` : "Upload a photo"}</span>
          <span className="block text-sm text-mist">Waist-up or full body, facing the camera. JPEG, PNG or WebP.</span>
        </span>
      </button>
      {uploading && (
        <div className="h-px bg-line" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
          <div className="h-px origin-left bg-signal transition-transform" style={{ transform: `scaleX(${progress / 100})` }} />
        </div>
      )}
      <input
        ref={input}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="sr-only"
        tabIndex={-1}
        onChange={(e) => {
          const f = e.target.files?.[0];
          e.target.value = "";
          if (f) handle(f);
        }}
      />
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}

      {photos.length > 0 && (
        <ul className="grid grid-cols-4 gap-2" aria-label="Your photos">
          {photos.map((p) => (
            <li key={p.id} className="group relative">
              <button
                type="button"
                onClick={() => setPhoto(p)}
                aria-pressed={photo?.id === p.id}
                className={`block aspect-[3/4] w-full overflow-hidden border ${
                  photo?.id === p.id ? "border-signal" : "border-line hover:border-mist"
                }`}
              >
                <img src={p.url} alt="Your uploaded photo" className="size-full object-cover" />
              </button>
              <button
                type="button"
                onClick={() => remove(p)}
                aria-label="Delete photo"
                className="absolute top-1 right-1 grid size-7 place-items-center bg-ink-950/90 text-mist opacity-0 group-hover:opacity-100 hover:text-danger focus-visible:opacity-100"
              >
                <Glyph name="close" className="size-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}

      <ConsentDialog
        open={consentOpen}
        onClose={() => setConsentOpen(false)}
        onGranted={() => {
          setConsentOpen(false);
          if (pending.current) {
            const f = pending.current;
            pending.current = null;
            // consent was just recorded; run the upload now
            upload(f).then((uploaded) => {
              if (uploaded) {
                setPhotos((p) => [uploaded, ...p]);
                setPhoto(uploaded);
              }
            });
          }
        }}
      />
    </section>
  );
}
