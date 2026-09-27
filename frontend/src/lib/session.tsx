"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import type { User } from "./types";

type SessionState = {
  /** undefined while loading, null when signed out */
  user: User | null | undefined;
  refresh: () => Promise<User | null>;
  setUser: (u: User | null) => void;
  signOut: () => Promise<void>;
};

const SessionContext = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null | undefined>(undefined);

  const refresh = useCallback(async () => {
    try {
      const me = await api.me();
      setUser(me);
      return me;
    } catch {
      setUser(null); // 401 (signed out) or unreachable: treat as signed out
      return null;
    }
  }, []);

  useEffect(() => {
    // Fetch the signed-in user once on mount; setState happens after the request resolves.
    let active = true;
    api
      .me()
      .then((me) => active && setUser(me))
      .catch(() => active && setUser(null));
    return () => {
      active = false;
    };
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setUser(null);
    }
  }, []);

  const value = useMemo(() => ({ user, refresh, setUser, signOut }), [user, refresh, signOut]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionState {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside SessionProvider");
  return ctx;
}
