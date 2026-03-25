"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Search,
  Target,
  FileCode2,
  Webhook,
  Users,
  Settings,
  Shield,
  LogOut,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { logout } from "@/lib/auth";

const navItems = [
  { href: "/", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/scans", icon: Search, label: "Scans" },
  { href: "/findings", icon: Shield, label: "Findings" },
  { href: "/targets", icon: Target, label: "Targets" },
  { href: "/templates", icon: FileCode2, label: "Templates" },
  { href: "/webhooks", icon: Webhook, label: "Webhooks" },
  { href: "/users", icon: Users, label: "Users" },
  { href: "/settings", icon: Settings, label: "Settings" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-60 flex-shrink-0 h-screen flex flex-col border-r border-border bg-card">
      {/* Logo */}
      <div className="h-16 flex items-center gap-2.5 px-5 border-b border-border">
        <div className="w-8 h-8 rounded-md bg-primary flex items-center justify-center flex-shrink-0">
          <Shield className="w-4 h-4 text-primary-foreground" />
        </div>
        <span className="text-sm font-semibold text-foreground tracking-wide">
          Nuclei Cloud
        </span>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 px-3 space-y-0.5 overflow-y-auto">
        {navItems.map(({ href, icon: Icon, label }) => {
          const isActive =
            href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
                isActive
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-muted-foreground hover:text-foreground hover:bg-secondary"
              )}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="p-3 border-t border-border">
        <button
          onClick={logout}
          className="flex items-center gap-3 w-full px-3 py-2 rounded-md text-sm text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
        >
          <LogOut className="w-4 h-4" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
