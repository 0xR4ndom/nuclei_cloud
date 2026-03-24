"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { AppLayout } from "@/components/layout/app-layout";
import { ScanBadge } from "@/components/scans/scan-badge";
import { SeverityBadge } from "@/components/findings/severity-badge";
import { scansApi, findingsApi } from "@/lib/api";
import { formatDate, formatRelative } from "@/lib/utils";
import type { Scan, Finding } from "@/types";
import {
  ArrowLeft,
  Clock,
  Target,
  Shield,
  Search,
  ChevronLeft,
  ChevronRight,
  Copy,
} from "lucide-react";
import toast from "react-hot-toast";

export default function ScanDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [scan, setScan] = useState<Scan | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [search, setSearch] = useState("");
  const [severity, setSeverity] = useState("");
  const [loading, setLoading] = useState(true);
  const [selectedFinding, setSelectedFinding] = useState<Finding | null>(null);
  const sseRef = useRef<EventSource | null>(null);

  async function fetchScan() {
    try {
      const res = await scansApi.get(id);
      setScan(res.data);
    } catch {
      toast.error("Scan not found");
      router.push("/scans");
    }
  }

  async function fetchFindings() {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { scan_id: id, page, size: 20 };
      if (search) params.search = search;
      if (severity) params.severity = severity;
      const res = await findingsApi.list(params);
      setFindings(res.data.items ?? []);
      setTotal(res.data.total);
      setPages(res.data.pages);
    } finally {
      setLoading(false);
    }
  }

  // SSE for live updates
  function startSSE() {
    if (sseRef.current) sseRef.current.close();
    const token = document.cookie
      .split("; ")
      .find((row) => row.startsWith("access_token="))
      ?.split("=")[1];

    const url = `/api/v1/scans/${id}/stream`;
    const es = new EventSource(url);
    sseRef.current = es;

    es.onmessage = (e) => {
      const data = JSON.parse(e.data);
      setScan((prev) =>
        prev
          ? {
              ...prev,
              status: data.status,
              total_findings: data.total_findings,
              critical_count: data.critical,
              high_count: data.high,
            }
          : prev
      );
      if (data.new_findings?.length) {
        fetchFindings();
      }
      if (data.done) {
        es.close();
        fetchScan();
      }
    };
    es.onerror = () => es.close();
  }

  useEffect(() => {
    fetchScan().then(() => {
      fetchFindings();
    });
  }, [id]);

  useEffect(() => {
    if (scan?.status === "RUNNING" || scan?.status === "QUEUED") {
      startSSE();
    }
    return () => sseRef.current?.close();
  }, [scan?.status]);

  useEffect(() => {
    fetchFindings();
  }, [page, search, severity]);

  if (!scan) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center h-64">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="p-6 space-y-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <Link
              href="/scans"
              className="p-1.5 rounded-lg hover:bg-secondary text-muted-foreground transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
            </Link>
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-xl font-bold text-foreground">{scan.name}</h1>
                <ScanBadge status={scan.status} />
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                Created {formatRelative(scan.created_at)}
              </p>
            </div>
          </div>
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            {
              label: "Total Findings",
              value: scan.total_findings,
              icon: Shield,
              color: "text-emerald-400",
            },
            {
              label: "Critical",
              value: scan.critical_count,
              icon: Shield,
              color: "text-red-400",
            },
            {
              label: "High",
              value: scan.high_count,
              icon: Shield,
              color: "text-orange-400",
            },
            {
              label: "Targets",
              value: scan.total_targets,
              icon: Target,
              color: "text-blue-400",
            },
          ].map(({ label, value, icon: Icon, color }) => (
            <div
              key={label}
              className="rounded-xl border border-border bg-card p-4 flex items-center gap-3"
            >
              <Icon className={`w-5 h-5 ${color}`} />
              <div>
                <p className="text-xl font-bold text-foreground">{value}</p>
                <p className="text-xs text-muted-foreground">{label}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Timing */}
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="flex flex-wrap gap-6 text-xs text-muted-foreground">
            <span>
              <span className="font-medium text-foreground">Started:</span>{" "}
              {formatDate(scan.started_at)}
            </span>
            <span>
              <span className="font-medium text-foreground">Completed:</span>{" "}
              {formatDate(scan.completed_at)}
            </span>
            {scan.error_message && (
              <span className="text-red-400">
                <span className="font-medium">Error:</span> {scan.error_message}
              </span>
            )}
          </div>
        </div>

        {/* Findings */}
        <div className="rounded-xl border border-border bg-card">
          {/* Toolbar */}
          <div className="flex flex-wrap items-center gap-3 p-4 border-b border-border">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search findings..."
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(1);
                }}
                className="w-full pl-9 pr-3 py-2 rounded-lg bg-secondary border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary text-sm"
              />
            </div>
            <select
              value={severity}
              onChange={(e) => {
                setSeverity(e.target.value);
                setPage(1);
              }}
              className="px-3 py-2 rounded-lg bg-secondary border border-border text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="">All Severities</option>
              {["critical", "high", "medium", "low", "info"].map((s) => (
                <option key={s} value={s}>
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </option>
              ))}
            </select>
            <span className="text-xs text-muted-foreground ml-auto">
              {total} finding{total !== 1 ? "s" : ""}
            </span>
          </div>

          {/* Table */}
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            </div>
          ) : findings.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground text-sm">
              No findings match your filters
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-secondary/30 text-xs text-muted-foreground">
                  <tr className="text-left">
                    <th className="px-4 py-3 font-medium">Severity</th>
                    <th className="px-4 py-3 font-medium">Template</th>
                    <th className="px-4 py-3 font-medium">Target</th>
                    <th className="px-4 py-3 font-medium hidden lg:table-cell">Found</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {findings.map((f) => (
                    <tr
                      key={f.id}
                      onClick={() => setSelectedFinding(f)}
                      className="hover:bg-secondary/30 cursor-pointer transition-colors"
                    >
                      <td className="px-4 py-3">
                        <SeverityBadge severity={f.severity} />
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-foreground max-w-[220px] truncate">
                        {f.template_name ?? f.template_id ?? "—"}
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground max-w-[220px] truncate">
                        {f.matched_at}
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground hidden lg:table-cell">
                        {formatRelative(f.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          {pages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-border">
              <span className="text-xs text-muted-foreground">
                Page {page} of {pages}
              </span>
              <div className="flex gap-1">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="p-1.5 rounded hover:bg-secondary disabled:opacity-40 transition-colors"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(pages, p + 1))}
                  disabled={page === pages}
                  className="p-1.5 rounded hover:bg-secondary disabled:opacity-40 transition-colors"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Finding Detail Modal */}
      {selectedFinding && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
          onClick={() => setSelectedFinding(null)}
        >
          <div
            className="bg-card border border-border rounded-xl max-w-2xl w-full max-h-[80vh] overflow-y-auto p-6 space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between">
              <div>
                <SeverityBadge severity={selectedFinding.severity} />
                <h3 className="text-lg font-semibold text-foreground mt-2">
                  {selectedFinding.template_name}
                </h3>
                <p className="text-xs font-mono text-muted-foreground">
                  {selectedFinding.template_id}
                </p>
              </div>
              <button
                onClick={() => setSelectedFinding(null)}
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-sm">
              <div>
                <p className="text-xs text-muted-foreground mb-1">Matched At</p>
                <p className="font-mono text-foreground text-xs bg-secondary px-3 py-2 rounded-lg break-all">
                  {selectedFinding.matched_at}
                </p>
              </div>

              {selectedFinding.description && (
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Description</p>
                  <p className="text-foreground text-sm">{selectedFinding.description}</p>
                </div>
              )}

              {selectedFinding.extracted_results.length > 0 && (
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Extracted</p>
                  <div className="space-y-1">
                    {selectedFinding.extracted_results.map((r, i) => (
                      <p
                        key={i}
                        className="font-mono text-xs bg-secondary px-3 py-2 rounded-lg break-all"
                      >
                        {r}
                      </p>
                    ))}
                  </div>
                </div>
              )}

              {selectedFinding.curl_command && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-xs text-muted-foreground">cURL Command</p>
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(selectedFinding.curl_command!);
                        toast.success("Copied!");
                      }}
                      className="text-xs text-primary hover:underline flex items-center gap-1"
                    >
                      <Copy className="w-3 h-3" /> Copy
                    </button>
                  </div>
                  <pre className="font-mono text-xs bg-secondary px-3 py-2 rounded-lg overflow-x-auto whitespace-pre-wrap break-all text-foreground">
                    {selectedFinding.curl_command}
                  </pre>
                </div>
              )}

              {selectedFinding.reference.length > 0 && (
                <div>
                  <p className="text-xs text-muted-foreground mb-1">References</p>
                  <ul className="space-y-0.5">
                    {selectedFinding.reference.map((ref, i) => (
                      <li key={i} className="text-xs text-primary break-all">
                        {ref}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {selectedFinding.tags.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {selectedFinding.tags.map((tag) => (
                    <span
                      key={tag}
                      className="px-2 py-0.5 rounded-full bg-secondary text-xs text-muted-foreground"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </AppLayout>
  );
}
