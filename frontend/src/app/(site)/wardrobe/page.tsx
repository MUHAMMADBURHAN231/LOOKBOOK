"use client";

/* eslint-disable @next/next/no-img-element -- images come from the API server */
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import Spinner from "@/components/Spinner";
import { api, mediaUrl, type Look } from "@/lib/api";
import { setSourceFile } from "@/lib/photo";

export default function WardrobePage() {
  const [looks, setLooks] = useState<Look[] | null>(null);
  const [filter, setFilter] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .looks()
      .then(setLooks)
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(load, [load]);

  const collections = useMemo(
    () => [...new Set((looks ?? []).map((l) => l.collection).filter(Boolean))].sort(),
    [looks],
  );
  const shown = (looks ?? []).filter((l) => !filter || l.collection === filter);

  async function remove(id: string) {
    await api.deleteLook(id).catch((e: Error) => setError(e.message));
    load();
  }

  async function wipe() {
    if (!confirm("Delete ALL your photos, generated images and saved looks? This can't be undone.")) return;
    try {
      await api.deleteAllData();
      setSourceFile(null);
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function share(look: Look) {
    const url = mediaUrl(look.image_url);
    try {
      if (navigator.share) await navigator.share({ title: look.title, url });
      else {
        await navigator.clipboard.writeText(url);
        alert("Image link copied to clipboard");
      }
    } catch {}
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-black tracking-tight">Wardrobe</h1>
          <p className="text-sm text-zinc-500">Your saved looks, organised into collections.</p>
        </div>
        <button className="btn-ghost text-xs text-red-600" onClick={wipe}>
          Delete all my data
        </button>
      </div>

      {collections.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {["", ...collections].map((c) => (
            <button
              key={c || "all"}
              onClick={() => setFilter(c)}
              className={`chip ${filter === c ? "bg-brand-600 text-white" : "hover:bg-brand-100"}`}
            >
              {c || "All"}
            </button>
          ))}
        </div>
      )}

      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      {looks === null && !error && (
        <div className="flex justify-center py-20 text-brand-500">
          <Spinner className="h-8 w-8" />
        </div>
      )}

      {looks?.length === 0 && (
        <div className="card p-10 text-center text-sm text-zinc-500">
          No saved looks yet.{" "}
          <Link href="/" className="font-semibold text-brand-600 underline">
            Create one in the Studio
          </Link>
          .
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
        {shown.map((look) => (
          <article key={look.id} className="card overflow-hidden">
            <img src={mediaUrl(look.image_url)} alt={look.title} className="aspect-[3/4] w-full object-cover" />
            <div className="space-y-2 p-3">
              <h2 className="line-clamp-2 text-sm font-semibold">{look.title}</h2>
              <div className="flex flex-wrap gap-1">
                {look.collection && <span className="chip">{look.collection}</span>}
                {look.spec.style_tags.map((t) => (
                  <span key={t} className="rounded-full bg-zinc-100 px-2 py-0.5 text-[10px] text-zinc-500">
                    {t}
                  </span>
                ))}
              </div>
              <div className="flex gap-1.5">
                <Link
                  href={`/?prompt=${encodeURIComponent(look.description)}`}
                  className="btn-ghost flex-1 px-2 py-1 text-xs"
                >
                  Remix
                </Link>
                <button className="btn-ghost px-2 py-1 text-xs" onClick={() => share(look)}>
                  Share
                </button>
                <button className="btn-ghost px-2 py-1 text-xs text-red-600" onClick={() => remove(look.id)}>
                  ✕
                </button>
              </div>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
