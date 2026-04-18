"use client";

// Org list + switcher. The list comes straight from Supabase via a join
// through `org_memberships` — RLS ensures we only see orgs we're in.

import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { Organization } from "@/types";
import { getBrowserSupabase } from "@/lib/supabase/browser";
import { useOrgStore } from "@/stores/org-store";

type MembershipRow = {
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
};

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
        .eq("user_id", auth.user.id);
      if (error) throw error;
      return (data as unknown as MembershipRow[])
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
  const currentOrg = useOrgStore((s) => s.currentOrg);
  const setCurrentOrg = useOrgStore((s) => s.setCurrentOrg);
  const setOrgs = useOrgStore((s) => s.setOrgs);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (orgs.length === 0) return;
    setOrgs(orgs);
    if (!currentOrg) {
      const stored =
        typeof window !== "undefined" ? localStorage.getItem("org_id") : null;
      const match = stored ? orgs.find((o) => o.id === stored) : undefined;
      setCurrentOrg(match ?? orgs[0]);
    }
  }, [orgs, currentOrg, setOrgs, setCurrentOrg]);

  const switchOrg = (orgId: string) => {
    const next = orgs.find((o) => o.id === orgId);
    if (!next || next.id === currentOrg?.id) return;
    setCurrentOrg(next);
    // Drop per-tenant caches.
    queryClient.removeQueries({ queryKey: ["deals"] });
    queryClient.removeQueries({ queryKey: ["meetings"] });
    queryClient.removeQueries({ queryKey: ["documents"] });
    queryClient.removeQueries({ queryKey: ["analyses"] });
    queryClient.removeQueries({ queryKey: ["qa"] });
    queryClient.removeQueries({ queryKey: ["calendar"] });
  };

  return { currentOrg, orgs, setCurrentOrg, setOrgs, switchOrg };
}
