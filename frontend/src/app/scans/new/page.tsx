"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppLayout } from "@/components/layout/app-layout";
import { scansApi, targetsApi } from "@/lib/api";
import type { TargetList } from "@/types";
import toast from "react-hot-toast";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

const SEVERITIES = ["critical", "high", "medium", "low", "info"];

export default function NewScanPage() {
  const router = useRouter();
  const [targetLists, setTargetLists] = useState<TargetList[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const [form, setForm] = useState({
    name: "",
    target_list_ids: [] as string[],
    config: {
      severity: ["critical", "high", "medium"],
      tags: [] as string[],
      templates: [] as string[],
      exclude_tags: [] as string[],
      rate_limit: 150,
      bulk_size: 25,
      concurrency: 25,
      timeout: 30,
      retries: 1,
      extra_flags: [] as string[],
    },
    scheduled_at: "",
  });

  useEffect(() => {
    targetsApi.lists().then((res) => setTargetLists(res.data));
  }, []);

  function toggleSeverity(sev: string) {
    setForm((prev) => ({
      ...prev,
      config: {
        ...prev.config,
        severity: prev.config.severity.includes(sev)
          ? prev.config.severity.filter((s) => s !== sev)
          : [...prev.config.severity, sev],
      },
    }));
  }

  function toggleTargetList(id: string) {
    setForm((prev) => ({
      ...prev,
      target_list_ids: prev.target_list_ids.includes(id)
        ? prev.target_list_ids.filter((t) => t !== id)
        : [...prev.target_list_ids, id],
    }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) return toast.error("Scan name is required");
    if (form.target_list_ids.length === 0)
      return toast.error("Select at least one target list");

    setSubmitting(true);
    try {
      const payload = {
        ...form,
        scheduled_at: form.scheduled_at || null,
      };
      const res = await scansApi.create(payload);
      toast.success("Scan created!");
      router.push(`/scans/${res.data.id}`);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Failed to create scan";
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AppLayout>
      <div className="p-6 max-w-3xl mx-auto space-y-6">
        <div className="flex items-center gap-3">
          <Link
            href="/scans"
            className="p-1.5 rounded-lg hover:bg-secondary text-muted-foreground transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <h1 className="text-2xl font-bold text-foreground">New Scan</h1>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Name */}
          <div className="rounded-xl border border-border bg-card p-5 space-y-4">
            <h2 className="text-sm font-semibold text-foreground">General</h2>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Scan Name *</label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                placeholder="e.g. Weekly CVE Scan – Production"
                className="w-full px-3 py-2 rounded-lg bg-secondary border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary text-sm"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">
                Schedule (optional)
              </label>
              <input
                type="datetime-local"
                value={form.scheduled_at}
                onChange={(e) =>
                  setForm((p) => ({ ...p, scheduled_at: e.target.value }))
                }
                className="w-full px-3 py-2 rounded-lg bg-secondary border border-border text-foreground focus:outline-none focus:ring-2 focus:ring-primary text-sm"
              />
            </div>
          </div>

          {/* Target Lists */}
          <div className="rounded-xl border border-border bg-card p-5 space-y-4">
            <h2 className="text-sm font-semibold text-foreground">
              Target Lists *
            </h2>
            {targetLists.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No target lists.{" "}
                <Link href="/targets" className="text-primary hover:underline">
                  Create one first
                </Link>
              </p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {targetLists.map((tl) => (
                  <label
                    key={tl.id}
                    className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                      form.target_list_ids.includes(tl.id)
                        ? "border-primary bg-primary/5"
                        : "border-border hover:bg-secondary"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={form.target_list_ids.includes(tl.id)}
                      onChange={() => toggleTargetList(tl.id)}
                      className="rounded border-border text-primary"
                    />
                    <div>
                      <p className="text-sm font-medium text-foreground">
                        {tl.name}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {tl.target_count} targets
                      </p>
                    </div>
                  </label>
                ))}
              </div>
            )}
          </div>

          {/* Severity */}
          <div className="rounded-xl border border-border bg-card p-5 space-y-4">
            <h2 className="text-sm font-semibold text-foreground">
              Severity Filter
            </h2>
            <div className="flex flex-wrap gap-2">
              {SEVERITIES.map((sev) => {
                const active = form.config.severity.includes(sev);
                const colors: Record<string, string> = {
                  critical: "border-red-500 bg-red-500/10 text-red-400",
                  high: "border-orange-500 bg-orange-500/10 text-orange-400",
                  medium: "border-yellow-500 bg-yellow-500/10 text-yellow-400",
                  low: "border-blue-500 bg-blue-500/10 text-blue-400",
                  info: "border-gray-500 bg-gray-500/10 text-gray-400",
                };
                return (
                  <button
                    key={sev}
                    type="button"
                    onClick={() => toggleSeverity(sev)}
                    className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                      active
                        ? colors[sev]
                        : "border-border text-muted-foreground hover:bg-secondary"
                    }`}
                  >
                    {sev.charAt(0).toUpperCase() + sev.slice(1)}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Advanced Config */}
          <div className="rounded-xl border border-border bg-card p-5 space-y-4">
            <h2 className="text-sm font-semibold text-foreground">
              Performance
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              {(
                [
                  { key: "rate_limit", label: "Rate Limit (req/s)" },
                  { key: "bulk_size", label: "Bulk Size" },
                  { key: "concurrency", label: "Concurrency" },
                  { key: "timeout", label: "Timeout (s)" },
                  { key: "retries", label: "Retries" },
                ] as { key: keyof typeof form.config; label: string }[]
              ).map(({ key, label }) => (
                <div key={key} className="space-y-1">
                  <label className="text-xs text-muted-foreground">{label}</label>
                  <input
                    type="number"
                    value={form.config[key] as number}
                    onChange={(e) =>
                      setForm((p) => ({
                        ...p,
                        config: { ...p.config, [key]: Number(e.target.value) },
                      }))
                    }
                    className="w-full px-3 py-2 rounded-lg bg-secondary border border-border text-foreground focus:outline-none focus:ring-2 focus:ring-primary text-sm"
                  />
                </div>
              ))}
            </div>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full py-3 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {submitting ? "Launching scan..." : "Launch Scan"}
          </button>
        </form>
      </div>
    </AppLayout>
  );
}
