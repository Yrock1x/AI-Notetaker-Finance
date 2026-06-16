"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ArrowRight, Search } from "lucide-react";
import { useDeals } from "@/hooks/use-deals";
import { useCalendarMeetings } from "@/hooks/use-calendar";
import { EmptyState } from "@/components/shared/empty-state";
import { HeroSearch } from "@/components/dashboard/hero-search";
import { TodayAgenda } from "@/components/dashboard/today-agenda";
import { NeedsAttention } from "@/components/dashboard/needs-attention";
import { DealStatus } from "@/types";
import { useScribeTheme } from "@/components/cogniscribe/theme-provider";

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
  const [query, setQuery] = useState("");

  const deals = dealsData?.items ?? [];

  // Meeting count per deal, derived from the calendar feed we already load.
  const meetingCountByDeal = useMemo(() => {
    const map = new Map<string, number>();
    for (const m of meetings) {
      if (!m.deal_id) continue;
      map.set(m.deal_id, (map.get(m.deal_id) ?? 0) + 1);
    }
    return map;
  }, [meetings]);

  const filteredDeals = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return deals;
    return deals.filter(
      (d) =>
        d.name.toLowerCase().includes(q) ||
        (d.target_company ?? "").toLowerCase().includes(q),
    );
  }, [deals, query]);

  const dateLabel = new Date().toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  });

  return (
    <div className="flex flex-col gap-7">
      {/* Slim header */}
      <div className="flex flex-col gap-1">
        <p className={`text-[13px] ${isDark ? "text-white/45" : "text-black/45"}`}>
          {greeting()} · {dateLabel}
        </p>
        <h1 className="text-[26px] sm:text-[30px] leading-tight tracking-[-0.02em] font-medium">
          What do you want to know?
        </h1>
      </div>

      {/* Hero: ask across all deals */}
      <HeroSearch />

      {/* Today's calls — collapses when there are none */}
      <TodayAgenda />

      {/* Deal switcher — the primary way to move between deals */}
      <section className="flex flex-col gap-4">
        <div
          className={`flex items-center gap-3 flex-wrap border-b pb-3 ${
            isDark ? "border-white/5" : "border-black/[0.06]"
          }`}
        >
          <div className="flex items-center gap-3">
            <span className="inline-block h-3.5 w-1 rounded-full bg-gradient-to-b from-emerald-500 to-indigo-500" />
            <h2 className="text-[18px] tracking-[-0.01em] font-medium">Your deals</h2>
          </div>
          <div
            className={`ml-auto flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12.5px] ${
              isDark ? "border-white/10 bg-white/[0.03]" : "border-black/10 bg-white"
            }`}
          >
            <Search className={`h-3.5 w-3.5 ${isDark ? "text-white/40" : "text-black/40"}`} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Find a deal…"
              className={`w-40 bg-transparent outline-none ${
                isDark ? "text-white placeholder:text-white/30" : "text-black placeholder:text-black/30"
              }`}
            />
          </div>
          <Link
            href="/deals"
            className={`group flex items-center gap-1.5 text-[12.5px] font-medium ${
              isDark ? "text-white/65 hover:text-white" : "text-black/65 hover:text-black"
            }`}
          >
            View all
            <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>

        {dealsLoading ? (
          <div className={`text-sm ${isDark ? "text-white/40" : "text-black/40"}`}>Loading…</div>
        ) : deals.length === 0 ? (
          <EmptyState
            title="No deals yet"
            description="Create your first deal to start recording meetings and asking AI across your calls."
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
        ) : filteredDeals.length === 0 ? (
          <p className={`text-sm ${isDark ? "text-white/40" : "text-black/40"}`}>
            No deals match “{query}”.
          </p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {filteredDeals.map((deal) => {
              const count = meetingCountByDeal.get(deal.id) ?? 0;
              const isActive = deal.status === DealStatus.ACTIVE;
              return (
                <Link
                  key={deal.id}
                  href={`/deals/${deal.id}`}
                  className={`group rounded-2xl border p-4 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-sm ${
                    isDark
                      ? "border-white/10 bg-[#121212] hover:border-white/20"
                      : "border-black/[0.06] bg-white hover:border-black/15"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span
                          className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                            isActive ? "bg-emerald-500" : isDark ? "bg-white/25" : "bg-black/25"
                          }`}
                        />
                        <h3 className="truncate text-[15px] font-medium">{deal.name}</h3>
                      </div>
                      {deal.target_company && (
                        <p
                          className={`mt-0.5 truncate text-[12px] ${
                            isDark ? "text-white/45" : "text-black/45"
                          }`}
                        >
                          {deal.target_company}
                        </p>
                      )}
                    </div>
                    {deal.stage && (
                      <span
                        className={`shrink-0 rounded-full px-2 py-0.5 text-[10.5px] font-medium ${
                          isDark
                            ? "bg-indigo-500/10 text-indigo-300"
                            : "bg-indigo-50 text-indigo-600"
                        }`}
                      >
                        {deal.stage}
                      </span>
                    )}
                  </div>
                  <div
                    className={`mt-3 flex items-center justify-between text-[11.5px] ${
                      isDark ? "text-white/45" : "text-black/45"
                    }`}
                  >
                    <span className="tabular-nums">
                      {count} meeting{count === 1 ? "" : "s"}
                    </span>
                    <ArrowRight className="w-3.5 h-3.5 opacity-0 transition-all group-hover:translate-x-0.5 group-hover:opacity-100" />
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </section>

      {/* Small triage: meetings not yet assigned to a deal */}
      <NeedsAttention />
    </div>
  );
}
