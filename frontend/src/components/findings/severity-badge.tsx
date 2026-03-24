"use client";

import { cn, SEVERITY_CONFIG } from "@/lib/utils";
import type { FindingSeverity } from "@/types";

export function SeverityBadge({ severity }: { severity: FindingSeverity }) {
  const cfg = SEVERITY_CONFIG[severity] ?? SEVERITY_CONFIG.unknown;
  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border",
        cfg.bg,
        cfg.color,
        cfg.border
      )}
    >
      {cfg.label}
    </span>
  );
}
