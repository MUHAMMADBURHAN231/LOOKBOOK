"use client";

/*
 * Adapted from React Bits "DecryptedText" by David Haz (https://github.com/DavidHDev/react-bits).
 * MIT + Commons Clause License Condition v1.0. Copyright (c) 2026 David Haz.
 *
 * Changes for LOOKBOOK: no `motion` dependency, screen readers always get the real text (the
 * original exposed the scrambled string), and it stays static under prefers-reduced-motion.
 */
import { useCallback, useEffect, useRef, useState } from "react";

type Props = {
  text: string;
  speed?: number;
  maxIterations?: number;
  characters?: string;
  animateOn?: "view" | "hover";
  className?: string;
};

const DEFAULT_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/[]_-+";

export default function DecryptedText({
  text,
  speed = 40,
  maxIterations = 12,
  characters = DEFAULT_CHARS,
  animateOn = "hover",
  className = "",
}: Props) {
  const [display, setDisplay] = useState(text);
  const ref = useRef<HTMLSpanElement>(null);
  const timer = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  const played = useRef(false);

  const run = useCallback(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    clearInterval(timer.current);
    let i = 0;
    timer.current = setInterval(() => {
      i++;
      // Reveal left to right while the unrevealed tail keeps shuffling.
      const revealed = Math.floor((i / maxIterations) * text.length);
      setDisplay(
        text
          .split("")
          .map((ch, idx) => (ch === " " || idx < revealed ? ch : characters[Math.floor(Math.random() * characters.length)]))
          .join(""),
      );
      if (i >= maxIterations) {
        clearInterval(timer.current);
        setDisplay(text);
      }
    }, speed);
  }, [text, speed, maxIterations, characters]);

  useEffect(() => {
    if (animateOn !== "view" || !ref.current) return;
    const io = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting && !played.current) {
        played.current = true;
        run();
      }
    });
    io.observe(ref.current);
    return () => io.disconnect();
  }, [animateOn, run]);

  useEffect(() => () => clearInterval(timer.current), []);

  return (
    <span ref={ref} className={`relative inline-block ${className}`} onMouseEnter={animateOn === "hover" ? run : undefined}>
      <span className="sr-only">{text}</span>
      <span aria-hidden="true" className="tabular-nums">
        {display}
      </span>
    </span>
  );
}
