"use client";

import { Shield, Search, AlertTriangle, Activity } from "lucide-react";
import type { GlobalStats } from "@/types";
import { cn } from "@/lib/utils";

interface StatsCardsProps {
  stats: GlobalStats | null;
}

export function StatsCards({ stats }: StatsCardsProps) {
  const cards = [
    {
      label: "Total Scans",
      value: stats?.total_scans ?? 0,
      icon: Search,
      color: "text-blue-400",
      bg: "bg-blue-500/10",
    },
    {
      label: "Total Findings",
      value: stats?.total_findings ?? 0,
      icon: Shield,
      color: "text-emerald-400",
      bg: "bg-emerald-500/10",
    },
    {
      label: "Critical",
      value: stats?.findings_by_severity?.critical ?? 0,
      icon: AlertTriangle,
      color: "text-red-400",
      bg: "bg-red-500/10",
    },
    {
      label: "Active Scans",
      value: stats?.running_scans ?? 0,
      icon: Activity,
      color: "text-orange-400",
      bg: "bg-orange-500/10",
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
      {cards.map(({ label, value, icon: Icon, color, bg }) => (
        <div
          key={label}
          className="rounded-xl border border-border bg-card p-5 flex items-center gap-4"
        >
          <div className={cn("p-3 rounded-lg", bg)}>
            <Icon className={cn("w-5 h-5", color)} />
          </div>
          <div>
            <p className="text-2xl font-bold text-foreground">
              {value.toLocaleString()}
            </p>
            <p className="text-sm text-muted-foreground">{label}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
