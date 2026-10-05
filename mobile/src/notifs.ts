import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { AppState } from "react-native";
import { api } from "./api";
import { showLocal } from "./push";

type Listener = (n: Notif) => void;
const listeners = new Set<Listener>();
export const onNewNotification = (fn: Listener) => (listeners.add(fn), () => void listeners.delete(fn));

export type Notif = { id: string; agreement_id: string | null; title: string; body: string; read: boolean; created_at: string };
export type Feed = { unread: number; items: Notif[] };

/** Feed + 10s foreground poll; newly arrived items raise a local banner. */
export function useNotifications() {
  const qc = useQueryClient();
  const seen = useRef<Set<string> | null>(null);
  const q = useQuery({
    queryKey: ["notifications"],
    queryFn: async () => (await api.get<Feed>("/notifications")).data,
    refetchInterval: 10000,
  });

  useEffect(() => {
    if (!q.data) return;
    const ids = new Set(q.data.items.map((n) => n.id));
    if (seen.current) {
      q.data.items.filter((n) => !seen.current!.has(n.id) && !n.read).forEach((n) => {
        void showLocal(n);
        listeners.forEach((l) => l(n));
      });
    }
    seen.current = ids; // first load only primes the set — no banners for old history
  }, [q.data]);

  useEffect(() => {
    const sub = AppState.addEventListener("change", (s) => s === "active" && qc.invalidateQueries({ queryKey: ["notifications"] }));
    return () => sub.remove();
  }, [qc]);

  return q;
}
