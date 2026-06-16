"use client";

// Org list + switcher via the worker REST API (GET /orgs). The worker scopes
// to the caller's memberships. useOrgs returns the list; useOrg returns the
// resolved current org + switchOrg action. The selection lives in Zustand +
// localStorage; the data lives in React Query.

import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { Organization } from "@/types";
import { apiGet } from "@/lib/worker-api";
import { useOrgSelection } from "@/stores/org-store";

// Shape returned by GET /api/v1/orgs.
interface OrgResponse {
  id: string;
  name: string;
  slug: string;
  role: string;
}

// Query-key roots that are NOT org-scoped and must survive an org switch:
// the org list itself and the auth session. Everything else holds per-org data
// and is dropped on switch (see switchOrg). Using a denylist of global keys —
// rather than an allowlist of org-scoped ones — means a newly-added org-scoped
// hook is cleared automatically instead of silently leaking the previous org's
// rows until someone remembers to extend a list.
const GLOBAL_QUERY_KEYS = new Set(["orgs", "auth"]);

export function useOrgs() {
  return useQuery<Organization[]>({
    queryKey: ["orgs"],
    queryFn: async () => {
      const rows = await apiGet<OrgResponse[]>("/orgs");
      // The worker returns a slim shape; fill the remaining Organization
      // fields with defaults so the existing type/consumers are satisfied.
      return rows.map((o) => ({
        id: o.id,
        name: o.name,
        slug: o.slug ?? "",
        settings: {},
        created_at: "",
        updated_at: "",
      }));
    },
    staleTime: 5 * 60 * 1000,
  });
}

export function useOrg() {
  const { data: orgs = [] } = useOrgs();
  const currentOrgId = useOrgSelection((s) => s.currentOrgId);
  const setCurrentOrgId = useOrgSelection((s) => s.setCurrentOrgId);
  const queryClient = useQueryClient();

  const currentOrg = orgs.find((o) => o.id === currentOrgId) ?? null;

  // On first load, pick either the stored selection (if it's still in the
  // user's membership) or the first org.
  useEffect(() => {
    if (orgs.length === 0) return;
    if (currentOrg) return;
    setCurrentOrgId(orgs[0].id);
  }, [orgs, currentOrg, setCurrentOrgId]);

  const switchOrg = (orgId: string) => {
    if (!orgs.some((o) => o.id === orgId) || orgId === currentOrgId) return;
    setCurrentOrgId(orgId);
    // Drop every org-scoped query so the UI can't show the previous org's rows
    // while the new org refetches. Keep only the genuinely-global queries.
    queryClient.removeQueries({
      predicate: (query) => {
        const root = Array.isArray(query.queryKey) ? query.queryKey[0] : query.queryKey;
        return typeof root !== "string" || !GLOBAL_QUERY_KEYS.has(root);
      },
    });
  };

  return { currentOrg, orgs, switchOrg };
}
