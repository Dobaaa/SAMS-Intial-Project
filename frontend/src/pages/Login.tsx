import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";

import { api } from "../lib/api";
import { useAuth, type AuthUser } from "../stores/auth";

type LoginResponse = {
  access_token: string;
  refresh_token: string;
  user: AuthUser;
};

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const setSession = useAuth((s) => s.setSession);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const redirectTo = (location.state as { from?: string } | null)?.from ?? "/dashboard";

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const { data } = await api.post<LoginResponse>("/auth/login", { email, password });
      setSession(
        { accessToken: data.access_token, refreshToken: data.refresh_token },
        data.user
      );
      navigate(redirectTo, { replace: true });
    } catch (err: unknown) {
      const message =
        typeof err === "object" && err && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail ??
            "Login failed"
          : "Login failed";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-sky-50 via-cyan-50 to-white p-5">
      <form
        onSubmit={submit}
        className="w-full max-w-sm space-y-4 rounded-2xl border border-sky-100 bg-white p-6 shadow-sm"
      >
        <h1 className="text-2xl font-bold text-sky-900">SAMS Sign in</h1>
        <p className="text-sm text-sky-700">
          Subcontract Agreement Management System
        </p>

        <div className="space-y-1">
          <label htmlFor="login-email" className="block text-sm font-medium text-sky-900">
            Email
          </label>
          <input
            id="login-email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-lg border border-sky-200 p-2 focus:border-sky-500 focus:outline-none"
            autoComplete="email"
          />
        </div>

        <div className="space-y-1">
          <label htmlFor="login-password" className="block text-sm font-medium text-sky-900">
            Password
          </label>
          <input
            id="login-password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-lg border border-sky-200 p-2 focus:border-sky-500 focus:outline-none"
            autoComplete="current-password"
          />
        </div>

        {error && (
          <div className="rounded-lg border border-red-300 bg-red-50 p-2 text-sm text-red-700">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-lg bg-sky-600 px-3 py-2 font-medium text-white transition hover:bg-sky-700 disabled:opacity-60"
        >
          {submitting ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
