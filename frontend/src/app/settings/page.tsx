"use client";

import { useEffect, useState } from "react";
import { AppLayout } from "@/components/layout/app-layout";
import { authApi } from "@/lib/api";
import type { User } from "@/types";
import { Copy, RefreshCw } from "lucide-react";
import toast from "react-hot-toast";

export default function SettingsPage() {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    authApi.me().then((r) => setUser(r.data));
  }, []);

  async function regenerateKey() {
    try {
      const res = await authApi.regenerateApiKey();
      setUser(res.data);
      toast.success("API key regenerated");
    } catch {
      toast.error("Failed");
    }
  }

  return (
    <AppLayout>
      <div className="p-6 space-y-6 max-w-2xl mx-auto">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Settings</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Account & API configuration</p>
        </div>

        <div className="rounded-xl border border-border bg-card p-5 space-y-4">
          <h2 className="text-sm font-semibold text-foreground">Profile</h2>
          {user && (
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Email</span>
                <span className="text-foreground">{user.email}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Role</span>
                <span className="text-foreground">{user.role}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Status</span>
                <span className={user.is_active ? "text-emerald-400" : "text-muted-foreground"}>
                  {user.is_active ? "Active" : "Inactive"}
                </span>
              </div>
            </div>
          )}
        </div>

        <div className="rounded-xl border border-border bg-card p-5 space-y-4">
          <h2 className="text-sm font-semibold text-foreground">API Key</h2>
          <p className="text-xs text-muted-foreground">
            Use this key to authenticate API requests directly without JWT.
          </p>
          {user?.api_key && (
            <div className="flex items-center gap-2">
              <code className="flex-1 px-3 py-2 rounded-lg bg-secondary text-xs font-mono text-foreground break-all">
                {user.api_key}
              </code>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(user.api_key!);
                  toast.success("Copied!");
                }}
                className="p-2 rounded-lg hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors"
              >
                <Copy className="w-4 h-4" />
              </button>
            </div>
          )}
          <button
            onClick={regenerateKey}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-secondary text-sm text-muted-foreground hover:text-foreground hover:bg-secondary/70 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Regenerate Key
          </button>
        </div>
      </div>
    </AppLayout>
  );
}
