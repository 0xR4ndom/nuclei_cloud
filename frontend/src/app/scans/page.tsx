"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AppLayout } from "@/components/layout/app-layout";
import { ScanBadge } from "@/components/scans/scan-badge";
import { scansApi } from "@/lib/api";
import { formatRelative } from "@/lib/utils";
import type { Scan, ScanStatus } from "@/types";
import { Plus, Trash2, XCircle, RefreshCw } from "lucide-react";
import toast from "react-hot-toast";

const STATUS_FILTERS: Array<{ label: string; value: ScanStatus | "" }> = [
  { label: "All", value: "" },
  { label: "Running", value: "RUNNING" },
  { label: "Done", value: "DONE" },
  { label: "Failed", value: "FAILED" },
  { label: "Queued", value: "QUEUED" },
];

export default function ScansPage() {
  const [scans, setScans] = useState<Scan[]>([]);
  const [filter, setFilter] = useState<ScanStatus | "">("");
  const [loading, setLoading] = useState(true);

  async function fetchScans() {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (filter) params.status = filter;
      const res = await scansApi.list(params);
      setScans(res.data);
    } catch {
      toast.error("Failed to load scans");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchScans();
  }, [filter]);

  async function handleCancel(id: string) {
    try {
      await scansApi.cancel(id);
      toast.success("Scan cancelled");
      fetchScans();
    } catch {
      toast.error("Failed to cancel scan");
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this scan and all its findings?")) return;
    try {
      await scansApi.delete(id);
      toast.success("Scan deleted");
      setScans((prev) => prev.filter((s) => s.id !== id));
    } catch {
      toast.error("Failed to delete scan");
    }
  }

  return (
    <AppLayout>
      <div className="p-6 space-y-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Scans</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {scans.length} scan{scans.length !== 1 ? "s" : ""}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchScans}
              disabled={loading}
              className="p-2 rounded-lg border border-border text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            </button>
            <Link
              href="/scans/new"
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
            >
              <Plus className="w-4 h-4" />
              New Scan
            </Link>
          </div>
        </div>

        {/* Filters */}
        <div className="flex gap-2">
          {STATUS_FILTERS.map(({ label, value }) => (
            <button
              key={label}
              onClick={() => setFilter(value as ScanStatus | "")}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                filter === value
                  ? "bg-primary text-primary-foreground"
                  : "bg-secondary text-muted-foreground hover:text-foreground"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Table */}
        <div className="rounded-xl border border-border bg-card overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            </div>
          ) : scans.length === 0 ? (
            <div className="py-16 text-center text-muted-foreground text-sm">
              No scans found.{" "}
              <Link href="/scans/new" className="text-primary hover:underline">
                Create one
              </Link>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-secondary/30">
                <tr className="text-left text-xs text-muted-foreground">
                  <th className="px-4 py-3 font-medium">Name</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium text-right">Findings</th>
                  <th className="px-4 py-3 font-medium hidden lg:table-cell">Started</th>
                  <th className="px-4 py-3 font-medium hidden lg:table-cell">Created</th>
                  <th className="px-4 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {scans.map((scan) => (
                  <tr key={scan.id} className="hover:bg-secondary/30 transition-colors">
                    <td className="px-4 py-3">
                      <Link
                        href={`/scans/${scan.id}`}
                        className="font-medium text-foreground hover:text-primary transition-colors"
                      >
                        {scan.name}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <ScanBadge status={scan.status} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-2 text-xs">
                        {scan.critical_count > 0 && (
                          <span className="text-red-400 font-medium">{scan.critical_count}C</span>
                        )}
                        {scan.high_count > 0 && (
                          <span className="text-orange-400 font-medium">{scan.high_count}H</span>
                        )}
                        <span className="text-muted-foreground">
                          {scan.total_findings}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground hidden lg:table-cell text-xs">
                      {formatRelative(scan.started_at)}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground hidden lg:table-cell text-xs">
                      {formatRelative(scan.created_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        {["PENDING", "QUEUED", "RUNNING"].includes(scan.status) && (
                          <button
                            onClick={() => handleCancel(scan.id)}
                            className="p-1.5 rounded hover:bg-secondary text-muted-foreground hover:text-orange-400 transition-colors"
                            title="Cancel"
                          >
                            <XCircle className="w-4 h-4" />
                          </button>
                        )}
                        <button
                          onClick={() => handleDelete(scan.id)}
                          className="p-1.5 rounded hover:bg-secondary text-muted-foreground hover:text-red-400 transition-colors"
                          title="Delete"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
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
