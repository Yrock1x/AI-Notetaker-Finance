"use client";

import { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import { useDeals } from "@/hooks/use-deals";
import { DealCard } from "@/components/deals/deal-card";
import { LoadingState } from "@/components/shared/loading-state";
import { EmptyState } from "@/components/shared/empty-state";
import { DEAL_STATUS_LABELS } from "@/lib/constants";
import { DealStatus } from "@/types";
import { Plus, Search, Briefcase } from "lucide-react";
import { cn } from "@/lib/utils";

export default function DealsPage() {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<DealStatus | "">("");
  const [sideSearch, setSideSearch] = useState("");
  const [selectedDealId, setSelectedDealId] = useState<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const { data, isLoading } = useDeals({
    search: debouncedSearch || undefined,
    status: statusFilter || undefined,
  });
  const deals = data?.items ?? [];

  // Unfiltered list for the left-hand picker — so users can jump to any
  // deal regardless of the filters applied to the main grid.
  const { data: allDealsResp } = useDeals();
  const allDeals = allDealsResp?.items ?? [];

  const sidebarDeals = useMemo(() => {
    const q = sideSearch.trim().toLowerCase();
    if (!q) return allDeals;
    return allDeals.filter(
      (d) =>
        d.name.toLowerCase().includes(q) ||
        (d.target_company ?? "").toLowerCase().includes(q)
    );
  }, [allDeals, sideSearch]);

  const selectedDeal = allDeals.find((d) => d.id === selectedDealId);

  return (
    <div className="flex gap-6">
      {/* Left rail — deal picker, always visible on large screens */}
      <aside className="hidden lg:flex flex-col w-64 shrink-0 rounded-[2rem] border border-[#1A1A1A]/5 bg-white p-4 h-[calc(100vh-8rem)] sticky top-8">
        <div className="flex items-center gap-2 px-2 mb-3">
          <Briefcase className="h-4 w-4 text-[#1A1A1A]/40" />
          <h2 className="text-xs font-data uppercase tracking-widest text-[#1A1A1A]/40 font-bold">
            Your Deals
          </h2>
        </div>
        <div className="relative mb-3">
          <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Jump to deal…"
            value={sideSearch}
            onChange={(e) => setSideSearch(e.target.value)}
            className="w-full rounded-full border border-[#1A1A1A]/10 bg-[#F2F0E9]/40 py-2 pl-9 pr-3 text-xs focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </div>
        <div className="flex-1 overflow-y-auto pr-1 space-y-1">
          {sidebarDeals.length === 0 ? (
            <p className="px-2 py-4 text-xs text-[#1A1A1A]/30">
              {allDeals.length === 0 ? "No deals yet." : "No matches."}
            </p>
          ) : (
            sidebarDeals.map((d) => {
              const active = d.id === selectedDealId;
              return (
                <button
                  key={d.id}
                  onClick={() => setSelectedDealId(d.id)}
                  className={cn(
                    "w-full truncate rounded-xl px-3 py-2 text-left text-xs transition-colors",
                    active
                      ? "bg-accent/10 text-accent font-bold"
                      : "text-[#1A1A1A]/70 hover:bg-[#F2F0E9]/60"
                  )}
                  title={d.name}
                >
                  <div className="truncate font-medium">{d.name}</div>
                  {d.target_company && (
                    <div className="truncate text-[10px] text-[#1A1A1A]/40">
                      {d.target_company}
                    </div>
                  )}
                </button>
              );
            })
          )}
        </div>
        {selectedDeal && (
          <Link
            href={`/deals/${selectedDeal.id}`}
            className="mt-3 block rounded-full bg-primary px-4 py-2 text-center text-xs font-bold text-primary-foreground hover:opacity-90"
          >
            Open {selectedDeal.name}
          </Link>
        )}
      </aside>

      {/* Right side — existing grid + filters */}
      <div className="flex-1 space-y-6 min-w-0">
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

        {/* Mobile-only fallback: left rail hidden on small screens, so expose a dropdown */}
        <div className="lg:hidden">
          <select
            value={selectedDealId ?? ""}
            onChange={(e) => {
              const id = e.target.value;
              if (id) window.location.href = `/deals/${id}`;
            }}
            className="w-full rounded-md border bg-white px-3 py-2 text-sm"
          >
            <option value="">Jump to a deal…</option>
            {allDeals.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
                {d.target_company ? ` — ${d.target_company}` : ""}
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
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {deals.map((deal) => (
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
