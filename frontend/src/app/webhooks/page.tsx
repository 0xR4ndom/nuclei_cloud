"use client";

import { useEffect, useState } from "react";
import { AppLayout } from "@/components/layout/app-layout";
import { webhooksApi } from "@/lib/api";
import type { Webhook, WebhookType } from "@/types";
import { Plus, Trash2, TestTube, ToggleLeft, ToggleRight } from "lucide-react";
import toast from "react-hot-toast";

export default function WebhooksPage() {
  const [webhooks, setWebhooks] = useState<Webhook[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    name: "",
    url: "",
    type: "GENERIC" as WebhookType,
    events: ["scan.completed", "finding.critical"],
    severity_filter: ["critical", "high"],
    secret: "",
  });

  async function fetchWebhooks() {
    setLoading(true);
    try {
      const res = await webhooksApi.list();
      setWebhooks(res.data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchWebhooks();
  }, []);

  async function handleCreate() {
    if (!form.name || !form.url) return toast.error("Name and URL required");
    try {
      await webhooksApi.create(form);
      toast.success("Webhook created");
      setShowCreate(false);
      fetchWebhooks();
    } catch {
      toast.error("Failed to create webhook");
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete webhook?")) return;
    try {
      await webhooksApi.delete(id);
      toast.success("Deleted");
      setWebhooks((prev) => prev.filter((w) => w.id !== id));
    } catch {
      toast.error("Failed to delete");
    }
  }

  async function handleToggle(wh: Webhook) {
    try {
      await webhooksApi.update(wh.id, { is_active: !wh.is_active });
      setWebhooks((prev) =>
        prev.map((w) => (w.id === wh.id ? { ...w, is_active: !w.is_active } : w))
      );
    } catch {
      toast.error("Failed to update");
    }
  }

  async function handleTest(id: string) {
    try {
      await webhooksApi.test(id);
      toast.success("Test notification sent!");
    } catch {
      toast.error("Test failed");
    }
  }

  return (
    <AppLayout>
      <div className="p-6 space-y-6 max-w-4xl mx-auto">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Webhooks</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              Discord, Slack, Jira and custom notifications
            </p>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add Webhook
          </button>
        </div>

        {showCreate && (
          <div className="rounded-xl border border-border bg-card p-5 space-y-4">
            <h2 className="text-sm font-semibold text-foreground">New Webhook</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Name</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                  placeholder="Discord alerts"
                  className="w-full px-3 py-2 rounded-lg bg-secondary border border-border text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Type</label>
                <select
                  value={form.type}
                  onChange={(e) => setForm((p) => ({ ...p, type: e.target.value as WebhookType }))}
                  className="w-full px-3 py-2 rounded-lg bg-secondary border border-border text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  {["DISCORD", "SLACK", "JIRA", "GENERIC"].map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-1 sm:col-span-2">
                <label className="text-xs text-muted-foreground">Webhook URL</label>
                <input
                  type="url"
                  value={form.url}
                  onChange={(e) => setForm((p) => ({ ...p, url: e.target.value }))}
                  placeholder="https://discord.com/api/webhooks/..."
                  className="w-full px-3 py-2 rounded-lg bg-secondary border border-border text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <div className="space-y-1 sm:col-span-2">
                <label className="text-xs text-muted-foreground">Secret (optional, for HMAC signature)</label>
                <input
                  type="text"
                  value={form.secret}
                  onChange={(e) => setForm((p) => ({ ...p, secret: e.target.value }))}
                  placeholder="my-webhook-secret"
                  className="w-full px-3 py-2 rounded-lg bg-secondary border border-border text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleCreate}
                className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
              >
                Save
              </button>
              <button
                onClick={() => setShowCreate(false)}
                className="px-4 py-2 rounded-lg bg-secondary text-muted-foreground text-sm hover:text-foreground transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        ) : webhooks.length === 0 ? (
          <div className="rounded-xl border border-border bg-card py-16 text-center text-muted-foreground text-sm">
            No webhooks configured
          </div>
        ) : (
          <div className="space-y-3">
            {webhooks.map((wh) => (
              <div
                key={wh.id}
                className="rounded-xl border border-border bg-card p-4 flex items-center justify-between gap-4"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-foreground">{wh.name}</span>
                    <span className="px-2 py-0.5 rounded-full bg-secondary text-xs text-muted-foreground">
                      {wh.type}
                    </span>
                    {!wh.is_active && (
                      <span className="px-2 py-0.5 rounded-full bg-secondary text-xs text-muted-foreground">
                        Disabled
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5 truncate max-w-sm">
                    {wh.url}
                  </p>
                  <div className="flex gap-1.5 mt-1.5 flex-wrap">
                    {wh.events.map((ev) => (
                      <span key={ev} className="px-1.5 py-0.5 rounded bg-secondary text-xs text-muted-foreground">
                        {ev}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="flex items-center gap-1 flex-shrink-0">
                  <button
                    onClick={() => handleTest(wh.id)}
                    className="p-1.5 rounded hover:bg-secondary text-muted-foreground hover:text-primary transition-colors"
                    title="Test"
                  >
                    <TestTube className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleToggle(wh)}
                    className="p-1.5 rounded hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors"
                    title={wh.is_active ? "Disable" : "Enable"}
                  >
                    {wh.is_active ? (
                      <ToggleRight className="w-4 h-4 text-primary" />
                    ) : (
                      <ToggleLeft className="w-4 h-4" />
                    )}
                  </button>
                  <button
                    onClick={() => handleDelete(wh.id)}
                    className="p-1.5 rounded hover:bg-secondary text-muted-foreground hover:text-red-400 transition-colors"
                    title="Delete"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </AppLayout>
  );
}
