import "./App.css";
import AgreementCreate from "./pages/AgreementCreate";
import Dashboard from "./pages/Dashboard";
import MasterTemplates from "./pages/MasterTemplates";
import UserManagement from "./pages/UserManagement";

function App() {
  const view = new URLSearchParams(window.location.search).get("view") || "dashboard";
  const linkClass =
    "rounded-lg border border-sky-200 bg-white/80 px-3 py-1.5 text-sm font-medium text-sky-800 shadow-sm transition hover:border-sky-300 hover:bg-sky-50";

  return (
    <div className="min-h-screen bg-gradient-to-b from-sky-50 via-cyan-50 to-white">
      <nav className="sticky top-0 z-10 flex gap-2 border-b border-sky-100 bg-white/90 p-3 backdrop-blur">
        <a className={linkClass} href="/?view=dashboard">Dashboard</a>
        <a className={linkClass} href="/?view=users">Users</a>
        <a className={linkClass} href="/?view=agreements">Agreements</a>
        <a className={linkClass} href="/?view=masters">Masters</a>
      </nav>
      {view === "users" ? (
        <UserManagement />
      ) : view === "masters" ? (
        <MasterTemplates />
      ) : view === "agreements" ? (
        <AgreementCreate />
      ) : (
        <Dashboard />
      )}
    </div>
  );
}

export default App;
