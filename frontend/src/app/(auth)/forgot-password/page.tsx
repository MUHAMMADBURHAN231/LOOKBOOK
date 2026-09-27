"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { AuthShell } from "@/components/auth/AuthShell";
import { Field } from "@/components/ui/Field";
import { Turnstile, turnstileEnabled } from "@/components/ui/Turnstile";
import { api } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const onToken = useCallback((t: string | null) => setToken(t), []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.forgotPassword({ email, turnstile_token: token });
      setSent(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell title="Reset password" lead="We'll email you a link. It works once and expires after 30 minutes.">
      {sent ? (
        <div role="status" className="panel space-y-4 p-6">
          <p className="text-frost">If {email} has an account, a reset link is on its way.</p>
          <p className="text-sm text-mist">Check your spam folder if it hasn&apos;t arrived in a few minutes.</p>
          <Link href="/login" className="btn-line">
            Back to sign in
          </Link>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-6" noValidate>
          <Field label="Email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          <Turnstile onToken={onToken} />
          {error && (
            <p role="alert" className="border border-danger/40 px-4 py-3 text-sm text-danger">
              {error}
            </p>
          )}
          <button className="btn-signal w-full" disabled={busy || !email || (turnstileEnabled && !token)}>
            {busy ? "Sending" : "Send reset link"}
          </button>
          <Link href="/login" className="block text-sm text-mist hover:text-frost">
            Back to sign in
          </Link>
        </form>
      )}
    </AuthShell>
  );
}
