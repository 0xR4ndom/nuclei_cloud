"use client";

import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { GlobalStats } from "@/types";

const COLORS: Record<string, string> = {
  critical: "#ef4444",
  high: "#f97316",
  medium: "#eab308",
  low: "#3b82f6",
  info: "#6b7280",
  unknown: "#374151",
};

interface SeverityChartProps {
  stats: GlobalStats | null;
}

export function SeverityChart({ stats }: SeverityChartProps) {
  if (!stats) return null;

  const data = Object.entries(stats.findings_by_severity)
    .filter(([, v]) => v > 0)
    .map(([key, value]) => ({
      name: key.charAt(0).toUpperCase() + key.slice(1),
      value,
      key,
    }));

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-muted-foreground text-sm">
        No findings yet
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={55}
          outerRadius={85}
          paddingAngle={3}
          dataKey="value"
        >
          {data.map((entry) => (
            <Cell
              key={entry.key}
              fill={COLORS[entry.key] ?? "#6b7280"}
              strokeWidth={0}
            />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            background: "hsl(222 47% 8%)",
            border: "1px solid hsl(222 47% 14%)",
            borderRadius: 8,
            color: "hsl(213 31% 91%)",
            fontSize: 13,
          }}
        />
        <Legend
          formatter={(value) => (
            <span style={{ color: "hsl(215 16% 57%)", fontSize: 12 }}>
              {value}
            </span>
          )}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
