"use client";

import { Suspense, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import LiveTryOn, { promptFor } from "@/components/LiveTryOn";

/** Minimal try-on view loaded in an iframe by public/widget.js on retailer sites. */
export default function EmbedPage() {
  return (
    <Suspense>
      <Embed />
    </Suspense>
  );
}

function Embed() {
  const params = useSearchParams();
  const name = params.get("name") || "this item";
  const description = params.get("garment") || name;
  const image = params.get("image") || undefined;

  // Key presses inside the iframe don't reach the host page, so forward Escape to widget.js.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") window.parent.postMessage({ type: "lookbook:close" }, "*");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="flex h-dvh flex-col gap-3 bg-white p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h1 className="truncate text-base font-bold">Try on: {name}</h1>
        <span className="shrink-0 text-xs text-zinc-400">
          Powered by <span className="font-black text-brand-600">LOOKBOOK</span>
        </span>
      </div>
      <div className="flex-1">
        <LiveTryOn compact initial={{ label: name, prompt: promptFor(description), image }} />
      </div>
    </div>
  );
}
