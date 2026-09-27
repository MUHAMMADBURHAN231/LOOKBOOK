"use client";

/* eslint-disable @next/next/no-img-element -- signed, short-lived storage URLs */
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Glyph } from "@/components/ui/Glyph";
import { api } from "@/lib/api";
import type { Garment, StylistSession } from "@/lib/types";
import { useTryOnStore } from "@/stores/useTryOnStore";

type Turn = { role: "user" | "assistant"; content: string; garments: Garment[]; tools?: string[] };

const STARTERS = [
  "Mehndi on Saturday, outdoors in Lahore. I want colour.",
  "Job interview at a tech start-up next week",
  "Wedding guest, evening, black tie optional",
  "What's worth buying this autumn?",
];

const TOOL_LABELS: Record<string, string> = {
  search_catalog: "Searched catalogue",
  get_local_weather: "Checked weather",
  get_user_style_history: "Read your style history",
  search_style_notes: "Read style notes",
};

export default function StylistPage() {
  const router = useRouter();
  const setGarment = useTryOnStore((s) => s.setGarment);
  const [sessions, setSessions] = useState<StylistSession[]>([]);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.stylistSessions().then(setSessions).catch(() => {});
  }, []);
  useEffect(() => end.current?.scrollIntoView({ block: "end" }), [turns, busy]);

  async function open(id: string) {
    setSessionId(id);
    setError(null);
    try {
      const msgs = await api.stylistMessages(id);
      setTurns(msgs.map((m) => ({ role: m.role, content: m.content, garments: m.garments })));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function send(text: string) {
    const message = text.trim();
    if (!message || busy) return;
    setTurns((t) => [...t, { role: "user", content: message, garments: [] }]);
    setInput("");
    setBusy(true);
    setError(null);
    try {
      const reply = await api.chat(message, sessionId);
      if (!sessionId) {
        setSessionId(reply.session_id);
        api.stylistSessions().then(setSessions).catch(() => {});
      }
      setTurns((t) => [...t, { role: "assistant", content: reply.reply, garments: reply.recommended_garments, tools: reply.tools_used }]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function tryOn(g: Garment) {
    setGarment(g);
    router.push("/studio");
  }

  return (
    <div className="grid min-h-[calc(100dvh-3.5rem)] lg:min-h-dvh lg:grid-cols-[260px_1fr]">
      <aside className="hidden border-r border-line p-5 lg:block">
        <button
          className="btn-line w-full"
          onClick={() => {
            setSessionId(undefined);
            setTurns([]);
          }}
        >
          <Glyph name="plus" /> New conversation
        </button>
        <h2 className="label mt-8 mb-3 text-fog">History</h2>
        <ul className="space-y-1">
          {sessions.map((s) => (
            <li key={s.id}>
              <button
                onClick={() => open(s.id)}
                aria-current={s.id === sessionId ? "true" : undefined}
                className={`w-full truncate px-3 py-2 text-left text-sm ${s.id === sessionId ? "bg-ink-800 text-frost" : "text-mist hover:text-frost"}`}
              >
                {s.title}
              </button>
            </li>
          ))}
          {sessions.length === 0 && <li className="text-sm text-fog">Your conversations appear here.</li>}
        </ul>
      </aside>

      <section className="flex min-w-0 flex-col" aria-label="Conversation with your stylist">
        <div className="flex-1 space-y-8 overflow-y-auto p-5 md:p-10" aria-live="polite">
          {turns.length === 0 && (
            <div className="max-w-2xl">
              <h1 className="display-md text-3xl">Stylist</h1>
              <p className="mt-3 text-mist">
                Tell it the occasion, the place and the vibe. It checks the weather, searches the catalogue and remembers
                what you like.
              </p>
              <ul className="mt-8 space-y-2">
                {STARTERS.map((s) => (
                  <li key={s}>
                    <button onClick={() => send(s)} className="w-full border border-line px-4 py-3 text-left text-sm text-mist hover:border-mist hover:text-frost">
                      {s}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {turns.map((t, i) =>
            t.role === "user" ? (
              <p key={i} className="ml-auto max-w-xl border-r border-signal pr-4 text-right text-frost">
                {t.content}
              </p>
            ) : (
              <div key={i} className="max-w-3xl space-y-4">
                {t.tools && t.tools.length > 0 && (
                  <ul className="flex flex-wrap gap-1.5" aria-label="What the stylist did">
                    {[...new Set(t.tools)].map((tool) => (
                      <li key={tool} className="label border border-line px-2 py-1 text-fog">
                        {TOOL_LABELS[tool] ?? tool}
                      </li>
                    ))}
                  </ul>
                )}
                <p className="leading-relaxed whitespace-pre-line text-mist">{t.content}</p>
                {t.garments.length > 0 && (
                  <ul className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    {t.garments.map((g) => (
                      <li key={g.id} className="border border-line">
                        <img src={g.image_url} alt="" className="aspect-[3/4] w-full bg-bone object-contain" loading="lazy" />
                        <div className="space-y-2 p-3">
                          <p className="text-sm text-frost">{g.title}</p>
                          <button className="label text-signal hover:text-frost" onClick={() => tryOn(g)}>
                            Try it on
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ),
          )}
          {busy && (
            <p className="label text-mist" role="status">
              Thinking it through
            </p>
          )}
          {error && (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          )}
          <div ref={end} />
        </div>
        <form
          className="sticky bottom-16 flex gap-2 border-t border-line bg-ink-900 p-4 lg:bottom-0"
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
        >
          <label htmlFor="stylist-input" className="sr-only">
            Message your stylist
          </label>
          <input
            id="stylist-input"
            className="field flex-1"
            placeholder="Ask your stylist"
            maxLength={2000}
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
          <button className="btn-signal" disabled={busy || !input.trim()} aria-label="Send">
            <Glyph name="send" />
          </button>
        </form>
      </section>
    </div>
  );
}
