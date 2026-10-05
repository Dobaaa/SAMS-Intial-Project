import axios from "axios";
import * as SecureStore from "expo-secure-store";

// Set EXPO_PUBLIC_API_URL (e.g. https://76-13-159-24.sslip.io/api). 10.0.2.2 = host machine from the Android emulator.
export const API_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://10.0.2.2:8000/api";

export type User = { id: string; name: string; email: string; role: string };

const K = { access: "access", refresh: "refresh", user: "user" };
export const store = {
  get: (k: keyof typeof K) => SecureStore.getItemAsync(K[k]),
  set: (k: keyof typeof K, v: string) => SecureStore.setItemAsync(K[k], v),
  clear: () => Promise.all(Object.values(K).map((k) => SecureStore.deleteItemAsync(k))),
};

export const api = axios.create({ baseURL: API_URL, timeout: 20000 });

let onLogout: () => void = () => {};
export const setLogoutHandler = (fn: () => void) => (onLogout = fn);

api.interceptors.request.use(async (cfg) => {
  const t = await store.get("access");
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

let refreshing: Promise<string | null> | null = null;
api.interceptors.response.use(
  (r) => r,
  async (err) => {
    const cfg = err.config;
    if (err.response?.status !== 401 || cfg?._retried || cfg?.url?.includes("/auth/")) throw err;
    cfg._retried = true;
    refreshing ??= (async () => {
      const rt = await store.get("refresh");
      if (!rt) return null;
      try {
        const { data } = await axios.post(`${API_URL}/auth/refresh`, { refresh_token: rt });
        await store.set("access", data.access_token);
        return data.access_token as string;
      } catch {
        return null;
      }
    })().finally(() => (refreshing = null));
    const t = await refreshing;
    if (!t) {
      onLogout();
      throw err;
    }
    cfg.headers.Authorization = `Bearer ${t}`;
    return api(cfg);
  },
);

export const errMsg = (e: any) => e?.response?.data?.detail ?? (e?.code === "ECONNABORTED" || !e?.response ? "Can't reach the server" : "Something went wrong");
