"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Field } from "@/components/ui/Field";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { SessionInfo } from "@/lib/types";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="grid gap-6 border-t border-line py-10 md:grid-cols-[16rem_1fr]">
      <h2 className="label pt-1 text-mist">{title}</h2>
      <div className="max-w-xl space-y-4">{children}</div>
    </section>
  );
}

export default function AccountPage() {
  const router = useRouter();
  const { user, refresh, setUser } = useSession();
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [pw, setPw] = useState({ current: "", next: "" });
  const [pwError, setPwError] = useState<string | null>(null);
  const [confirmText, setConfirmText] = useState("");

  useEffect(() => {
    api.sessions().then(setSessions).catch(() => {});
  }, []);

  if (!user) return null;

  const flash = (m: string) => {
    setMessage(m);
    setTimeout(() => setMessage(null), 4000);
  };

  async function withdrawConsent() {
    if (!confirm("Withdrawing consent deletes every photo and generated image now. Continue?")) return;
    await api.setConsent(false);
    await refresh();
    flash("Consent withdrawn. Your photos and results were deleted.");
  }

  async function exportData() {
    const data = await api.exportData();
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "lookbook-export.json";
    a.click();
    URL.revokeObjectURL(url);
  }

  async function changePassword(e: React.FormEvent) {
    e.preventDefault();
    setPwError(null);
    try {
      await api.changePassword({ current_password: pw.current, new_password: pw.next });
      setPw({ current: "", next: "" });
      flash("Password changed. Other devices were signed out.");
      setSessions(await api.sessions());
    } catch (err) {
      setPwError((err as Error).message);
    }
  }

  return (
    <div className="p-5 md:p-8">
      <h1 className="display-md text-3xl">Account</h1>
      <p className="mt-2 text-sm text-mist">{user.email}</p>
      <div role="status" aria-live="polite" className="min-h-8 pt-3 text-sm text-ok">
        {message}
      </div>

      <Section title="Photo consent">
        <p className="text-sm text-mist">
          {user.biometric_consent_granted
            ? "You've agreed to let LOOKBOOK process your photos for try-on. Withdrawing deletes every photo and result immediately."
            : "Consent is off. You'll be asked again before your next upload."}
        </p>
        {user.biometric_consent_granted && (
          <button className="btn-line" onClick={withdrawConsent}>
            Withdraw consent
          </button>
        )}
      </Section>

      <Section title="Signed-in devices">
        <ul className="divide-y divide-line border border-line">
          {sessions.map((s) => (
            <li key={s.id} className="flex items-center justify-between gap-4 px-4 py-3">
              <div className="min-w-0">
                <p className="truncate text-sm text-frost">{s.user_agent || "Unknown device"}</p>
                <p className="label text-fog">
                  {s.current ? "This device" : `Last seen ${new Date(s.last_seen_at).toLocaleString()}`}
                </p>
              </div>
              {!s.current && (
                <button
                  className="btn-quiet min-h-9"
                  onClick={async () => {
                    await api.revokeSession(s.id);
                    setSessions((list) => list.filter((x) => x.id !== s.id));
                  }}
                >
                  Sign out
                </button>
              )}
            </li>
          ))}
        </ul>
        <button
          className="btn-line"
          onClick={async () => {
            await api.logoutAll();
            setUser(null);
            router.replace("/login");
          }}
        >
          Sign out everywhere
        </button>
      </Section>

      <Section title="Password">
        <form onSubmit={changePassword} className="space-y-4">
          <Field label="Current password" type="password" autoComplete="current-password" value={pw.current} onChange={(e) => setPw({ ...pw, current: e.target.value })} />
          <Field label="New password" type="password" autoComplete="new-password" value={pw.next} onChange={(e) => setPw({ ...pw, next: e.target.value })} error={pwError} />
          <button className="btn-line" disabled={!pw.current || pw.next.length < 10}>
            Change password
          </button>
        </form>
      </Section>

      <Section title="Your data">
        <p className="text-sm text-mist">Download everything we hold about you, or delete your photos, looks and conversations.</p>
        <div className="flex flex-wrap gap-3">
          <button className="btn-line" onClick={exportData}>
            Download my data
          </button>
          <button
            className="btn-line"
            onClick={async () => {
              if (!confirm("Delete all photos, try-ons, saved looks and stylist conversations?")) return;
              await api.deleteData();
              flash("All your data was deleted. Your account stays open.");
            }}
          >
            Delete my data
          </button>
        </div>
      </Section>

      <Section title="Delete account">
        <p className="text-sm text-mist">This permanently deletes your account and everything in it. Type DELETE to confirm.</p>
        <label htmlFor="confirm-delete" className="sr-only">
          Type DELETE to confirm
        </label>
        <input id="confirm-delete" className="field" value={confirmText} onChange={(e) => setConfirmText(e.target.value)} />
        <button
          className="btn border-danger text-danger hover:bg-danger hover:text-ink-950"
          disabled={confirmText !== "DELETE"}
          onClick={async () => {
            await api.deleteAccount();
            setUser(null);
            router.replace("/");
          }}
        >
          Delete account
        </button>
      </Section>
    </div>
  );
}
