import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { api } from "../lib/api";
import { useAuth, type Role } from "../stores/auth";

type NavItem = {
  to: string;
  label: string;
  roles?: Role[];
};

const NAV_ITEMS: NavItem[] = [
  { to: "/dashboard", label: "Dashboard", roles: ["admin"] },
  { to: "/reviewer-dashboard", label: "My Agreements", roles: ["project_director", "accounts", "operation_manager", "gm"] },
  { to: "/agreements/new", label: "New Agreement", roles: ["admin"] },
  { to: "/workflow", label: "Workflow Review" },
  { to: "/resolution", label: "Resolution" },
  { to: "/archive", label: "Archive" },
  { to: "/masters", label: "Masters", roles: ["admin"] },
  { to: "/users", label: "Users", roles: ["admin"] },
];

export default function AppLayout() {
  const navigate = useNavigate();
  const { user, refreshToken, clear } = useAuth();

  const logout = async () => {
    try {
      if (refreshToken) {
        await api.post("/auth/logout", { refresh_token: refreshToken });
      }
    } catch {
      // Even if revocation fails, clear local state so the UI reflects logout.
    } finally {
      clear();
      navigate("/login", { replace: true });
    }
  };

  const visibleItems = NAV_ITEMS.filter(
    (item) => !item.roles || (user && item.roles.includes(user.role))
  );

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `rounded-lg border px-3 py-1.5 text-sm font-medium transition ${
      isActive
        ? "border-sky-400 bg-sky-600 text-white"
        : "border-sky-200 bg-white/80 text-sky-800 hover:border-sky-300 hover:bg-sky-50"
    }`;

  return (
    <div className="min-h-screen bg-gradient-to-b from-sky-50 via-cyan-50 to-white">
      <nav className="sticky top-0 z-10 flex flex-wrap items-center gap-3 border-b border-sky-100 bg-white/90 p-3 backdrop-blur">
        <img
          src="/bhatia-logo.png"
          alt="Bhatia General Contracting Co."
          className="h-10 w-auto pr-3 border-r border-sky-100"
        />
        {visibleItems.map((item) => (
          <NavLink key={item.to} to={item.to} className={linkClass}>
            {item.label}
          </NavLink>
        ))}
        <div className="ml-auto flex items-center gap-3 text-sm text-sky-800">
          {user && (
            <span>
              {user.name} <span className="text-sky-500">({user.role})</span>
            </span>
          )}
          <button
            onClick={logout}
            className="rounded-lg border border-sky-200 bg-white px-3 py-1.5 font-medium text-sky-800 hover:border-sky-300 hover:bg-sky-50"
          >
            Logout
          </button>
        </div>
      </nav>
      <Outlet />
    </div>
  );
}
