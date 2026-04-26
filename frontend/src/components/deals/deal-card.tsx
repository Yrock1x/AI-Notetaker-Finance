"use client";

import type { Deal } from "@/types";
import { DEAL_STATUS_LABELS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { ArrowRight } from "lucide-react";
import { useScribeTheme } from "@/components/cogniscribe/theme-provider";

interface DealCardProps {
  deal: Deal;
}

const STATUS_TONE: Record<string, { dotCls: string; textDark: string; textLight: string; bgDark: string; bgLight: string; borderDark: string; borderLight: string }> = {
  active: {
    dotCls: "bg-emerald-400",
    textDark: "text-emerald-300",
    textLight: "text-emerald-700",
    bgDark: "bg-emerald-500/10",
    bgLight: "bg-emerald-50",
    borderDark: "border-emerald-500/25",
    borderLight: "border-emerald-200/70",
  },
  archived: {
    dotCls: "bg-slate-400",
    textDark: "text-slate-300",
    textLight: "text-slate-600",
    bgDark: "bg-slate-500/10",
    bgLight: "bg-slate-50",
    borderDark: "border-slate-500/25",
    borderLight: "border-slate-200/70",
  },
};

const DEAL_TYPE_LABELS: Record<string, string> = {
  buyout: "Buyout",
  growth_equity: "Growth equity",
  venture: "Venture",
  recapitalization: "Recapitalization",
  add_on: "Add-on",
  other: "Other",
};

export function DealCard({ deal }: DealCardProps) {
  const { isDark } = useScribeTheme();
  const tone = STATUS_TONE[deal.status] ?? STATUS_TONE.active;

  return (
    <div
      className={cn(
        "group rounded-2xl border p-5 transition-colors h-full flex flex-col justify-between shadow-sm hover:shadow-lg",
        isDark
          ? "border-white/10 bg-[#121212] hover:border-white/20"
          : "border-black/[0.06] bg-white hover:border-black/15"
      )}
    >
      <div className="flex flex-col gap-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <h3
              className={cn(
                "text-[18px] leading-tight font-medium tracking-[-0.01em] truncate",
                isDark ? "text-white/95" : "text-black/90"
              )}
            >
              {deal.name}
            </h3>
            <p
              className={cn(
                "text-[12px] mt-1 truncate font-mono uppercase tracking-[0.18em]",
                isDark ? "text-white/40" : "text-black/40"
              )}
            >
              {deal.target_company}
            </p>
          </div>
          <div
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[10px] font-medium border",
              isDark
                ? `${tone.bgDark} ${tone.textDark} ${tone.borderDark}`
                : `${tone.bgLight} ${tone.textLight} ${tone.borderLight}`
            )}
          >
            <span className={cn("w-1.5 h-1.5 rounded-full", tone.dotCls)}></span>
            {DEAL_STATUS_LABELS[deal.status] ?? deal.status}
          </div>
        </div>

        <div className="flex flex-wrap gap-1.5">
          {deal.deal_type && (
            <span
              className={cn(
                "px-2 py-0.5 rounded-md text-[10px] font-mono",
                isDark ? "bg-white/5 text-white/55" : "bg-black/[0.04] text-black/55"
              )}
            >
              {DEAL_TYPE_LABELS[deal.deal_type] ?? deal.deal_type}
            </span>
          )}
          {deal.stage && (
            <span
              className={cn(
                "px-2 py-0.5 rounded-md text-[10px] font-mono",
                isDark ? "bg-white/5 text-white/55" : "bg-black/[0.04] text-black/55"
              )}
            >
              {deal.stage}
            </span>
          )}
        </div>
      </div>

      <div
        className={cn(
          "mt-6 pt-4 border-t flex items-center justify-between transition-colors",
          isDark ? "border-white/5" : "border-black/[0.06]"
        )}
      >
        <span
          className={cn(
            "font-mono text-[10px] uppercase tracking-[0.22em]",
            isDark ? "text-white/35" : "text-black/35"
          )}
        >
          Open deal
        </span>
        <ArrowRight
          className={cn(
            "w-4 h-4 transition-transform group-hover:translate-x-0.5",
            isDark ? "text-white/40" : "text-black/40"
          )}
        />
      </div>
    </div>
  );
}
