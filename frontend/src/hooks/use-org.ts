"use client";

// Org list + switcher. RLS ensures we only see orgs we're a member of.
// useOrgs returns the list from Supabase. useOrg returns the resolved current
// org + switchOrg action. The selection lives in Zustand + localStorage; the
// data lives in React Query.

import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { Organization } from "@/types";
import { getBrowserSupabase } from "@/lib/supabase/browser";
import { useOrgSelection } from "@/stores/org-store";

interface MembershipRow {
  org_id: string;
  role: string;
  organization: {
    id: string;
    name: string;
    slug: string | null;
    domain: string | null;
    settings: Record<string, unknown> | null;
    created_at: string;
    updated_at: string;
  } | null;
}

// Queries that hold per-org data. switchOrg drops these to avoid showing the
// previous org's rows while the new org's queries refetch.
const ORG_SCOPED_KEYS = [
  "deals",
  "meetings",
  "documents",
  "analyses",
  "qa",
  "calendar",
  "bot-sessions",
  "deliverables",
  "transcripts",
];

export function useOrgs() {
  return useQuery<Organization[]>({
    queryKey: ["orgs"],
    queryFn: async () => {
      const supabase = getBrowserSupabase();
      const { data: auth } = await supabase.auth.getUser();
      if (!auth.user) return [];
      const { data, error } = await supabase
        .from("org_memberships")
        .select(
          "org_id, role, organization:organizations(id, name, slug, domain, settings, created_at, updated_at)"
        )
        .eq("user_id", auth.user.id)
        .returns<MembershipRow[]>();
      if (error) throw error;
      return (data ?? [])
        .map((row) => row.organization)
        .filter((o): o is NonNullable<MembershipRow["organization"]> => o !== null)
        .map((o) => ({
          id: o.id,
          name: o.name,
          slug: o.slug ?? "",
          settings: o.settings ?? {},
          created_at: o.created_at,
          updated_at: o.updated_at,
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
    for (const key of ORG_SCOPED_KEYS) {
      queryClient.removeQueries({ queryKey: [key] });
    }
  };

  return { currentOrg, orgs, switchOrg };
}
