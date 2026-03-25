import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { formatDistanceToNow, format } from "date-fns";
import type { FindingSeverity, ScanStatus } from "@/types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(date: string | null | undefined): string {
  if (!date) return "—";
  return format(new Date(date), "MMM d, yyyy HH:mm");
}

export function formatRelative(date: string | null | undefined): string {
  if (!date) return "—";
  return formatDistanceToNow(new Date(date), { addSuffix: true });
}

export const SEVERITY_CONFIG: Record<
  FindingSeverity,
  { label: string; color: string; bg: string; border: string }
> = {
  critical: {
    label: "Critical",
    color: "text-red-500",
    bg: "bg-red-500/10",
    border: "border-red-500/30",
  },
  high: {
    label: "High",
    color: "text-orange-500",
    bg: "bg-orange-500/10",
    border: "border-orange-500/30",
  },
  medium: {
    label: "Medium",
    color: "text-yellow-500",
    bg: "bg-yellow-500/10",
    border: "border-yellow-500/30",
  },
  low: {
    label: "Low",
    color: "text-blue-500",
    bg: "bg-blue-500/10",
    border: "border-blue-500/30",
  },
  info: {
    label: "Info",
    color: "text-gray-400",
    bg: "bg-gray-500/10",
    border: "border-gray-500/30",
  },
  unknown: {
    label: "Unknown",
    color: "text-gray-400",
    bg: "bg-gray-500/10",
    border: "border-gray-500/30",
  },
};

export const STATUS_CONFIG: Record<
  ScanStatus,
  { label: string; color: string; bg: string }
> = {
  PENDING: { label: "Pending", color: "text-gray-400", bg: "bg-gray-500/10" },
  QUEUED: { label: "Queued", color: "text-blue-400", bg: "bg-blue-500/10" },
  RUNNING: {
    label: "Running",
    color: "text-emerald-400",
    bg: "bg-emerald-500/10",
  },
  DONE: { label: "Done", color: "text-green-400", bg: "bg-green-500/10" },
  FAILED: { label: "Failed", color: "text-red-400", bg: "bg-red-500/10" },
  CANCELLED: {
    label: "Cancelled",
    color: "text-gray-400",
    bg: "bg-gray-500/10",
  },
};
