"use client";

// Deal Overview — top-level workspace page. Owns the data fetching and maps
// the design's six blocks onto live worker data; the cards themselves live
// in components/deals/overview-cards.tsx.

import { useParams } from "next/navigation";
import { useDeal } from "@/hooks/use-deals";
import { isBotSessionLive } from "@/lib/meeting-status";
import { useMeetings } from "@/hooks/use-meetings";
import { useDealStats } from "@/hooks/use-deal-stats";
import { useDealExtractions } from "@/hooks/use-deal-extractions";
import { useBotSessions } from "@/hooks/use-bot-sessions";
import { LoadingState } from "@/components/shared/loading-state";
import {
  ActionsCard,
  ExtractionsCard,
  ProjectPulse,
  RecentMeetings,
  StatsRow,
  UpcomingCard,
} from "@/components/deals/overview-cards";

export default function DealOverviewPage() {
  const params = useParams<{ dealId: string }>();
  const dealId = params.dealId;
  const { data: deal, isLoading: dealLoading } = useDeal(dealId);
  const { data: meetingsResp, isLoading: meetingsLoading } = useMeetings(dealId);
  const { data: stats } = useDealStats(dealId);
  const { data: extractions } = useDealExtractions(dealId);
  const { data: sessions } = useBotSessions({ deal_id: dealId });

  if (dealLoading || !deal) {
    return (
      <div className="px-7 py-6">
        <LoadingState message="Loading deal…" />
      </div>
    );
  }

  const meetings = meetingsResp?.items ?? [];
  const now = Date.now();
  const upcoming = meetings
    .filter((m) => {
      const t = m.meeting_date ? Date.parse(m.meeting_date) : 0;
      return m.status === "scheduled" && t > now;
    })
    .sort(
      (a, b) =>
        Date.parse(a.meeting_date || a.created_at) -
        Date.parse(b.meeting_date || b.created_at),
    )
    .slice(0, 4);

  const recent = meetings
    .filter((m) => m.status !== "scheduled" && m.status !== "recording")
    .slice(0, 6);

  const isLive = sessions?.some(isBotSessionLive);

  return (
    <div
      className="flex flex-col gap-4 px-7 pt-4 pb-10"
      style={{ background: "var(--ws-sub)", minHeight: "100%" }}
    >
      <StatsRow stats={stats} totalActions={extractions?.actions.length ?? 0} totalDecisions={extractions?.decisions.length ?? 0} totalQuestions={extractions?.questions.length ?? 0} liveCount={isLive ? 1 : 0} />

      <ProjectPulse
        dealId={dealId}
        meetingsCount={meetings.length}
        actionCount={extractions?.actions.length ?? 0}
        decisionCount={extractions?.decisions.length ?? 0}
      />

      <div className="grid grid-cols-1 lg:grid-cols-[1.3fr_1fr] gap-4">
        <RecentMeetings dealId={dealId} meetings={recent} loading={meetingsLoading} />

        <div className="flex flex-col gap-4">
          <UpcomingCard upcoming={upcoming} dealId={dealId} />
          <ActionsCard actions={extractions?.actions ?? []} dealId={dealId} />
          <ExtractionsCard
            decisions={extractions?.decisions ?? []}
            questions={extractions?.questions ?? []}
            dealId={dealId}
          />
        </div>
      </div>
    </div>
  );
}
