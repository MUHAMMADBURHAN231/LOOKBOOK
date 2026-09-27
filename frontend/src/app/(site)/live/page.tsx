"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import LiveTryOn, { promptFor, type Selection } from "@/components/LiveTryOn";
import { garmentById } from "@/lib/catalog";

export default function LivePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black tracking-tight">Live Try-On</h1>
        <p className="text-sm text-zinc-500">
          Your camera, real clothes, real time. Move around and the garment moves with you.
        </p>
      </div>
      <Suspense>
        <LiveFromParams />
      </Suspense>
    </div>
  );
}

function LiveFromParams() {
  const params = useSearchParams();
  const garment = garmentById(params.get("garment"));
  const prompt = params.get("prompt");
  const initial: Selection | undefined = garment
    ? { label: garment.name, prompt: garment.prompt, image: garment.image }
    : prompt
      ? { label: prompt, prompt: promptFor(prompt) }
      : undefined;
  return <LiveTryOn initial={initial} />;
}
