"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Briefcase,
  Calendar,
  Plug,
  Shield,
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

  return (
    <aside className="flex w-72 flex-col border-r border-[#1A1A1A]/5 bg-white h-screen transition-all shadow-sm relative z-30 antialiased">
      <div className="flex h-24 items-center px-10">
        <Link href="/dashboard" className="text-xl font-heading font-extrabold tracking-tight text-primary uppercase">
          Deal Companion
        </Link>
      </div>
      <nav className="flex-1 space-y-2 p-6">
        <p className="px-4 text-[10px] font-data font-bold uppercase tracking-[0.2em] text-[#1A1A1A]/30 mb-4">Navigation Protocol</p>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "group flex items-center gap-4 rounded-full px-5 py-4 text-sm font-subheading font-bold transition-all duration-300 relative overflow-hidden",
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
