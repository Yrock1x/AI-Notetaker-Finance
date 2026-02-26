import type { Deal } from "@/types";
import { DEAL_STATUS_LABELS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { Briefcase } from "lucide-react";

interface DealCardProps {
  deal: Deal;
}

const STATUS_COLORS: Record<string, string> = {
  active: "bg-green-100 text-green-800",
  on_hold: "bg-yellow-100 text-yellow-800",
  closed_won: "bg-blue-100 text-blue-800",
  closed_lost: "bg-red-100 text-red-800",
  archived: "bg-gray-100 text-gray-800",
};

const DEAL_TYPE_LABELS: Record<string, string> = {
  buyout: "Buyout",
  growth_equity: "Growth Equity",
  venture: "Venture",
  recapitalization: "Recap",
  add_on: "Add-on",
  other: "Other",
};

export function DealCard({ deal }: DealCardProps) {
  return (
    <div className="group rounded-lg border bg-white p-4 transition-shadow hover:shadow-md">
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3">
          <div className="rounded-md bg-primary/10 p-2 text-primary">
            <Briefcase className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <h3 className="font-semibold leading-tight group-hover:text-primary">
              {deal.name}
            </h3>
            <p className="mt-0.5 text-sm text-muted-foreground truncate">
              {deal.target_company}
            </p>
          </div>
        </div>
        <span
          className={cn(
            "inline-flex shrink-0 rounded-full px-2 py-0.5 text-xs font-medium",
            STATUS_COLORS[deal.status] ?? "bg-gray-100 text-gray-800"
          )}
        >
          {DEAL_STATUS_LABELS[deal.status] ?? deal.status}
        </span>
      </div>

      <div className="mt-3 flex items-center gap-3 text-xs text-muted-foreground">
        {deal.deal_type && (
          <span>{DEAL_TYPE_LABELS[deal.deal_type] ?? deal.deal_type}</span>
        )}
        {deal.stage && (
          <>
            <span>·</span>
            <span>{deal.stage}</span>
          </>
        )}
      </div>
    </div>
  );
}
