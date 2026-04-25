import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

type ToastKind = "success" | "error" | "info";

type Toast = {
  id: number;
  kind: ToastKind;
  message: string;
};

type ToastApi = {
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
};

const ToastContext = createContext<ToastApi | null>(null);

const AUTO_DISMISS_MS = 4500;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const counterRef = useRef(0);

  const remove = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (kind: ToastKind, message: string) => {
      counterRef.current += 1;
      const id = counterRef.current;
      setToasts((prev) => [...prev, { id, kind, message }]);
      window.setTimeout(() => remove(id), AUTO_DISMISS_MS);
    },
    [remove]
  );

  const api = useMemo<ToastApi>(
    () => ({
      success: (message) => push("success", message),
      error: (message) => push("error", message),
      info: (message) => push("info", message),
    }),
    [push]
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        className="pointer-events-none fixed right-4 top-4 z-50 flex w-full max-w-sm flex-col gap-2"
        aria-live="polite"
        aria-atomic="true"
      >
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onClose={() => remove(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastItem({ toast, onClose }: { toast: Toast; onClose: () => void }) {
  // Fade-in once mounted; the parent already auto-dismisses on a timer.
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const t = window.setTimeout(() => setVisible(true), 10);
    return () => window.clearTimeout(t);
  }, []);

  const palette =
    toast.kind === "success"
      ? "border-emerald-300 bg-emerald-50 text-emerald-900"
      : toast.kind === "error"
      ? "border-red-300 bg-red-50 text-red-900"
      : "border-sky-300 bg-sky-50 text-sky-900";

  const icon = toast.kind === "success" ? "✓" : toast.kind === "error" ? "✕" : "ℹ";

  return (
    <div
      role={toast.kind === "error" ? "alert" : "status"}
      className={`pointer-events-auto flex items-start gap-3 rounded-lg border px-3 py-2 shadow-md transition-all duration-200 ${palette} ${
        visible ? "translate-x-0 opacity-100" : "translate-x-2 opacity-0"
      }`}
    >
      <span className="mt-0.5 flex h-5 w-5 flex-none items-center justify-center rounded-full bg-white/60 text-xs font-bold">
        {icon}
      </span>
      <div className="flex-1 whitespace-pre-wrap break-words text-sm">{toast.message}</div>
      <button
        type="button"
        className="text-xs opacity-60 hover:opacity-100"
        onClick={onClose}
        aria-label="Dismiss"
      >
        ✕
      </button>
    </div>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return ctx;
}
