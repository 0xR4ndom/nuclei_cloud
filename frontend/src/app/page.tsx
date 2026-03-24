"use client";

import { useEffect, useState } from "react";
import { AppLayout } from "@/components/layout/app-layout";
import { StatsCards } from "@/components/dashboard/stats-cards";
import { SeverityChart } from "@/components/dashboard/severity-chart";
import { ScanBadge } from "@/components/scans/scan-badge";
import { SeverityBadge } from "@/components/findings/severity-badge";
import { scansApi, findingsApi } from "@/lib/api";
import { formatRelative } from "@/lib/utils";
import type { GlobalStats, Scan, Finding } from "@/types";
import Link from "next/link";
import { RefreshCw, Plus, ArrowRight } from "lucide-react";
import toast from "react-hot-toast";

export default function DashboardPage() {
  const [stats, setStats] = useState<GlobalStats | null>(null);
  const [recentScans, setRecentScans] = useState<Scan[]>([]);
  const [recentFindings, setRecentFindings] = useState<Finding[]>([]);
  const [loading, setLoading] = useState(true);

  async function fetchData() {
    setLoading(true);
    try {
      const [statsRes, scansRes, findingsRes] = await Promise.all([
        scansApi.stats(),
        scansApi.list({ limit: 5 }),
        findingsApi.list({ size: 8, page: 1 }),
      ]);
      setStats(statsRes.data);
      setRecentScans(scansRes.data);
      setRecentFindings(findingsRes.data.items ?? []);
    } catch {
      toast.error("Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30_000);
    return () => clearInterval(interval);
  }, []);

  return (
    <AppLayout>
      <div className="p-6 space-y-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              Vulnerability scan overview
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchData}
              disabled={loading}
              className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border text-sm text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
              Refresh
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

        {/* Stats */}
        <StatsCards stats={stats} />

        {/* Charts + Recent Scans */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Pie Chart */}
          <div className="lg:col-span-1 rounded-xl border border-border bg-card p-5">
            <h2 className="text-sm font-semibold text-foreground mb-4">
              Findings by Severity
            </h2>
            <SeverityChart stats={stats} />
          </div>

          {/* Recent Scans */}
          <div className="lg:col-span-2 rounded-xl border border-border bg-card p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-foreground">
                Recent Scans
              </h2>
              <Link
                href="/scans"
                className="text-xs text-primary hover:underline flex items-center gap-1"
              >
                View all <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
            <div className="space-y-2">
              {recentScans.length === 0 ? (
                <p className="text-sm text-muted-foreground py-4 text-center">
                  No scans yet.{" "}
                  <Link href="/scans/new" className="text-primary hover:underline">
                    Start one
                  </Link>
                </p>
              ) : (
                recentScans.map((scan) => (
                  <Link
                    key={scan.id}
                    href={`/scans/${scan.id}`}
                    className="flex items-center justify-between p-3 rounded-lg hover:bg-secondary transition-colors group"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <ScanBadge status={scan.status} />
                      <span className="text-sm text-foreground truncate font-medium">
                        {scan.name}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 flex-shrink-0 ml-4">
                      <span className="text-xs text-muted-foreground hidden sm:block">
                        {formatRelative(scan.created_at)}
                      </span>
                      <div className="flex gap-2 text-xs">
                        {scan.critical_count > 0 && (
                          <span className="text-red-400 font-medium">
                            {scan.critical_count}C
                          </span>
                        )}
                        {scan.high_count > 0 && (
                          <span className="text-orange-400 font-medium">
                            {scan.high_count}H
                          </span>
                        )}
                        {scan.total_findings > 0 && (
                          <span className="text-muted-foreground">
                            {scan.total_findings} total
                          </span>
                        )}
                      </div>
                    </div>
                  </Link>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Recent Findings */}
        <div className="rounded-xl border border-border bg-card p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-foreground">
              Recent Findings
            </h2>
            <Link
              href="/findings"
              className="text-xs text-primary hover:underline flex items-center gap-1"
            >
              View all <ArrowRight className="w-3 h-3" />
            </Link>
          </div>

          {recentFindings.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">
              No findings yet
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-muted-foreground border-b border-border">
                    <th className="pb-2 font-medium">Severity</th>
                    <th className="pb-2 font-medium">Template</th>
                    <th className="pb-2 font-medium">Target</th>
                    <th className="pb-2 font-medium hidden md:table-cell">Found</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {recentFindings.map((f) => (
                    <tr key={f.id} className="hover:bg-secondary/50 transition-colors">
                      <td className="py-2.5 pr-4">
                        <SeverityBadge severity={f.severity} />
                      </td>
                      <td className="py-2.5 pr-4 font-mono text-xs text-foreground max-w-[200px] truncate">
                        {f.template_name ?? f.template_id ?? "—"}
                      </td>
                      <td className="py-2.5 pr-4 text-xs text-muted-foreground max-w-[200px] truncate">
                        {f.matched_at}
                      </td>
                      <td className="py-2.5 text-xs text-muted-foreground hidden md:table-cell">
                        {formatRelative(f.created_at)}
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
