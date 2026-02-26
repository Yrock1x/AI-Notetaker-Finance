"use client";

import { useDeals } from "@/hooks/use-deals";
import { useMeetings } from "@/hooks/use-meetings";
import { DealCard } from "@/components/deals/deal-card";
import { LoadingState } from "@/components/shared/loading-state";
import { EmptyState } from "@/components/shared/empty-state";
import { Briefcase, Calendar, FileText, TrendingUp } from "lucide-react";
import Link from "next/link";

export default function DashboardPage() {
  const { data: dealsData, isLoading: dealsLoading } = useDeals();

  const deals = dealsData?.items ?? [];
  const activeDeals = deals.filter((d) => d.status === "active");

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="mt-1 text-muted-foreground">
          Overview of your deal activity
        </p>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={<Briefcase className="h-5 w-5" />}
          label="Active Deals"
          value={activeDeals.length}
        />
        <StatCard
          icon={<Calendar className="h-5 w-5" />}
          label="Total Meetings"
          value="—"
        />
        <StatCard
          icon={<FileText className="h-5 w-5" />}
          label="Analyses"
          value="—"
        />
        <StatCard
          icon={<TrendingUp className="h-5 w-5" />}
          label="Documents"
          value="—"
        />
      </div>

      {/* Recent deals */}
      <div>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Recent Deals</h2>
          <Link
            href="/deals"
            className="text-sm text-primary hover:underline"
          >
            View all
          </Link>
        </div>

        {dealsLoading ? (
          <LoadingState message="Loading deals..." />
        ) : deals.length === 0 ? (
          <EmptyState
            title="No deals yet"
            description="Create your first deal to get started with meeting intelligence."
            action={
              <Link
                href="/deals/new"
                className="inline-flex items-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
              >
                Create Deal
              </Link>
            }
          />
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {deals.slice(0, 6).map((deal) => (
              <Link key={deal.id} href={`/deals/${deal.id}`}>
                <DealCard deal={deal} />
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
}) {
  return (
    <div className="rounded-lg border bg-white p-4">
      <div className="flex items-center gap-3">
        <div className="rounded-md bg-primary/10 p-2 text-primary">{icon}</div>
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="text-2xl font-bold">{value}</p>
        </div>
      </div>
    </div>
  );
}
