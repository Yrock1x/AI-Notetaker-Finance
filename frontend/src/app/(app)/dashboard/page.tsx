"use client";

import Link from "next/link";
import { useMemo } from "react";
import { ArrowRight, Briefcase, CalendarDays, Mic } from "lucide-react";
import { useDeals } from "@/hooks/use-deals";
import { useCalendarMeetings } from "@/hooks/use-calendar";
import { useBotSessions } from "@/hooks/use-bot-sessions";
import { EmptyState } from "@/components/shared/empty-state";
import { HeroSearch } from "@/components/dashboard/hero-search";
import { TodayAgenda } from "@/components/dashboard/today-agenda";
import { NeedsAttention } from "@/components/dashboard/needs-attention";
import { RecentActivity } from "@/components/dashboard/recent-activity";
import { DealStatus } from "@/types";
import { useScribeTheme } from "@/components/cogniscribe/theme-provider";
import { Eyebrow } from "@/components/cogniscribe/primitives";

function StatPill({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
}) {
  const { isDark } = useScribeTheme();
  return (
    <div
      className={`flex items-center gap-3 rounded-xl border px-4 py-3 ${
        isDark
          ? "bg-[#121212] border-white/10"
          : "bg-white border-black/[0.06]"
      }`}
    >
      <div
        className={`flex h-8 w-8 items-center justify-center rounded-lg ${
          isDark ? "bg-white/[0.05] text-white/70" : "bg-black/[0.04] text-black/70"
        }`}
      >
        {icon}
      </div>
      <div className="flex flex-col">
        <span
          className={`text-[10px] font-medium tracking-[0.18em] uppercase ${
            isDark ? "text-white/45" : "text-black/45"
          }`}
        >
          {label}
        </span>
        <span className="font-display text-2xl tabular-nums leading-tight">{value}</span>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { isDark } = useScribeTheme();
  const { data: dealsData, isLoading: dealsLoading } = useDeals();
  const { meetings } = useCalendarMeetings();
  const { data: botSessions = [] } = useBotSessions();

  const deals = dealsData?.items ?? [];
  const activeDeals = deals.filter((d) => d.status === DealStatus.ACTIVE);

  const meetingsThisWeek = useMemo(() => {
    const start = new Date();
    start.setHours(0, 0, 0, 0);
    start.setDate(start.getDate() - start.getDay());
    const ms = start.getTime();
    return meetings.filter((m) => {
      const t = m.meeting_date ? new Date(m.meeting_date).getTime() : 0;
      return t >= ms;
    }).length;
  }, [meetings]);

  const liveNow = botSessions.filter((b) => b.status === "recording").length;

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-3">
        <Eyebrow>Workspace</Eyebrow>
        <h1 className="text-[40px] sm:text-[52px] leading-[1] tracking-[-0.025em] font-medium">
          Dashboard
        </h1>
      </div>

      <HeroSearch />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <StatPill
          icon={<Briefcase className="h-4 w-4" />}
          label="Active deals"
          value={activeDeals.length}
        />
        <StatPill
          icon={<CalendarDays className="h-4 w-4" />}
          label="Meetings this week"
          value={meetingsThisWeek}
        />
        <StatPill
          icon={<Mic className="h-4 w-4" />}
          label="Live now"
          value={liveNow}
        />
      </div>

      <TodayAgenda />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <NeedsAttention />
        <RecentActivity />
      </div>

      <div className="flex flex-col gap-4">
        <div
          className={`flex items-end justify-between border-b pb-3 ${
            isDark ? "border-white/5" : "border-black/[0.06]"
          }`}
        >
          <div className="flex items-center gap-3">
            <Eyebrow>Pipeline</Eyebrow>
            <h2 className="text-[18px] tracking-[-0.01em] font-medium">Recent deals</h2>
          </div>
          <Link
            href="/deals"
            className={`group flex items-center gap-1.5 text-[12.5px] font-medium ${
              isDark ? "text-white/65 hover:text-white" : "text-black/65 hover:text-black"
            }`}
          >
            View all deals
            <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>

        {dealsLoading ? (
          <div className={`text-sm ${isDark ? "text-white/40" : "text-black/40"}`}>Loading…</div>
        ) : deals.length === 0 ? (
          <EmptyState
            title="No deals yet"
            description="Create your first deal to start recording meetings and generating AI-powered insights."
            action={
              <Link
                href="/deals/new"
                className={`inline-flex items-center gap-2 h-10 px-5 rounded-full text-[13px] font-medium ${
                  isDark
                    ? "bg-white text-[#0a0a0a] hover:bg-white/90"
                    : "bg-[#0a0a0a] text-white hover:bg-black/90"
                }`}
              >
                Create deal <ArrowRight className="w-4 h-4" />
              </Link>
            }
          />
        ) : (
          <div className="flex flex-wrap gap-2">
            {deals.slice(0, 8).map((deal) => (
              <Link
                key={deal.id}
                href={`/deals/${deal.id}`}
                className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-[13px] font-medium transition-colors ${
                  isDark
                    ? "border-white/10 text-white/85 hover:border-white/25 hover:bg-white/[0.04]"
                    : "border-black/10 text-black/85 hover:border-black/25 hover:bg-black/[0.03]"
                }`}
              >
                {deal.name}
                {deal.target_company && (
                  <span className={isDark ? "text-white/40" : "text-black/40"}>
                    · {deal.target_company}
                  </span>
                )}
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
