"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useDeals } from "@/hooks/use-deals";
import { useScribeTheme } from "@/components/cogniscribe/theme-provider";
import {
  LayoutDashboard,
  Briefcase,
  Calendar,
  MessageSquare,
  Plug,
  Shield,
  ChevronDown,
} from "lucide-react";

const navItems = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Deals", href: "/deals", icon: Briefcase },
  { label: "AI Chat", href: "/chat", icon: MessageSquare },
  { label: "Calendar", href: "/calendar", icon: Calendar },
  { label: "Integrations", href: "/integrations", icon: Plug },
  { label: "Admin", href: "/admin", icon: Shield },
];

export function Sidebar() {
  const { isDark } = useScribeTheme();
  const pathname = usePathname();
  const { data: dealsData } = useDeals();
  const deals = dealsData?.items ?? [];
  const [dealsExpanded, setDealsExpanded] = useState(true);

  return (
    <aside
      className={cn(
        "flex w-64 flex-col h-screen relative z-30 border-r",
        isDark ? "bg-[#050505] text-white border-white/5" : "bg-[#f0eeea] text-black border-black/[0.06]"
      )}
    >
      <div className="flex h-16 items-center px-6">
        <Link href="/dashboard" className="flex items-center gap-2">
          <div
            className={cn(
              "w-7 h-7 rounded-md flex items-center justify-center",
              isDark ? "bg-white text-black" : "bg-black text-white"
            )}
          >
            <span className="font-display italic text-base leading-none translate-y-px">C</span>
          </div>
          <span className="text-[15px] font-medium tracking-tight">
            CogniSuite<span className={isDark ? "text-white/40" : "text-black/40"}>.ai</span>
          </span>
        </Link>
      </div>

      <nav className="flex-1 px-4 pb-6 overflow-y-auto">
        <p
          className={cn(
            "px-3 mb-3 text-[10px] font-mono font-medium uppercase tracking-[0.22em]",
            isDark ? "text-white/35" : "text-black/35"
          )}
        >
          Workspace
        </p>
        <div className="flex flex-col gap-0.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname.startsWith(item.href);
            const isDeals = item.href === "/deals";

            return (
              <div key={item.href}>
                <div className="flex items-center">
                  <Link
                    href={item.href}
                    className={cn(
                      "group flex flex-1 items-center gap-3 rounded-lg px-3 py-2 text-[13px] font-medium transition-colors",
                      isActive
                        ? isDark
                          ? "bg-white/[0.06] text-white"
                          : "bg-black/[0.05] text-black"
                        : isDark
                        ? "text-white/55 hover:text-white hover:bg-white/[0.03]"
                        : "text-black/60 hover:text-black hover:bg-black/[0.03]"
                    )}
                  >
                    <Icon
                      className={cn(
                        "h-4 w-4 transition-colors",
                        isActive
                          ? isDark
                            ? "text-white"
                            : "text-black"
                          : isDark
                          ? "text-white/40 group-hover:text-white/70"
                          : "text-black/40 group-hover:text-black/70"
                      )}
                    />
                    <span>{item.label}</span>
                    {isActive && (
                      <span className="ml-auto w-1.5 h-1.5 rounded-full bg-emerald-400 breathe"></span>
                    )}
                  </Link>
                  {isDeals && deals.length > 0 && (
                    <button
                      onClick={() => setDealsExpanded(!dealsExpanded)}
                      aria-label={dealsExpanded ? "Collapse deals" : "Expand deals"}
                      className={cn(
                        "ml-1 p-1.5 rounded-md transition-colors",
                        isDark
                          ? "text-white/35 hover:text-white/70 hover:bg-white/[0.04]"
                          : "text-black/35 hover:text-black/70 hover:bg-black/[0.04]"
                      )}
                    >
                      <ChevronDown
                        className={cn("h-3.5 w-3.5 transition-transform", dealsExpanded && "rotate-180")}
                      />
                    </button>
                  )}
                </div>

                {isDeals && dealsExpanded && deals.length > 0 && (
                  <div
                    className={cn(
                      "ml-7 mt-1 mb-1 border-l pl-3",
                      isDark ? "border-white/5" : "border-black/[0.06]"
                    )}
                  >
                    <div className="flex flex-col gap-0.5 max-h-[calc(100vh-26rem)] overflow-y-auto pr-1">
                      {deals.map((deal) => {
                        const dealPath = `/deals/${deal.id}`;
                        const isDealActive = pathname.startsWith(dealPath);
                        return (
                          <Link
                            key={deal.id}
                            href={dealPath}
                            className={cn(
                              "block truncate rounded-md px-2.5 py-1.5 text-[12px] transition-colors",
                              isDealActive
                                ? isDark
                                  ? "text-white bg-white/[0.04] font-medium"
                                  : "text-black bg-black/[0.04] font-medium"
                                : isDark
                                ? "text-white/45 hover:text-white/80 hover:bg-white/[0.03]"
                                : "text-black/50 hover:text-black/85 hover:bg-black/[0.03]"
                            )}
                            title={deal.name}
                          >
                            {deal.name}
                          </Link>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </nav>

      <div className={cn("p-4 border-t", isDark ? "border-white/5" : "border-black/[0.06]")}>
        <div
          className={cn(
            "flex items-center gap-2 px-3 py-2 rounded-lg border",
            isDark ? "bg-white/[0.02] border-white/5" : "bg-[#fafafa] border-black/[0.05]"
          )}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 breathe"></span>
          <span
            className={cn(
              "font-mono text-[10px] uppercase tracking-[0.22em]",
              isDark ? "text-white/45" : "text-black/45"
            )}
          >
            All systems operational
          </span>
        </div>
      </div>
    </aside>
  );
}
