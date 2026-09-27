"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo } from "react";
import LiveTryOn, { promptFor } from "@/components/live/LiveTryOn";
import { api } from "@/lib/api";

/** Try-on window loaded by public/widget.js inside a store's page. The proxy only lets this page be
 *  framed by origins registered for the store key (CSP frame-ancestors). */
export default function EmbedPage() {
  return (
    <Suspense>
      <Embed />
    </Suspense>
  );
}

function Embed() {
  const params = useSearchParams();
  const key = params.get("key") ?? "";
  const host = params.get("host") ?? "";
  const name = params.get("name") || "this piece";
  const description = params.get("garment") || name;
  const image = params.get("image") || undefined;
  const selection = useMemo(() => ({ label: name, prompt: promptFor(description), image }), [name, description, image]);
  const getToken = useCallback(() => api.widgetToken(key, host), [key, host]);

  // Key presses inside the iframe don't reach the store page, so forward Escape to the widget.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") window.parent.postMessage({ type: "lookbook:close" }, "*");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <main id="main" className="flex min-h-dvh flex-col gap-4 bg-ink-900 p-5">
      <div className="flex items-baseline justify-between gap-3">
        <h1 className="truncate text-base text-frost">Try on: {name}</h1>
        <span className="label shrink-0 text-fog">
          by LOOK<span className="text-signal">/</span>BOOK
        </span>
      </div>
      <LiveTryOn selection={selection} getToken={getToken} compact />
    </main>
  );
}
