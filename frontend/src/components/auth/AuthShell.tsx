"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { Wordmark } from "@/components/ui/Wordmark";

/** Split layout for sign-in flows: a slow, warm-neutral Vanta fog on the left (static under reduced
 *  motion or without WebGL), the form on the right. */
export function AuthShell({ title, lead, children }: { title: string; lead: string; children: React.ReactNode }) {
  const fog = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!fog.current || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let effect: { destroy: () => void } | undefined;
    let cancelled = false;
    import("vanta/dist/vanta.fog.min")
      .then(({ default: FOG }) => {
        if (cancelled || !fog.current) return;
        effect = FOG({
          el: fog.current,
          THREE,
          mouseControls: false,
          touchControls: false,
          gyroControls: false,
          highlightColor: 0xf2e6de,
          midtoneColor: 0xe3d6cb,
          lowlightColor: 0xece9e4,
          baseColor: 0xf8f7f5,
          blurFactor: 0.62,
          speed: 0.55,
          zoom: 0.7,
        });
      })
      .catch(() => {
        /* no WebGL: the solid panel remains */
      });
    return () => {
      cancelled = true;
      effect?.destroy();
    };
  }, []);

  return (
    <div className="grid min-h-dvh lg:grid-cols-[1.1fr_1fr]">
      <aside ref={fog} className="relative hidden overflow-hidden bg-ink-950 lg:block" aria-hidden="true">
        <div className="absolute inset-0 z-10 flex flex-col justify-between p-10">
          <Wordmark />
          <p className="display-md max-w-[16ch] text-[clamp(2rem,3.4vw,3.2rem)] text-frost">
            Your photo stays yours. Encrypted, never trained on, deleted on schedule.
          </p>
        </div>
      </aside>
      <main id="main" className="flex items-center justify-center px-5 py-16 md:px-12">
        <div className="w-full max-w-md">
          <div className="mb-10 lg:hidden">
            <Wordmark />
          </div>
          <h1 className="display-md text-[2.4rem] text-frost">{title}</h1>
          <p className="mt-3 text-mist">{lead}</p>
          <div className="mt-10">{children}</div>
        </div>
      </main>
    </div>
  );
}
