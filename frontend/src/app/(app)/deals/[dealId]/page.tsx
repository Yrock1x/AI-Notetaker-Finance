"use client";

import { useParams } from "next/navigation";
import { useDeal } from "@/hooks/use-deals";
import { useMeetings } from "@/hooks/use-meetings";
import { LoadingState } from "@/components/shared/loading-state";
import { DEAL_STATUS_LABELS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { Calendar, FileText, Users } from "lucide-react";

const STATUS_COLORS: Record<string, string> = {
  active: "bg-green-100 text-green-800",
  on_hold: "bg-yellow-100 text-yellow-800",
  closed_won: "bg-blue-100 text-blue-800",
  closed_lost: "bg-red-100 text-red-800",
  archived: "bg-gray-100 text-gray-800",
};

export default function DealOverviewPage() {
  const params = useParams<{ dealId: string }>();
  const { data: deal, isLoading } = useDeal(params.dealId);
  const { data: meetingsData } = useMeetings(params.dealId);

  if (isLoading || !deal) {
    return <LoadingState message="Loading deal..." />;
  }

  const meetings = meetingsData?.items ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">{deal.name}</h1>
          <p className="mt-1 text-muted-foreground">{deal.target_company}</p>
        </div>
        <span
          className={cn(
            "rounded-full px-3 py-1 text-sm font-medium",
            STATUS_COLORS[deal.status] ?? "bg-gray-100 text-gray-800"
          )}
        >
          {DEAL_STATUS_LABELS[deal.status] ?? deal.status}
        </span>
      </div>

      {deal.description && (
        <p className="text-sm text-muted-foreground">{deal.description}</p>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-lg border bg-white p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Calendar className="h-4 w-4" />
            <span>Meetings</span>
          </div>
          <p className="mt-1 text-2xl font-bold">{meetings.length}</p>
        </div>
        <div className="rounded-lg border bg-white p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <FileText className="h-4 w-4" />
            <span>Documents</span>
          </div>
          <p className="mt-1 text-2xl font-bold">—</p>
        </div>
        <div className="rounded-lg border bg-white p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Users className="h-4 w-4" />
            <span>Team Members</span>
          </div>
          <p className="mt-1 text-2xl font-bold">—</p>
        </div>
      </div>

      {deal.stage && (
        <div className="text-sm">
          <span className="text-muted-foreground">Stage:</span>{" "}
          <span className="font-medium">{deal.stage}</span>
        </div>
      )}

      <div className="text-sm">
        <span className="text-muted-foreground">Created:</span>{" "}
        <span className="font-medium">
          {new Date(deal.created_at).toLocaleDateString()}
        </span>
      </div>
    </div>
  );
}
