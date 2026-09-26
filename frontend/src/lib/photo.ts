"use client";

import { useSyncExternalStore } from "react";

// The stored photo's server file name, remembered so Stylist can try looks on without re-uploading.
const KEY = "lookbook.sourceFile";
const listeners = new Set<() => void>();

function read(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setSourceFile(name: string | null) {
  try {
    if (name) localStorage.setItem(KEY, name);
    else localStorage.removeItem(KEY);
  } catch {}
  listeners.forEach((l) => l());
}

export function sourceFileFromUrl(url: string) {
  return url.split("/").pop() ?? "";
}

export function useSourceFile() {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    read,
    () => null,
  );
}
