"use client";

import { cn, STATUS_CONFIG } from "@/lib/utils";
import type { ScanStatus } from "@/types";

export function ScanBadge({ status }: { status: ScanStatus }) {
  const cfg = STATUS_CONFIG[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium",
        cfg.bg,
        cfg.color
      )}
    >
      {status === "RUNNING" && (
        <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
      )}
      {cfg.label}
    </span>
  );
}
