"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";
import { AuthShell } from "@/components/auth/AuthShell";
import { Field } from "@/components/ui/Field";
import { Glyph } from "@/components/ui/Glyph";
import { Turnstile, turnstileEnabled } from "@/components/ui/Turnstile";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";

export default function SignupPage() {
  const router = useRouter();
  const { setUser } = useSession();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const onToken = useCallback((t: string | null) => setToken(t), []);
  const weak = password.length > 0 && password.length < 10;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setUser(await api.signup({ email, password, full_name: name, turnstile_token: token }));
      router.replace("/studio");
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <AuthShell title="Create your account" lead="Two minutes from now you'll be wearing something you described.">
      <form onSubmit={submit} className="space-y-6" noValidate>
        <Field label="Name (optional)" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} />
        <Field label="Email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <Field
          label="Password"
          type="password"
          autoComplete="new-password"
          required
          minLength={10}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          hint="At least 10 characters. A short phrase works well."
          error={weak ? "Use at least 10 characters." : null}
        />
        <Turnstile onToken={onToken} />
        {error && (
          <p role="alert" className="border border-danger/40 px-4 py-3 text-sm text-danger">
            {error}
          </p>
        )}
        <button className="btn-signal w-full" disabled={busy || !email || password.length < 10 || (turnstileEnabled && !token)}>
          {busy ? "Creating account" : "Create account"} <Glyph name="arrow" className="arrow-nudge size-4" />
        </button>
        <p className="text-sm text-mist">
          Already have an account?{" "}
          <Link href="/login" className="text-frost underline underline-offset-4">
            Sign in
          </Link>
          . By continuing you agree to our{" "}
          <Link href="/privacy" className="text-frost underline underline-offset-4">
            privacy policy
          </Link>
          .
        </p>
      </form>
    </AuthShell>
  );
}
