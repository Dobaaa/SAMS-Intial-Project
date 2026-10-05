import React, { createContext, useContext, useEffect, useState } from "react";
import { api, setLogoutHandler, store, User } from "./api";
import { unregisterPush } from "./push";

type Ctx = { user: User | null; ready: boolean; login: (e: string, p: string) => Promise<void>; logout: () => Promise<void> };
const AuthCtx = createContext<Ctx>(null as any);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  const clear = async () => {
    await store.clear();
    setUser(null);
  };

  useEffect(() => {
    setLogoutHandler(() => void clear());
    (async () => {
      const raw = await store.get("user");
      if (raw && (await store.get("access"))) setUser(JSON.parse(raw));
      setReady(true);
    })();
  }, []);

  const login = async (email: string, password: string) => {
    const { data } = await api.post("/auth/login", { email: email.trim(), password });
    await store.set("access", data.access_token);
    await store.set("refresh", data.refresh_token);
    await store.set("user", JSON.stringify(data.user));
    setUser(data.user);
  };

  const logout = async () => {
    await unregisterPush().catch(() => {});
    const rt = await store.get("refresh");
    if (rt) await api.post("/auth/logout", { refresh_token: rt }).catch(() => {});
    await clear();
  };

  return <AuthCtx.Provider value={{ user, ready, login, logout }}>{children}</AuthCtx.Provider>;
}
