"use client";

import { useEffect, useState } from "react";
import { AppLayout } from "@/components/layout/app-layout";
import { usersApi } from "@/lib/api";
import type { User, UserRole } from "@/types";
import { Plus, Trash2, UserCheck } from "lucide-react";
import { formatRelative } from "@/lib/utils";
import toast from "react-hot-toast";

const ROLE_COLORS: Record<UserRole, string> = {
  ADMIN: "text-red-400 bg-red-500/10",
  ANALYST: "text-blue-400 bg-blue-500/10",
  VIEWER: "text-gray-400 bg-gray-500/10",
};

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ email: "", password: "", full_name: "", role: "ANALYST" as UserRole });

  async function fetchUsers() {
    setLoading(true);
    try {
      const res = await usersApi.list();
      setUsers(res.data);
    } catch {
      toast.error("Access denied or failed to load users");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchUsers(); }, []);

  async function handleCreate() {
    if (!form.email || !form.password) return toast.error("Email and password required");
    try {
      await usersApi.create(form);
      toast.success("User created");
      setShowCreate(false);
      fetchUsers();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Failed";
      toast.error(msg);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this user?")) return;
    try {
      await usersApi.delete(id);
      toast.success("User deleted");
      setUsers((p) => p.filter((u) => u.id !== id));
    } catch {
      toast.error("Failed");
    }
  }

  return (
    <AppLayout>
      <div className="p-6 space-y-6 max-w-5xl mx-auto">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Users</h1>
            <p className="text-sm text-muted-foreground mt-0.5">RBAC user management</p>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            <Plus className="w-4 h-4" />
            New User
          </button>
        </div>

        {showCreate && (
          <div className="rounded-xl border border-border bg-card p-5 space-y-4">
            <h2 className="text-sm font-semibold text-foreground">Create User</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {[
                { key: "email", label: "Email", type: "email", placeholder: "user@example.com" },
                { key: "password", label: "Password", type: "password", placeholder: "••••••••" },
                { key: "full_name", label: "Full Name", type: "text", placeholder: "John Doe" },
              ].map(({ key, label, type, placeholder }) => (
                <div key={key} className="space-y-1">
                  <label className="text-xs text-muted-foreground">{label}</label>
                  <input
                    type={type}
                    value={(form as Record<string, string>)[key]}
                    onChange={(e) => setForm((p) => ({ ...p, [key]: e.target.value }))}
                    placeholder={placeholder}
                    className="w-full px-3 py-2 rounded-lg bg-secondary border border-border text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
              ))}
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Role</label>
                <select
                  value={form.role}
                  onChange={(e) => setForm((p) => ({ ...p, role: e.target.value as UserRole }))}
                  className="w-full px-3 py-2 rounded-lg bg-secondary border border-border text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  {["ADMIN", "ANALYST", "VIEWER"].map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex gap-2">
              <button onClick={handleCreate} className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors">Create</button>
              <button onClick={() => setShowCreate(false)} className="px-4 py-2 rounded-lg bg-secondary text-muted-foreground text-sm hover:text-foreground transition-colors">Cancel</button>
            </div>
          </div>
        )}

        <div className="rounded-xl border border-border bg-card overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-secondary/30 text-xs text-muted-foreground border-b border-border">
                <tr className="text-left">
                  <th className="px-4 py-3 font-medium">User</th>
                  <th className="px-4 py-3 font-medium">Role</th>
                  <th className="px-4 py-3 font-medium hidden md:table-cell">Status</th>
                  <th className="px-4 py-3 font-medium hidden lg:table-cell">Created</th>
                  <th className="px-4 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-secondary/30 transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                          <UserCheck className="w-4 h-4 text-primary" />
                        </div>
                        <div>
                          <p className="font-medium text-foreground text-sm">{u.full_name ?? "—"}</p>
                          <p className="text-xs text-muted-foreground">{u.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${ROLE_COLORS[u.role]}`}>
                        {u.role}
                      </span>
                    </td>
                    <td className="px-4 py-3 hidden md:table-cell">
                      <span className={`text-xs ${u.is_active ? "text-emerald-400" : "text-muted-foreground"}`}>
                        {u.is_active ? "Active" : "Disabled"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground hidden lg:table-cell">
                      {formatRelative(u.created_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => handleDelete(u.id)}
                        className="p-1.5 rounded hover:bg-secondary text-muted-foreground hover:text-red-400 transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
