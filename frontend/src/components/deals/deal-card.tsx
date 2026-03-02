import type { Deal } from "@/types";
import { DEAL_STATUS_LABELS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { Briefcase, ArrowRight } from "lucide-react";

interface DealCardProps {
  deal: Deal;
}

const STATUS_COLORS: Record<string, { bg: string, text: string, dot: string }> = {
  active: { bg: "bg-emerald-50", text: "text-emerald-800", dot: "bg-emerald-500" },
  archived: { bg: "bg-slate-50", text: "text-slate-800", dot: "bg-slate-500" },
};

const DEAL_TYPE_LABELS: Record<string, string> = {
  buyout: "Buyout Protocol",
  growth_equity: "Growth Equity",
  venture: "Venture Layer",
  recapitalization: "Recapitization",
  add_on: "Strategic Add-on",
  other: "Other Protocol",
};

export function DealCard({ deal }: DealCardProps) {
  const status = STATUS_COLORS[deal.status] ?? STATUS_COLORS.active;

  return (
    <div className="group rounded-[2rem] border border-[#1A1A1A]/5 bg-white p-8 transition-all duration-300 hover:shadow-xl hover:-translate-y-1 relative overflow-hidden antialiased h-full flex flex-col justify-between">
      <div className="absolute top-0 left-0 w-2 h-full bg-primary/10"></div>

      <div className="space-y-6">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1.5 flex-1 min-w-0">
            <h3 className="font-heading font-extrabold text-lg md:text-xl leading-tight text-primary transition-colors group-hover:text-accent truncate">
              {deal.name}
            </h3>
            <p className="font-subheading text-sm text-[#1A1A1A]/40 font-medium truncate">
              {deal.target_company}
            </p>
          </div>
          <div className={cn("inline-flex items-center gap-2 rounded-full px-3 py-1 text-[10px] font-data font-bold uppercase tracking-wider", status.bg, status.text)}>
            <div className={cn("w-1.5 h-1.5 rounded-full animate-pulse", status.dot)}></div>
            {DEAL_STATUS_LABELS[deal.status] ?? deal.status}
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {deal.deal_type && (
            <div className="px-3 py-1 bg-[#F2F0E9] rounded-full text-[10px] font-data font-bold text-primary/40 uppercase tracking-widest border border-[#1A1A1A]/5">
              {DEAL_TYPE_LABELS[deal.deal_type] ?? deal.deal_type}
            </div>
          )}
          {deal.stage && (
            <div className="px-3 py-1 bg-[#F2F0E9] rounded-full text-[10px] font-data font-bold text-primary/40 uppercase tracking-widest border border-[#1A1A1A]/5">
              {deal.stage}
            </div>
          )}
        </div>
      </div>

      <div className="mt-8 pt-6 border-t border-[#1A1A1A]/5 flex items-center justify-between group-hover:border-accent/10 transition-colors">
        <span className="font-data text-[10px] text-primary/30 uppercase tracking-[0.2em] font-bold">Priority Status</span>
        <div className="w-8 h-8 rounded-full bg-[#F2F0E9] flex items-center justify-center transition-all group-hover:bg-accent group-hover:text-white">
          <ArrowRight className="w-4 h-4" />
        </div>
      </div>
    </div>
  );
}
