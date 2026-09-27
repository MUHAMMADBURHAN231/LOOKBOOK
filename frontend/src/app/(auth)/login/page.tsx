"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useState } from "react";
import { AuthShell } from "@/components/auth/AuthShell";
import { Field } from "@/components/ui/Field";
import { Glyph } from "@/components/ui/Glyph";
import { Turnstile, turnstileEnabled } from "@/components/ui/Turnstile";
import { api } from "@/lib/api";
import { safeNext } from "@/lib/safeNext";
import { useSession } from "@/lib/session";

export default function LoginPage() {
  return (
    <AuthShell title="Sign in" lead="Pick up where you left off.">
      <Suspense>
        <LoginForm />
      </Suspense>
    </AuthShell>
  );
}

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { setUser } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const onToken = useCallback((t: string | null) => setToken(t), []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setUser(await api.login({ email, password, turnstile_token: token }));
      router.replace(safeNext(params.get("next")));
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-6" noValidate>
      <Field label="Email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
      <Field
        label="Password"
        type="password"
        autoComplete="current-password"
        required
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <Turnstile onToken={onToken} />
      {error && (
        <p role="alert" className="border border-danger/40 px-4 py-3 text-sm text-danger">
          {error}
        </p>
      )}
      <button className="btn-signal w-full" disabled={busy || !email || !password || (turnstileEnabled && !token)}>
        {busy ? "Signing in" : "Sign in"} <Glyph name="arrow" className="arrow-nudge size-4" />
      </button>
      <div className="flex justify-between text-sm">
        <Link href="/forgot-password" className="text-mist underline-offset-4 hover:text-frost hover:underline">
          Forgot password?
        </Link>
        <Link href="/signup" className="text-mist underline-offset-4 hover:text-frost hover:underline">
          Create an account
        </Link>
      </div>
    </form>
  );
}
