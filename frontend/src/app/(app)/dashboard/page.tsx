"use client";

import { useDeals } from "@/hooks/use-deals";
import { useMeetings } from "@/hooks/use-meetings";
import { DealCard } from "@/components/deals/deal-card";
import { LoadingState } from "@/components/shared/loading-state";
import { EmptyState } from "@/components/shared/empty-state";
import { DealStatus } from "@/types";
import { Briefcase, Calendar, FileText, TrendingUp, ArrowRight } from "lucide-react";
import Link from "next/link";

function StatCard({
  icon,
  label,
  value,
  trend,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  trend?: string;
}) {
  return (
    <div className="rounded-[2.5rem] border border-[#1A1A1A]/5 bg-white p-8 shadow-sm hover:shadow-md transition-all duration-300 group overflow-hidden relative">
      <div className="absolute top-0 right-0 w-32 h-32 bg-[#F2F0E9]/50 rounded-full translate-x-16 -translate-y-16 group-hover:scale-110 transition-transform duration-500"></div>
      <div className="relative z-10 flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <div className="rounded-2xl bg-primary text-white p-3 shadow-lg shadow-primary/20 transition-transform group-hover:scale-110 duration-300">
            {icon}
          </div>
          {trend && <div className="font-data text-[10px] text-accent font-bold uppercase tracking-widest bg-accent/5 px-3 py-1 rounded-full border border-accent/10">{trend}</div>}
        </div>
        <div>
          <p className="font-data text-[10px] uppercase tracking-widest text-[#1A1A1A]/40 font-bold mb-1">{label}</p>
          <p className="text-4xl font-heading font-extrabold text-[#1A1A1A] tracking-tighter">{value}</p>
        </div>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { data: dealsData, isLoading: dealsLoading } = useDeals();

  const deals = dealsData?.items ?? [];
  const activeDeals = deals.filter((d) => d.status === DealStatus.ACTIVE);

  return (
    <div className="space-y-12 antialiased">
      <div className="space-y-2">
        <h1 className="text-4xl font-heading font-extrabold tracking-tight text-primary uppercase">Executive Overview</h1>
        <p className="font-subheading text-[#1A1A1A]/60 text-lg font-medium leading-relaxed">
          Operational monitoring of active deal flow and pipeline velocity.
        </p>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={<Briefcase className="h-6 w-6" />}
          label="Active Protocols"
          value={activeDeals.length}
          trend="+2 New"
        />
        <StatCard
          icon={<Calendar className="h-6 w-6" />}
          label="Ingested Meetings"
          value={`${(deals?.length || 0) * 3}`}
          trend={`${(deals?.length || 0) * 3}h total`}
        />
        <StatCard
          icon={<FileText className="h-6 w-6" />}
          label="Generated Reports"
          value={`${deals?.length || 0}`}
          trend="Last: PitchDeck"
        />
        <StatCard
          icon={<TrendingUp className="h-6 w-6" />}
          label="Captured Insights"
          value={`${(deals?.length || 0) * 80}+`}
          trend="+12 today"
        />
      </div>

      {/* Recent deals */}
      <div className="space-y-8">
        <div className="flex items-end justify-between border-b border-[#1A1A1A]/5 pb-6">
          <div className="space-y-1">
            <h2 className="text-2xl font-heading font-bold text-primary">Recent Active Deals</h2>
            <p className="font-subheading text-xs uppercase tracking-widest text-[#1A1A1A]/40 font-bold">Priority Pipeline</p>
          </div>
          <Link
            href="/deals"
            className="group flex items-center gap-2 font-subheading text-sm font-bold text-accent hover:opacity-80 transition-all"
          >
            <span>View protocol archive</span>
            <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
          </Link>
        </div>

        {dealsLoading ? (
          <LoadingState message="Synchronizing deal data..." />
        ) : deals.length === 0 ? (
          <EmptyState
            title="Protocol inactive"
            description="Initialize your first deal workspace to begin meeting ingestion and intelligence mapping."
            action={
              <Link
                href="/deals/new"
                className="magnetic-btn inline-flex items-center rounded-[2rem] bg-accent px-8 py-4 text-sm font-heading font-bold text-white shadow-xl hover:shadow-accent/20"
              >
                Initialize Deal
              </Link>
            }
          />
        ) : (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
            {deals.slice(0, 6).map((deal) => (
              <Link key={deal.id} href={`/deals/${deal.id}`} className="transition-transform duration-300 hover:scale-[1.02]">
                <DealCard deal={deal} />
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
