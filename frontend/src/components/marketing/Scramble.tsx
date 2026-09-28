"use client";

import { useEffect, useRef, useState } from "react";

const GLYPHS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/_#<>";

/** Text that decodes into place: characters cycle through random glyphs and settle left to right
 *  whenever `text` changes (and on first appearance when `fromEmpty`). Screen readers get the
 *  final text immediately; under reduced motion it simply swaps. */
export function Scramble({
  text,
  className = "",
  duration = 700,
  fromEmpty = true,
}: {
  text: string;
  className?: string;
  duration?: number;
  fromEmpty?: boolean;
}) {
  const [out, setOut] = useState(fromEmpty ? "" : text);
  const prev = useRef(fromEmpty ? "" : text);

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const from = prev.current;
    prev.current = text;
    let raf = 0;
    if (reduced || from === text) {
      raf = requestAnimationFrame(() => setOut(text));
      return () => cancelAnimationFrame(raf);
    }
    const start = performance.now();
    const len = Math.max(from.length, text.length);
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      let s = "";
      for (let i = 0; i < len; i++) {
        const ch = text[i] ?? "";
        const settleAt = 0.35 + 0.65 * (i / Math.max(1, len));
        if (t >= settleAt || ch === " ") s += ch;
        else s += GLYPHS[Math.floor(Math.random() * GLYPHS.length)];
      }
      setOut(s);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [text, duration]);

  return (
    <span className={className}>
      <span className="sr-only">{text}</span>
      <span aria-hidden="true">{out || " "}</span>
    </span>
  );
}
