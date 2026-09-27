"use client";

/* eslint-disable @next/next/no-img-element -- signed, short-lived storage URLs */
import { useEffect, useState } from "react";
import LiveTryOn, { promptFor, type Selection } from "@/components/live/LiveTryOn";
import { api } from "@/lib/api";
import type { Garment } from "@/lib/types";

const toSelection = (g: Garment): Selection => ({ label: g.title, prompt: promptFor(g.description), image: g.image_url });

export default function LivePage() {
  const [garments, setGarments] = useState<Garment[]>([]);
  const [selection, setSelection] = useState<Selection>({ label: "a tailored navy blazer", prompt: promptFor("a tailored navy wool blazer") });
  const [custom, setCustom] = useState("");

  useEffect(() => {
    api
      .garments()
      .then((g) => {
        setGarments(g);
        if (g[0]) setSelection(toSelection(g[0]));
      })
      .catch(() => {});
  }, []);

  return (
    <div className="grid gap-8 p-5 md:p-8 xl:grid-cols-[1fr_340px]">
      <div className="space-y-4">
        <div>
          <h1 className="display-md text-3xl">Live try-on</h1>
          <p className="mt-2 text-sm text-mist">Your camera, re-rendered in real time with the piece on you. Move around.</p>
        </div>
        <LiveTryOn selection={selection} getToken={api.liveToken} />
        <p className="label text-fog">Now wearing: {selection.label}</p>
      </div>
      <aside className="space-y-6">
        <div>
          <h2 className="label mb-3 text-mist">Pick a piece</h2>
          <ul className="grid grid-cols-3 gap-2">
            {garments.map((g) => (
              <li key={g.id}>
                <button
                  onClick={() => setSelection(toSelection(g))}
                  aria-pressed={selection.label === g.title}
                  className={`block w-full border ${selection.label === g.title ? "border-signal" : "border-line hover:border-mist"}`}
                  title={g.title}
                >
                  <img src={g.image_url} alt={g.title} className="aspect-[3/4] w-full bg-bone object-contain" />
                </button>
              </li>
            ))}
          </ul>
        </div>
        <form
          className="space-y-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (custom.trim()) setSelection({ label: custom.trim(), prompt: promptFor(custom) });
          }}
        >
          <label htmlFor="live-custom" className="label text-mist">
            Or describe anything
          </label>
          <div className="flex gap-2">
            <input id="live-custom" className="field" placeholder="a green bomber jacket" value={custom} onChange={(e) => setCustom(e.target.value)} />
            <button className="btn-line" disabled={!custom.trim()}>
              Apply
            </button>
          </div>
        </form>
      </aside>
    </div>
  );
}
