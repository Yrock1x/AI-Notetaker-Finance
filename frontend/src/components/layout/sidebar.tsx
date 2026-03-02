"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useDeals } from "@/hooks/use-deals";
import {
  LayoutDashboard,
  Briefcase,
  Calendar,
  Plug,
  Shield,
  ChevronDown,
} from "lucide-react";

const navItems = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Deals", href: "/deals", icon: Briefcase },
  { label: "Calendar", href: "/calendar", icon: Calendar },
  { label: "Integrations", href: "/integrations", icon: Plug },
  { label: "Admin", href: "/admin", icon: Shield },
];

export function Sidebar() {
  const pathname = usePathname();
  const { data: dealsData } = useDeals();
  const deals = dealsData?.items ?? [];
  const [dealsExpanded, setDealsExpanded] = useState(true);

  return (
    <aside className="flex w-72 flex-col border-r border-[#1A1A1A]/5 bg-white h-screen transition-all shadow-sm relative z-30 antialiased">
      <div className="flex h-24 items-center px-10">
        <Link href="/dashboard" className="text-xl font-heading font-extrabold tracking-tight text-primary uppercase">
          Deal Companion
        </Link>
      </div>
      <nav className="flex-1 space-y-2 p-6 overflow-y-auto">
        <p className="px-4 text-[10px] font-data font-bold uppercase tracking-[0.2em] text-[#1A1A1A]/30 mb-4">Navigation Protocol</p>
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
                    "group flex flex-1 items-center gap-4 rounded-full px-5 py-4 text-sm font-subheading font-bold transition-all duration-300 relative overflow-hidden",
                    isActive
                      ? "bg-primary text-white shadow-lg shadow-primary/20"
                      : "text-[#1A1A1A]/60 hover:text-accent hover:bg-accent/5"
                  )}
                >
                  <Icon className={cn("h-5 w-5 transition-transform duration-300 group-hover:scale-110", isActive ? "text-white" : "text-[#1A1A1A]/30 group-hover:text-accent")} />
                  <span className="relative z-10">{item.label}</span>
                  {isActive && (
                    <div className="absolute right-3 w-1.5 h-1.5 rounded-full bg-accent animate-pulse"></div>
                  )}
                </Link>
                {isDeals && deals.length > 0 && (
                  <button
                    onClick={() => setDealsExpanded(!dealsExpanded)}
                    className="ml-1 p-2 rounded-full text-[#1A1A1A]/30 hover:text-[#1A1A1A]/60 hover:bg-[#F2F0E9] transition-colors"
                  >
                    <ChevronDown className={cn("h-4 w-4 transition-transform duration-200", dealsExpanded && "rotate-180")} />
                  </button>
                )}
              </div>

              {isDeals && dealsExpanded && deals.length > 0 && (
                <div className="ml-9 mt-1 mb-1 space-y-0.5 border-l border-[#1A1A1A]/5 pl-4">
                  {deals.slice(0, 10).map((deal) => {
                    const dealPath = `/deals/${deal.id}`;
                    const isDealActive = pathname.startsWith(dealPath);
                    return (
                      <Link
                        key={deal.id}
                        href={dealPath}
                        className={cn(
                          "block truncate rounded-lg px-3 py-2 text-xs font-medium transition-colors",
                          isDealActive
                            ? "text-accent bg-accent/5 font-bold"
                            : "text-[#1A1A1A]/40 hover:text-[#1A1A1A]/70 hover:bg-[#F2F0E9]"
                        )}
                        title={deal.name}
                      >
                        {deal.name}
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </nav>
      <div className="p-8 border-t border-[#1A1A1A]/5">
        <div className="flex items-center gap-3 bg-[#F2F0E9] px-4 py-3 rounded-2xl border border-[#1A1A1A]/5">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-[pulse_2s_infinite]"></div>
          <span className="font-data text-[10px] uppercase tracking-widest text-primary/60 font-bold">System Online</span>
        </div>
      </div>
    </aside>
  );
}
