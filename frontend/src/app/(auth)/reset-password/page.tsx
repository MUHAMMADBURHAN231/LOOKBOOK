"use client";

import Link from "next/link";
import { useSyncExternalStore, useState } from "react";
import { AuthShell } from "@/components/auth/AuthShell";
import { Field } from "@/components/ui/Field";
import { api } from "@/lib/api";

// The token travels in the URL fragment (#token=...), which browsers never send to servers,
// so it can't leak through access logs or Referer headers.
const readToken = () => new URLSearchParams(window.location.hash.slice(1)).get("token") ?? "";
const subscribe = (cb: () => void) => {
  window.addEventListener("hashchange", cb);
  return () => window.removeEventListener("hashchange", cb);
};

export default function ResetPasswordPage() {
  const token = useSyncExternalStore(subscribe, readToken, () => "");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const mismatch = confirm.length > 0 && confirm !== password;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.resetPassword({ token, new_password: password });
      history.replaceState(null, "", "/reset-password"); // drop the used token from the address bar
      setDone(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <AuthShell title="Password updated" lead="For safety, every device was signed out.">
        <Link href="/login" className="btn-signal">
          Sign in with your new password
        </Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Choose a new password" lead="Use at least 10 characters.">
      {!token ? (
        <p role="alert" className="text-mist">
          This page needs the link from your reset email.{" "}
          <Link href="/forgot-password" className="text-frost underline underline-offset-4">
            Request a new one
          </Link>
          .
        </p>
      ) : (
        <form onSubmit={submit} className="space-y-6" noValidate>
          <Field label="New password" type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <Field
            label="Confirm password"
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            error={mismatch ? "Passwords don't match." : null}
          />
          {error && (
            <p role="alert" className="border border-danger/40 px-4 py-3 text-sm text-danger">
              {error}
            </p>
          )}
          <button className="btn-signal w-full" disabled={busy || password.length < 10 || password !== confirm}>
            {busy ? "Saving" : "Save new password"}
          </button>
        </form>
      )}
    </AuthShell>
  );
}
