"use client";

/* eslint-disable @next/next/no-img-element -- images come from the API server */
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import Spinner from "@/components/Spinner";
import {
  api,
  mediaUrl,
  type ChatMessage,
  type ChatResponse,
  type Generation,
  type OutfitSuggestion,
} from "@/lib/api";
import { useSourceFile } from "@/lib/photo";

type Turn = { message: ChatMessage; response?: ChatResponse };

const STARTERS = [
  "What should I wear to a wedding?",
  "Outfit ideas for a mehndi night",
  "I have a tech job interview next week",
  "What's trending this autumn?",
];

export default function StylistPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => bottom.current?.scrollIntoView({ behavior: "smooth" }), [turns, busy]);

  async function send(text: string) {
    const content = text.trim();
    if (!content || busy) return;
    const history = [...turns.map((t) => t.message), { role: "user" as const, content }];
    setTurns((t) => [...t, { message: { role: "user", content } }]);
    setInput("");
    setBusy(true);
    setError(null);
    try {
      const res = await api.chat(history);
      setTurns((t) => [...t, { message: { role: "assistant", content: res.reply }, response: res }]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <div>
        <h1 className="text-2xl font-black tracking-tight">AI Stylist</h1>
        <p className="text-sm text-zinc-500">
          Ask for advice, then try any suggestion on your own photo in one click.
        </p>
      </div>

      <div className="card min-h-[24rem] space-y-4 p-5">
        {turns.length === 0 && (
          <div className="flex flex-col items-center gap-3 py-10 text-center text-sm text-zinc-500">
            <p>Tell me the occasion and I&apos;ll style you.</p>
            <div className="flex flex-wrap justify-center gap-1.5">
              {STARTERS.map((s) => (
                <button key={s} className="chip hover:bg-brand-100" onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {turns.map((t, i) =>
          t.message.role === "user" ? (
            <div key={i} className="flex justify-end">
              <p className="max-w-[80%] rounded-2xl rounded-br-sm bg-brand-600 px-4 py-2 text-sm text-white">
                {t.message.content}
              </p>
            </div>
          ) : (
            <div key={i} className="space-y-3">
              <p className="max-w-[90%] whitespace-pre-line rounded-2xl rounded-bl-sm bg-zinc-100 px-4 py-2 text-sm text-zinc-800">
                {t.message.content}
              </p>
              {t.response && t.response.suggestions.length > 0 && (
                <Suggestions suggestions={t.response.suggestions} />
              )}
              {t.response && t.response.sources.length > 0 && (
                <p className="text-xs text-zinc-400">Style notes: {t.response.sources.join(" · ")}</p>
              )}
            </div>
          ),
        )}
        {busy && (
          <p className="flex items-center gap-2 text-sm text-zinc-400">
            <Spinner /> Styling…
          </p>
        )}
        {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        <div ref={bottom} />
      </div>

      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask your stylist…"
          className="flex-1 rounded-xl border border-zinc-200 bg-white px-4 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
        />
        <button className="btn-primary" disabled={busy || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}

function Suggestions({ suggestions }: { suggestions: OutfitSuggestion[] }) {
  const sourceFile = useSourceFile();
  const [results, setResults] = useState<Record<number, Generation | "loading" | Error>>({});

  async function tryOn(i: number) {
    if (!sourceFile) return;
    setResults((r) => ({ ...r, [i]: "loading" }));
    try {
      const gen = await api.generate({ description: suggestions[i].description, sourceFile });
      setResults((r) => ({ ...r, [i]: gen }));
    } catch (e) {
      setResults((r) => ({ ...r, [i]: e as Error }));
    }
  }

  return (
    <div className="space-y-2">
      {sourceFile ? (
        <button className="btn-ghost text-xs" onClick={() => suggestions.forEach((_, i) => tryOn(i))}>
          ✨ Visualize all {suggestions.length} on me
        </button>
      ) : (
        <p className="text-xs text-zinc-500">
          <Link href="/" className="font-semibold text-brand-600 underline">
            Upload a photo in the Studio
          </Link>{" "}
          to see these on you.
        </p>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        {suggestions.map((s, i) => {
          const r = results[i];
          return (
            <div key={i} className="overflow-hidden rounded-xl border border-brand-100 bg-brand-50/40">
              {r && r !== "loading" && !(r instanceof Error) && (
                <img src={mediaUrl(r.image_url)} alt={s.title} className="aspect-[3/4] w-full object-cover" />
              )}
              {r === "loading" && (
                <div className="flex aspect-[3/4] items-center justify-center text-brand-500">
                  <Spinner className="h-8 w-8" />
                </div>
              )}
              <div className="space-y-2 p-3">
                <p className="text-sm font-semibold text-brand-700">{s.title}</p>
                <p className="text-xs text-zinc-600">{s.description}</p>
                {r instanceof Error && <p className="text-xs text-red-600">{r.message}</p>}
                <div className="flex gap-2">
                  {sourceFile ? (
                    <button
                      className="btn-ghost px-3 py-1.5 text-xs"
                      disabled={r === "loading"}
                      onClick={() => tryOn(i)}
                    >
                      {r && r !== "loading" && !(r instanceof Error) ? "Regenerate" : "Try it on"}
                    </button>
                  ) : null}
                  <Link
                    href={`/?prompt=${encodeURIComponent(s.description)}`}
                    className="btn-ghost px-3 py-1.5 text-xs"
                  >
                    Open in Studio
                  </Link>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
