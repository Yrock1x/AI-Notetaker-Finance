"use client";

import Link from "next/link";
import { useMemo } from "react";
import { ArrowRight, Briefcase, CalendarDays, Mic } from "lucide-react";
import { useDeals } from "@/hooks/use-deals";
import { isBotSessionLive } from "@/lib/meeting-status";
import { useCalendarMeetings } from "@/hooks/use-calendar";
import { useBotSessions } from "@/hooks/use-bot-sessions";
import { EmptyState } from "@/components/shared/empty-state";
import { HeroSearch } from "@/components/dashboard/hero-search";
import { TodayAgenda } from "@/components/dashboard/today-agenda";
import { NeedsAttention } from "@/components/dashboard/needs-attention";
import { RecentActivity } from "@/components/dashboard/recent-activity";
import { DealStatus } from "@/types";
import { useScribeTheme } from "@/components/cogniscribe/theme-provider";

type StatTone = "indigo" | "emerald" | "rose";

const STAT_TONE_LIGHT: Record<StatTone, { bg: string; text: string; ring: string }> = {
  indigo: { bg: "bg-indigo-50", text: "text-indigo-600", ring: "ring-indigo-100" },
  emerald: { bg: "bg-emerald-50", text: "text-emerald-600", ring: "ring-emerald-100" },
  rose: { bg: "bg-rose-50", text: "text-rose-600", ring: "ring-rose-100" },
};

const STAT_TONE_DARK: Record<StatTone, { bg: string; text: string; ring: string }> = {
  indigo: { bg: "bg-indigo-500/10", text: "text-indigo-300", ring: "ring-indigo-400/20" },
  emerald: { bg: "bg-emerald-500/10", text: "text-emerald-300", ring: "ring-emerald-400/20" },
  rose: { bg: "bg-rose-500/10", text: "text-rose-300", ring: "ring-rose-400/20" },
};

function StatPill({
  icon,
  label,
  value,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  tone: StatTone;
}) {
  const { isDark } = useScribeTheme();
  const c = isDark ? STAT_TONE_DARK[tone] : STAT_TONE_LIGHT[tone];
  return (
    <div
      className={`group flex items-center gap-3 rounded-2xl border px-4 py-3.5 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-sm ${
        isDark
          ? "bg-[#121212] border-white/10 hover:border-white/20"
          : "bg-white border-black/[0.06] hover:border-black/15"
      }`}
    >
      <div
        className={`flex h-10 w-10 items-center justify-center rounded-xl ring-4 transition-transform duration-300 group-hover:scale-105 ${c.bg} ${c.text} ${c.ring}`}
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
        <span className="font-display text-[28px] tabular-nums leading-tight">{value}</span>
      </div>
    </div>
  );
}

const DEAL_PILL_DOTS = ["bg-emerald-500", "bg-indigo-500", "bg-violet-500", "bg-amber-500"];

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
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

  const liveNow = botSessions.filter(isBotSessionLive).length;

  const dateLabel = new Date().toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  });

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-2">
        <p
          className={`font-display italic text-[20px] sm:text-[22px] leading-tight ${
            isDark ? "text-white/55" : "text-black/55"
          }`}
        >
          {greeting()},
        </p>
        <h1 className="text-[44px] sm:text-[60px] leading-[0.95] tracking-[-0.03em] font-medium">
          <span
            className={`bg-clip-text text-transparent ${
              isDark
                ? "bg-gradient-to-r from-white via-indigo-200 to-emerald-200"
                : "bg-gradient-to-r from-[#0a0a0a] via-indigo-700 to-emerald-700"
            }`}
          >
            Your workspace
          </span>
        </h1>
        <p className={`text-[13px] tracking-wide ${isDark ? "text-white/40" : "text-black/40"}`}>
          {dateLabel}
        </p>
      </div>

      <HeroSearch />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <StatPill
          icon={<Briefcase className="h-4 w-4" />}
          label="Active deals"
          value={activeDeals.length}
          tone="indigo"
        />
        <StatPill
          icon={<CalendarDays className="h-4 w-4" />}
          label="Meetings this week"
          value={meetingsThisWeek}
          tone="emerald"
        />
        <StatPill
          icon={<Mic className="h-4 w-4" />}
          label="Live now"
          value={liveNow}
          tone="rose"
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
            <span className="inline-block h-3.5 w-1 rounded-full bg-gradient-to-b from-emerald-500 to-indigo-500" />
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
            {deals.slice(0, 8).map((deal, i) => (
              <Link
                key={deal.id}
                href={`/deals/${deal.id}`}
                className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-[13px] font-medium transition-all duration-200 hover:-translate-y-0.5 ${
                  isDark
                    ? "border-white/10 text-white/85 hover:border-white/25 hover:bg-white/[0.04]"
                    : "border-black/10 text-black/85 hover:border-black/25 hover:bg-black/[0.03]"
                }`}
              >
                <span className={`h-1.5 w-1.5 rounded-full ${DEAL_PILL_DOTS[i % DEAL_PILL_DOTS.length]}`} />
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
