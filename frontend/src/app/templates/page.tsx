"use client";

import { useEffect, useState } from "react";
import { AppLayout } from "@/components/layout/app-layout";
import { templatesApi } from "@/lib/api";
import { SeverityBadge } from "@/components/findings/severity-badge";
import type { FindingSeverity } from "@/types";
import { Search, RefreshCw, Upload } from "lucide-react";
import toast from "react-hot-toast";

interface Template {
  id: string;
  name: string;
  path: string;
  severity: string;
  tags: string[];
  source: string;
  is_active: boolean;
  description?: string;
}

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [severity, setSeverity] = useState("");
  const [syncing, setSyncing] = useState(false);

  async function fetchTemplates() {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (search) params.search = search;
      if (severity) params.severity = severity;
      const res = await templatesApi.list(params);
      setTemplates(res.data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchTemplates();
  }, [search, severity]);

  async function handleSync() {
    setSyncing(true);
    try {
      await templatesApi.sync();
      toast.success("Template sync started in background");
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Sync failed (Admin only)";
      toast.error(msg);
    } finally {
      setSyncing(false);
    }
  }

  return (
    <AppLayout>
      <div className="p-6 space-y-6 max-w-7xl mx-auto">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Templates</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {templates.length} templates indexed
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleSync}
              disabled={syncing}
              className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border text-sm text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${syncing ? "animate-spin" : ""}`} />
              Sync Templates
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search templates..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-2 rounded-lg bg-card border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary text-sm"
            />
          </div>
          <select
            value={severity}
            onChange={(e) => setSeverity(e.target.value)}
            className="px-3 py-2 rounded-lg bg-card border border-border text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <option value="">All Severities</option>
            {["critical", "high", "medium", "low", "info"].map((s) => (
              <option key={s} value={s}>
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </option>
            ))}
          </select>
        </div>

        <div className="rounded-xl border border-border bg-card overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            </div>
          ) : templates.length === 0 ? (
            <div className="py-16 text-center text-muted-foreground text-sm">
              No templates found. Run a sync first.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-secondary/30 text-xs text-muted-foreground border-b border-border">
                  <tr className="text-left">
                    <th className="px-4 py-3 font-medium">Severity</th>
                    <th className="px-4 py-3 font-medium">Name</th>
                    <th className="px-4 py-3 font-medium hidden xl:table-cell">Tags</th>
                    <th className="px-4 py-3 font-medium">Source</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {templates.map((t) => (
                    <tr key={t.id} className="hover:bg-secondary/30 transition-colors">
                      <td className="px-4 py-3">
                        <SeverityBadge severity={t.severity as FindingSeverity} />
                      </td>
                      <td className="px-4 py-3">
                        <p className="font-medium text-foreground text-sm">{t.name}</p>
                        <p className="text-xs text-muted-foreground font-mono truncate max-w-[300px]">
                          {t.path.split("/").slice(-2).join("/")}
                        </p>
                      </td>
                      <td className="px-4 py-3 hidden xl:table-cell">
                        <div className="flex flex-wrap gap-1">
                          {t.tags.slice(0, 4).map((tag) => (
                            <span key={tag} className="px-1.5 py-0.5 rounded bg-secondary text-xs text-muted-foreground">
                              {tag}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`text-xs px-2 py-0.5 rounded-full ${
                          t.source === "CUSTOM"
                            ? "bg-primary/10 text-primary"
                            : "bg-secondary text-muted-foreground"
                        }`}>
                          {t.source}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
