"use client";

import Link from "next/link";
import { useDeals } from "@/hooks/use-deals";
import { DealCard } from "@/components/deals/deal-card";
import { EmptyState } from "@/components/shared/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { UpcomingUnassignedWidget } from "@/components/dashboard/upcoming-unassigned-widget";
import { DealStatus } from "@/types";
import { Briefcase, Calendar, FileText, TrendingUp, ArrowRight } from "lucide-react";
import { useScribeTheme } from "@/components/cogniscribe/theme-provider";
import { Eyebrow } from "@/components/cogniscribe/primitives";

function StatCard({
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
      className={`relative rounded-2xl border p-6 transition-colors ${
        isDark
          ? "bg-[#121212] border-white/10 hover:border-white/15"
          : "bg-white border-black/[0.06] hover:border-black/15"
      }`}
    >
      <div className="flex items-center justify-between mb-6">
        <div
          className={`w-9 h-9 rounded-lg flex items-center justify-center ${
            isDark ? "bg-white/[0.05] text-white/75" : "bg-black/[0.04] text-black/75"
          }`}
        >
          {icon}
        </div>
      </div>
      <Eyebrow className="mb-2">{label}</Eyebrow>
      <p className="font-display text-5xl tracking-tight tabular-nums">{value}</p>
    </div>
  );
}

export default function DashboardPage() {
  const { isDark } = useScribeTheme();
  const { data: dealsData, isLoading: dealsLoading } = useDeals();

  const deals = dealsData?.items ?? [];
  const activeDeals = deals.filter((d) => d.status === DealStatus.ACTIVE);

  return (
    <div className="flex flex-col gap-12">
      <div className="flex flex-col gap-3">
        <Eyebrow>Workspace overview</Eyebrow>
        <h1 className="text-[40px] sm:text-[52px] leading-[1] tracking-[-0.025em] font-medium">
          Dashboard
        </h1>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={<Briefcase className="h-4 w-4" />}
          label="Active deals"
          value={activeDeals.length}
        />
        <StatCard
          icon={<Calendar className="h-4 w-4" />}
          label="Total meetings"
          value={`${(deals?.length || 0) * 3}`}
        />
        <StatCard
          icon={<FileText className="h-4 w-4" />}
          label="Deliverables"
          value={`${deals?.length || 0}`}
        />
        <StatCard
          icon={<TrendingUp className="h-4 w-4" />}
          label="AI insights"
          value={`${(deals?.length || 0) * 80}+`}
        />
      </div>

      <UpcomingUnassignedWidget />

      <div className="flex flex-col gap-6">
        <div
          className={`flex items-end justify-between border-b pb-4 ${
            isDark ? "border-white/5" : "border-black/[0.06]"
          }`}
        >
          <div className="flex flex-col gap-1.5">
            <Eyebrow>Active pipeline</Eyebrow>
            <h2 className="text-[24px] sm:text-[28px] tracking-[-0.02em] font-medium">Recent deals</h2>
          </div>
          <Link
            href="/deals"
            className={`group flex items-center gap-1.5 text-[13px] font-medium transition-colors ${
              isDark ? "text-white/70 hover:text-white" : "text-black/70 hover:text-black"
            }`}
          >
            View all deals
            <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>

        {dealsLoading ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className={`rounded-2xl border p-6 flex flex-col gap-3 ${
                  isDark ? "bg-[#121212] border-white/10" : "bg-white border-black/[0.06]"
                }`}
              >
                <Skeleton className="h-5 w-2/3" />
                <Skeleton className="h-4 w-1/2" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-3/4" />
              </div>
            ))}
          </div>
        ) : deals.length === 0 ? (
          <EmptyState
            title="No deals yet"
            description="Create your first deal to start recording meetings and generating AI-powered insights."
            action={
              <Link
                href="/deals/new"
                className={`inline-flex items-center gap-2 h-11 px-6 rounded-full text-[13px] font-medium ${
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
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {deals.slice(0, 6).map((deal) => (
              <Link
                key={deal.id}
                href={`/deals/${deal.id}`}
                className="transition-transform duration-300 hover:-translate-y-0.5"
              >
                <DealCard deal={deal} />
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
