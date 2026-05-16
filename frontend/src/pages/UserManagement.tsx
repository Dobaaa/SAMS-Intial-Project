import { useEffect, useMemo, useState } from "react";

import { api } from "../lib/api";
import { formatDateTime } from "../lib/formatDate";

type UserRow = {
  id: string;
  name: string;
  email: string;
  role: "admin" | "project_director" | "accounts" | "operation_manager" | "gm";
  is_active: boolean;
  last_login?: string | null;
};

function generateTempPassword(): string {
  const seed = Math.random().toString(36).slice(-8);
  return `SAMS-${seed}#1`;
}

export default function UserManagement() {
  const [users, setUsers] = useState<UserRow[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [editing, setEditing] = useState<UserRow | null>(null);
  const [form, setForm] = useState({ name: "", email: "", role: "accounts", password: generateTempPassword() });

  const loadUsers = async () => {
    const { data } = await api.get("/users/");
    setUsers(data);
  };

  useEffect(() => {
    void loadUsers();
  }, []);

  const roleBadge = useMemo(
    () => ({
      admin: "bg-purple-100 text-purple-700",
      project_director: "bg-blue-100 text-blue-700",
      accounts: "bg-indigo-100 text-indigo-700",
      operation_manager: "bg-cyan-100 text-cyan-700",
      gm: "bg-emerald-100 text-emerald-700",
    }),
    []
  );

  const createUser = async () => {
    await api.post("/users/", form);
    setShowAdd(false);
    setForm({ name: "", email: "", role: "accounts", password: generateTempPassword() });
    await loadUsers();
  };

  const saveEdit = async () => {
    if (!editing) return;
    await api.put(`/users/${editing.id}`, {
      name: editing.name,
      email: editing.email,
      role: editing.role,
    });
    setEditing(null);
    await loadUsers();
  };

  const toggleActive = async (user: UserRow) => {
    await api.patch(`/users/${user.id}/${user.is_active ? "deactivate" : "activate"}`);
    await loadUsers();
  };

  return (
    <div className="space-y-5 p-5">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-sky-900">User Management</h1>
        <button className="rounded-lg bg-sky-600 px-3 py-2 text-white transition hover:bg-sky-700" onClick={() => setShowAdd(true)}>
          Add User
        </button>
      </div>

      <table className="w-full border-collapse overflow-hidden rounded-xl border border-sky-100 bg-white shadow-sm">
        <thead>
          <tr className="bg-sky-50 text-sky-900">
            <th className="border p-2">Name</th>
            <th className="border p-2">Email</th>
            <th className="border p-2">Role</th>
            <th className="border p-2">Status</th>
            <th className="border p-2">Last Login</th>
            <th className="border p-2">Actions</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <tr key={user.id}>
              <td className="border border-sky-100 p-2">{user.name}</td>
              <td className="border border-sky-100 p-2">{user.email}</td>
              <td className="border border-sky-100 p-2">
                <span className={`rounded px-2 py-1 text-xs ${roleBadge[user.role]}`}>{user.role}</span>
              </td>
              <td className="border border-sky-100 p-2">{user.is_active ? "active" : "inactive"}</td>
              <td className="border border-sky-100 p-2">{formatDateTime(user.last_login) || "-"}</td>
              <td className="border border-sky-100 p-2">
                <div className="flex gap-2">
                  <button className="rounded-lg border border-sky-200 px-2 py-1 text-sky-700 hover:bg-sky-50" onClick={() => setEditing(user)}>
                    Edit
                  </button>
                  <button className="rounded-lg border border-sky-200 px-2 py-1 text-sky-700 hover:bg-sky-50" onClick={() => toggleActive(user)}>
                    {user.is_active ? "Deactivate" : "Activate"}
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {showAdd && (
        <div className="rounded-xl border border-sky-100 bg-white p-4 shadow-sm">
          <h2 className="mb-2 text-lg font-semibold">Add User</h2>
          <div className="grid grid-cols-2 gap-2">
            <input className="rounded-lg border border-sky-200 p-2" placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <input className="rounded-lg border border-sky-200 p-2" placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            <select className="rounded-lg border border-sky-200 p-2" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              <option value="admin">admin</option>
              <option value="project_director">project_director</option>
              <option value="accounts">accounts</option>
              <option value="operation_manager">operation_manager</option>
              <option value="gm">gm</option>
            </select>
            <input className="rounded-lg border border-sky-200 p-2" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          </div>
          <div className="mt-2 flex gap-2">
            <button className="rounded-lg bg-sky-600 px-3 py-2 text-white hover:bg-sky-700" onClick={createUser}>
              Save
            </button>
            <button className="rounded-lg border border-sky-200 px-3 py-2 text-sky-700 hover:bg-sky-50" onClick={() => setForm({ ...form, password: generateTempPassword() })}>
              Regenerate Temp Password
            </button>
          </div>
        </div>
      )}

      {editing && (
        <div className="rounded-xl border border-sky-100 bg-white p-4 shadow-sm">
          <h2 className="mb-2 text-lg font-semibold">Edit User</h2>
          <div className="grid grid-cols-2 gap-2">
            <input className="rounded-lg border border-sky-200 p-2" value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} />
            <input className="rounded-lg border border-sky-200 p-2" value={editing.email} onChange={(e) => setEditing({ ...editing, email: e.target.value })} />
            <select className="rounded-lg border border-sky-200 p-2" value={editing.role} onChange={(e) => setEditing({ ...editing, role: e.target.value as UserRow["role"] })}>
              <option value="admin">admin</option>
              <option value="project_director">project_director</option>
              <option value="accounts">accounts</option>
              <option value="operation_manager">operation_manager</option>
              <option value="gm">gm</option>
            </select>
          </div>
          <div className="mt-2 flex gap-2">
            <button className="rounded-lg bg-sky-600 px-3 py-2 text-white hover:bg-sky-700" onClick={saveEdit}>
              Save Changes
            </button>
            <button className="rounded-lg border border-sky-200 px-3 py-2 text-sky-700 hover:bg-sky-50" onClick={() => setEditing(null)}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
