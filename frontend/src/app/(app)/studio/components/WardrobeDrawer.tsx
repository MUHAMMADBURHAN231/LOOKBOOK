"use client";

/* eslint-disable @next/next/no-img-element -- signed, short-lived storage URLs */
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Garment } from "@/lib/types";
import { useTryOnStore } from "@/stores/useTryOnStore";

const CATEGORIES = [
  ["", "All"],
  ["upper_body", "Tops"],
  ["outerwear", "Outerwear"],
  ["lower_body", "Bottoms"],
  ["dresses", "Full length"],
] as const;

const EXAMPLES = [
  "a sleek black turtleneck with a tailored navy blazer, in front of a Ferrari",
  "a traditional sherwani with gold embroidery",
  "an oversized hoodie with cargo pants and Jordan 4s",
  "a full astronaut suit, standing on the moon",
];

/** Pick a catalogue piece (semantic search over pgvector) or describe any outfit in words. */
export function WardrobeDrawer() {
  const [tab, setTab] = useState<"catalog" | "describe">("catalog");
  const garment = useTryOnStore((s) => s.garment);
  const prompt = useTryOnStore((s) => s.prompt);
  const setGarment = useTryOnStore((s) => s.setGarment);
  const setPrompt = useTryOnStore((s) => s.setPrompt);
  const [items, setItems] = useState<Garment[] | null>(null);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stale = false; // ignore responses that arrive after a newer search started
    const t = setTimeout(() => {
      api
        .garments(query.trim() || undefined, category || undefined)
        .then((g) => {
          if (stale) return;
          setItems(g);
          setError(null);
        })
        .catch((e) => !stale && setError((e as Error).message));
    }, query ? 300 : 0); // debounce typed searches
    return () => {
      stale = true;
      clearTimeout(t);
    };
  }, [query, category]);

  return (
    <section aria-labelledby="garment-heading" className="space-y-4">
      <h2 id="garment-heading" className="label text-mist">
        02 / The outfit
      </h2>
      <div role="tablist" aria-label="Choose how to pick an outfit" className="grid grid-cols-2 border border-line">
        {(["catalog", "describe"] as const).map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={`label py-3 transition-colors ${tab === t ? "bg-frost text-ink-950" : "text-mist hover:text-frost"}`}
          >
            {t === "catalog" ? "Catalogue" : "Describe it"}
          </button>
        ))}
      </div>

      {tab === "catalog" ? (
        <div className="space-y-3" role="tabpanel">
          <label className="sr-only" htmlFor="garment-search">
            Search the catalogue
          </label>
          <input
            id="garment-search"
            className="field"
            placeholder="Search: warm coat for a gallery opening"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div className="flex flex-wrap gap-1.5">
            {CATEGORIES.map(([value, label]) => (
              <button
                key={value}
                onClick={() => setCategory(value)}
                aria-pressed={category === value}
                className={`label border px-2.5 py-1.5 ${category === value ? "border-frost text-frost" : "border-line text-mist hover:text-frost"}`}
              >
                {label}
              </button>
            ))}
          </div>
          {error && <p className="text-sm text-danger">{error}</p>}
          <ul className="grid grid-cols-3 gap-2">
            {items === null
              ? Array.from({ length: 6 }, (_, i) => <li key={i} className="aspect-[3/4] animate-pulse bg-ink-850" />)
              : items.map((g) => (
                  <li key={g.id}>
                    <button
                      onClick={() => setGarment(g)}
                      aria-pressed={garment?.id === g.id}
                      className={`block w-full border text-left ${garment?.id === g.id ? "border-signal" : "border-line hover:border-mist"}`}
                    >
                      <img src={g.image_url} alt="" className="aspect-[3/4] w-full bg-bone object-contain" loading="lazy" />
                      <span className="block truncate px-2 py-1.5 text-xs text-frost">{g.title}</span>
                    </button>
                  </li>
                ))}
          </ul>
          {items?.length === 0 && <p className="text-sm text-mist">Nothing matches that yet. Try describing it instead.</p>}
        </div>
      ) : (
        <div className="space-y-3" role="tabpanel">
          <label className="sr-only" htmlFor="outfit-prompt">
            Describe the outfit
          </label>
          <textarea
            id="outfit-prompt"
            rows={4}
            maxLength={1000}
            className="field resize-none leading-relaxed"
            placeholder="a cream linen suit with a white shirt and tan loafers, on a beach at sunset"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />
          <ul className="space-y-1">
            {EXAMPLES.map((ex) => (
              <li key={ex}>
                <button onClick={() => setPrompt(ex)} className="w-full py-1.5 text-left text-sm text-mist hover:text-frost">
                  <span className="text-fog">+</span> {ex}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
