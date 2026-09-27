"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";

/** Explicit biometric consent (BIPA / GDPR Art. 9) before any portrait is uploaded. */
export function ConsentDialog({ open, onClose, onGranted }: { open: boolean; onClose: () => void; onGranted: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const { refresh } = useSession();
  const [checked, setChecked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  async function grant() {
    setBusy(true);
    setError(null);
    try {
      await api.setConsent(true);
      await refresh();
      onGranted();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby="consent-title"
      className="m-auto w-[min(34rem,calc(100%-2rem))] border border-line-strong bg-ink-850 p-0 text-frost backdrop:bg-black/70"
    >
      <div className="space-y-5 p-7">
        <p className="label text-signal">Before your first photo</p>
        <h2 id="consent-title" className="display-md text-2xl">
          How we handle your photo
        </h2>
        <ul className="space-y-3 text-sm leading-relaxed text-mist">
          <li>Your portrait is used only to generate the try-ons you ask for.</li>
          <li>It is encrypted in storage, and LOOKBOOK never uses it to train models.</li>
          <li>Uploaded portraits are deleted automatically after 14 days. You can delete them sooner at any time.</li>
          <li>Withdrawing consent in Account deletes every portrait and generated image straight away.</li>
        </ul>
        <label className="flex items-start gap-3 text-sm">
          <input
            type="checkbox"
            className="mt-1 size-4 accent-[var(--color-signal)]"
            checked={checked}
            onChange={(e) => setChecked(e.target.checked)}
          />
          <span>
            I agree to LOOKBOOK processing images of me for virtual try-on, as described in the{" "}
            <Link href="/privacy" className="underline underline-offset-4" target="_blank">
              privacy policy
            </Link>
            .
          </span>
        </label>
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
        <div className="flex flex-wrap justify-end gap-3">
          <button className="btn-line" onClick={onClose}>
            Not now
          </button>
          <button className="btn-signal" disabled={!checked || busy} onClick={grant}>
            {busy ? "Saving" : "I agree"}
          </button>
        </div>
      </div>
    </dialog>
  );
}
