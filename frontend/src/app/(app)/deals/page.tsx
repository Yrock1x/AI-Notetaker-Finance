"use client";

import { useState } from "react";
import Link from "next/link";
import { useDeals } from "@/hooks/use-deals";
import { DealCard } from "@/components/deals/deal-card";
import { LoadingState } from "@/components/shared/loading-state";
import { EmptyState } from "@/components/shared/empty-state";
import { DEAL_STATUS_LABELS } from "@/lib/constants";
import { DealStatus } from "@/types";
import { Plus, Search } from "lucide-react";

export default function DealsPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<DealStatus | "">("");

  const { data, isLoading } = useDeals({
    search: search || undefined,
    status: statusFilter || undefined,
  });

  const deals = data?.items ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Deals</h1>
          <p className="mt-1 text-muted-foreground">
            Manage your deal workspaces
          </p>
        </div>
        <Link
          href="/deals/new"
          className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          New Deal
        </Link>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search deals..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-md border bg-white py-2 pl-10 pr-4 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as DealStatus | "")}
          className="rounded-md border bg-white px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
        >
          <option value="">All Statuses</option>
          {Object.entries(DEAL_STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>

      {/* Deal grid */}
      {isLoading ? (
        <LoadingState message="Loading deals..." />
      ) : deals.length === 0 ? (
        <EmptyState
          title="No deals found"
          description={
            search || statusFilter
              ? "Try adjusting your filters."
              : "Create your first deal to get started."
          }
          action={
            !search && !statusFilter ? (
              <Link
                href="/deals/new"
                className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
              >
                <Plus className="h-4 w-4" />
                Create Deal
              </Link>
            ) : undefined
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {deals.map((deal) => (
            <Link key={deal.id} href={`/deals/${deal.id}`}>
              <DealCard deal={deal} />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
