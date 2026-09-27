"use client";

/* eslint-disable @next/next/no-img-element -- signed, short-lived storage URLs */
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Glyph } from "@/components/ui/Glyph";
import { useWardrobeStore } from "@/stores/useWardrobeStore";

export default function WardrobePage() {
  const { looks, error, load, remove } = useWardrobeStore();
  const [filter, setFilter] = useState("");

  useEffect(() => {
    load();
  }, [load]);

  const collections = useMemo(() => [...new Set((looks ?? []).map((l) => l.collection).filter(Boolean))].sort(), [looks]);
  const shown = (looks ?? []).filter((l) => !filter || l.collection === filter);

  return (
    <div className="space-y-8 p-5 md:p-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="display-md text-3xl">Wardrobe</h1>
          <p className="mt-2 text-sm text-mist">Every look you saved, grouped into collections.</p>
        </div>
        {collections.length > 0 && (
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by collection">
            {["", ...collections].map((c) => (
              <button
                key={c || "all"}
                onClick={() => setFilter(c)}
                aria-pressed={filter === c}
                className={`label border px-3 py-2 ${filter === c ? "border-frost bg-frost text-ink-950" : "border-line text-mist hover:text-frost"}`}
              >
                {c || "All"}
              </button>
            ))}
          </div>
        )}
      </div>

      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}

      {looks === null ? (
        <ul className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => (
            <li key={i} className="aspect-[3/4] animate-pulse bg-ink-850" />
          ))}
        </ul>
      ) : looks.length === 0 ? (
        <div className="border border-line p-10">
          <p className="text-frost">Nothing saved yet.</p>
          <p className="mt-2 text-sm text-mist">Generate a look in the studio and save the ones you like.</p>
          <Link href="/studio" className="btn-signal mt-6">
            Open studio <Glyph name="arrow" className="arrow-nudge size-4" />
          </Link>
        </div>
      ) : (
        <ul className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
          {shown.map((look) => (
            <li key={look.id} className="border border-line">
              {look.image_url ? (
                <img src={look.image_url} alt={look.title} className="aspect-[3/4] w-full object-cover" loading="lazy" />
              ) : (
                <div className="grid aspect-[3/4] place-items-center text-sm text-fog">Image expired</div>
              )}
              <div className="space-y-3 p-3">
                <p className="line-clamp-2 text-sm text-frost">{look.title}</p>
                <div className="flex items-center justify-between">
                  <span className="label text-fog">{look.collection || "Unsorted"}</span>
                  <div className="flex">
                    {look.image_url && (
                      <a className="btn-quiet min-h-9 px-2" href={look.image_url} download aria-label={`Download ${look.title}`}>
                        <Glyph name="download" />
                      </a>
                    )}
                    <button
                      className="btn-quiet min-h-9 px-2 hover:text-danger"
                      aria-label={`Delete ${look.title}`}
                      onClick={() => confirm("Remove this look from your wardrobe?") && remove(look.id)}
                    >
                      <Glyph name="trash" />
                    </button>
                  </div>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
