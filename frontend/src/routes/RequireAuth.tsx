import { useEffect } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";

import { api } from "../lib/api";
import { useAuth, type AuthUser, type Role } from "../stores/auth";

type Props = {
  roles?: Role[];
};

export default function RequireAuth({ roles }: Props) {
  const location = useLocation();
  const { accessToken, user, setUser, clear } = useAuth();

  // If we have a token but lost the user (e.g. from a stale persisted state),
  // re-hydrate from /auth/me before deciding to render or redirect.
  useEffect(() => {
    let cancelled = false;
    async function hydrate() {
      if (accessToken && !user) {
        try {
          const { data } = await api.get<AuthUser>("/auth/me");
          if (!cancelled) setUser(data);
        } catch {
          if (!cancelled) clear();
        }
      }
    }
    void hydrate();
    return () => {
      cancelled = true;
    };
  }, [accessToken, user, setUser, clear]);

  if (!accessToken) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  }

  if (roles && user && !roles.includes(user.role)) {
    return (
      <div className="p-6">
        <div className="rounded-xl border border-red-300 bg-red-50 p-4 text-red-800">
          You do not have permission to view this page.
        </div>
      </div>
    );
  }

  return <Outlet />;
}
