import "./App.css";
import Dashboard from "./pages/Dashboard";
import MasterTemplates from "./pages/MasterTemplates";
import UserManagement from "./pages/UserManagement";

function App() {
  const view = new URLSearchParams(window.location.search).get("view") || "dashboard";

  return (
    <div>
      <nav className="flex gap-2 border-b p-3">
        <a className="rounded border px-3 py-1" href="/?view=dashboard">Dashboard</a>
        <a className="rounded border px-3 py-1" href="/?view=users">Users</a>
        <a className="rounded border px-3 py-1" href="/?view=masters">Masters</a>
      </nav>
      {view === "users" ? <UserManagement /> : view === "masters" ? <MasterTemplates /> : <Dashboard />}
    </div>
  );
}

export default App;
