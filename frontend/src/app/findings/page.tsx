"use client";

import { useEffect, useState } from "react";
import { AppLayout } from "@/components/layout/app-layout";
import { SeverityBadge } from "@/components/findings/severity-badge";
import { findingsApi } from "@/lib/api";
import { formatRelative } from "@/lib/utils";
import type { Finding } from "@/types";
import { Search, ChevronLeft, ChevronRight } from "lucide-react";
import toast from "react-hot-toast";

const SEVERITIES = ["critical", "high", "medium", "low", "info"];

export default function FindingsPage() {
  const [findings, setFindings] = useState<Finding[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [search, setSearch] = useState("");
  const [severity, setSeverity] = useState("");
  const [loading, setLoading] = useState(true);
  const [selectedFinding, setSelectedFinding] = useState<Finding | null>(null);

  async function fetchFindings() {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, size: 50 };
      if (search) params.search = search;
      if (severity) params.severity = severity;
      const res = await findingsApi.list(params);
      setFindings(res.data.items ?? []);
      setTotal(res.data.total);
      setPages(res.data.pages);
    } catch {
      toast.error("Failed to load findings");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchFindings();
  }, [page, search, severity]);

  return (
    <AppLayout>
      <div className="p-6 space-y-6 max-w-7xl mx-auto">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Findings</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {total.toLocaleString()} total findings
            </p>
          </div>
        </div>

        {/* Severity quick-filter */}
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => { setSeverity(""); setPage(1); }}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              !severity ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground hover:text-foreground"
            }`}
          >
            All
          </button>
          {SEVERITIES.map((s) => (
            <button
              key={s}
              onClick={() => { setSeverity(s); setPage(1); }}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                severity === s ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground hover:text-foreground"
              }`}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>

        <div className="rounded-xl border border-border bg-card">
          {/* Search */}
          <div className="p-4 border-b border-border">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search by template, target, host..."
                value={search}
                onChange={(e) => { setSearch(e.target.value); setPage(1); }}
                className="w-full pl-9 pr-3 py-2 rounded-lg bg-secondary border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary text-sm"
              />
            </div>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-16">
              <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            </div>
          ) : findings.length === 0 ? (
            <div className="py-16 text-center text-muted-foreground text-sm">
              No findings found
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-secondary/30 text-xs text-muted-foreground border-b border-border">
                  <tr className="text-left">
                    <th className="px-4 py-3 font-medium">Severity</th>
                    <th className="px-4 py-3 font-medium">Template</th>
                    <th className="px-4 py-3 font-medium">Target</th>
                    <th className="px-4 py-3 font-medium hidden xl:table-cell">Tags</th>
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
                      <td className="px-4 py-3 font-mono text-xs text-foreground max-w-[200px] truncate">
                        {f.template_name ?? f.template_id ?? "—"}
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground max-w-[200px] truncate">
                        {f.matched_at}
                      </td>
                      <td className="px-4 py-3 hidden xl:table-cell">
                        <div className="flex flex-wrap gap-1">
                          {f.tags.slice(0, 3).map((t) => (
                            <span key={t} className="px-1.5 py-0.5 rounded bg-secondary text-xs text-muted-foreground">
                              {t}
                            </span>
                          ))}
                        </div>
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

          {pages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-border">
              <span className="text-xs text-muted-foreground">
                Page {page} of {pages} • {total} findings
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
              <button onClick={() => setSelectedFinding(null)} className="text-muted-foreground hover:text-foreground">✕</button>
            </div>
            <div className="space-y-3 text-sm">
              <div>
                <p className="text-xs text-muted-foreground mb-1">Matched At</p>
                <p className="font-mono text-xs bg-secondary px-3 py-2 rounded-lg break-all text-foreground">
                  {selectedFinding.matched_at}
                </p>
              </div>
              {selectedFinding.description && (
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Description</p>
                  <p className="text-foreground">{selectedFinding.description}</p>
                </div>
              )}
              {selectedFinding.curl_command && (
                <div>
                  <p className="text-xs text-muted-foreground mb-1">cURL</p>
                  <pre className="font-mono text-xs bg-secondary px-3 py-2 rounded-lg overflow-x-auto whitespace-pre-wrap break-all text-foreground">
                    {selectedFinding.curl_command}
                  </pre>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </AppLayout>
  );
}
