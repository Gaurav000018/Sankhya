import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

import { api, getToken, setToken } from "./api";
import type { User } from "./types";

interface AuthState {
  user: User | null;
  loading: boolean;
  signIn: (token: string) => Promise<void>;
  signOut: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      setUser(await api.get<User>("/auth/me"));
    } catch {
      // An expired or tampered token is indistinguishable from no token here.
      setToken(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const signIn = useCallback(
    async (token: string) => {
      setToken(token);
      setLoading(true);
      await load();
    },
    [load],
  );

  const signOut = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}

/** What each role is allowed to open. Mirrors the API's RBAC — the server is
 *  still the authority; this only keeps people out of screens that would fail. */
export const ROLE_ROUTES: Record<string, string[]> = {
  learner: ["/", "/quiz", "/learning", "/promotion", "/interview", "/settings"],
  supervisor: ["/", "/quiz", "/learning", "/promotion", "/team", "/interview", "/settings"],
  sme: ["/", "/quiz", "/learning", "/promotion", "/review", "/interview", "/settings"],
  admin: ["/", "/quiz", "/learning", "/promotion", "/team", "/review", "/admin", "/acbp", "/interview", "/settings"],
};

export function canAccess(role: string | undefined, path: string): boolean {
  if (!role) return false;
  return (ROLE_ROUTES[role] ?? []).includes(path);
}
