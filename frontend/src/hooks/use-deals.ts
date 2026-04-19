"use client";

// All deal CRUD runs client-side against Supabase via RLS — the worker no
// longer has deal endpoints. Org scoping happens automatically because RLS
// policies only return rows whose org_id is in `auth.user_org_ids()`.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  Deal,
  DealMember,
  DealCreate,
  DealUpdate,
  DealFilters,
  DealMemberAdd,
  PaginatedResponse,
} from "@/types";
import { getBrowserSupabase } from "@/lib/supabase/browser";

const DEALS_KEY = "deals";

export function useDeals(filters?: DealFilters) {
  return useQuery<PaginatedResponse<Deal>>({
    queryKey: [DEALS_KEY, filters],
    queryFn: async () => {
      const supabase = getBrowserSupabase();
      let query = supabase
        .from("deals")
        .select("*", { count: "exact" })
        .is("deleted_at", null)
        .order("created_at", { ascending: false });

      if (filters?.status) query = query.eq("status", filters.status);
      if (filters?.deal_type) query = query.eq("deal_type", filters.deal_type);
      if (filters?.search) {
        const s = filters.search.replace(/[%_]/g, (c) => `\\${c}`);
        query = query.or(
          `name.ilike.%${s}%,target_company.ilike.%${s}%`
        );
      }
      if (filters?.limit) query = query.limit(filters.limit);

      const { data, error, count } = await query;
      if (error) throw error;

      return {
        items: (data ?? []) as Deal[],
        cursor: null,
        has_more: false,
        total: count ?? undefined,
      };
    },
  });
}

export function useDeal(dealId: string | undefined) {
  return useQuery<Deal>({
    queryKey: [DEALS_KEY, dealId],
    queryFn: async () => {
      const supabase = getBrowserSupabase();
      const { data, error } = await supabase
        .from("deals")
        .select("*")
        .eq("id", dealId!)
        .single();
      if (error) throw error;
      return data as Deal;
    },
    enabled: !!dealId,
  });
}

export function useCreateDeal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: DealCreate) => {
      const supabase = getBrowserSupabase();
      const { data: user } = await supabase.auth.getUser();
      if (!user.user) throw new Error("Not authenticated");

      // Resolve the target org. Prefer the active selection from the org
      // switcher (localStorage), but fall back to a direct membership lookup
      // so a fresh browser or cleared cache doesn't error out — otherwise
      // /deals/new crashes if the user hits it before useOrgs has run.
      let orgId =
        typeof window !== "undefined" ? localStorage.getItem("org_id") : null;
      if (!orgId) {
        const { data: memberships, error: memErr } = await supabase
          .from("org_memberships")
          .select("org_id")
          .eq("user_id", user.user.id)
          .limit(1);
        if (memErr) throw memErr;
        orgId = memberships?.[0]?.org_id ?? null;
        if (orgId && typeof window !== "undefined") {
          localStorage.setItem("org_id", orgId);
        }
      }
      if (!orgId) throw new Error("No active organization");

      const { data, error } = await supabase
        .from("deals")
        .insert({
          org_id: orgId,
          created_by: user.user.id,
          ...payload,
        })
        .select()
        .single();
      if (error) throw error;
      return data as Deal;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [DEALS_KEY] });
    },
  });
}

export function useUpdateDeal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      dealId,
      payload,
    }: {
      dealId: string;
      payload: DealUpdate;
    }) => {
      const supabase = getBrowserSupabase();
      const { data, error } = await supabase
        .from("deals")
        .update(payload)
        .eq("id", dealId)
        .select()
        .single();
      if (error) throw error;
      return data as Deal;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: [DEALS_KEY, variables.dealId],
      });
      queryClient.invalidateQueries({ queryKey: [DEALS_KEY] });
    },
  });
}

export function useDeleteDeal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (dealId: string) => {
      const supabase = getBrowserSupabase();
      // Soft-delete: set deleted_at instead of actual DELETE, matching the
      // schema's `deleted_at` column.
      const { error } = await supabase
        .from("deals")
        .update({ deleted_at: new Date().toISOString() })
        .eq("id", dealId);
      if (error) throw error;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [DEALS_KEY] });
    },
  });
}

export function useDealMembers(dealId: string | undefined) {
  return useQuery<DealMember[]>({
    queryKey: [DEALS_KEY, dealId, "members"],
    queryFn: async () => {
      const supabase = getBrowserSupabase();
      const { data, error } = await supabase
        .from("deal_memberships")
        .select("id, deal_id, user_id, role, added_at, user:profiles(id, email, full_name, avatar_url)")
        .eq("deal_id", dealId!)
        .order("added_at", { ascending: true });
      if (error) throw error;
      return (data ?? []).map((m) => ({
        id: m.id,
        deal_id: m.deal_id,
        user_id: m.user_id,
        role: m.role,
        created_at: m.added_at,
        user: Array.isArray(m.user) ? m.user[0] : m.user,
      })) as DealMember[];
    },
    enabled: !!dealId,
  });
}

export function useAddDealMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      dealId,
      payload,
    }: {
      dealId: string;
      payload: DealMemberAdd;
    }) => {
      const supabase = getBrowserSupabase();
      const { data: auth } = await supabase.auth.getUser();
      if (!auth.user) throw new Error("Not authenticated");

      // Resolve email -> user_id via the profiles table (RLS-visible if the
      // invitee is already in one of the caller's orgs).
      let userId = payload.user_id;
      if (!userId && payload.email) {
        const { data: profileRows } = await supabase
          .from("profiles")
          .select("id")
          .eq("email", payload.email)
          .limit(1);
        if (profileRows && profileRows.length > 0) {
          userId = profileRows[0].id;
        } else {
          throw new Error(
            "User not found. Ask them to sign in once, then invite them."
          );
        }
      }
      if (!userId) throw new Error("user_id or email required");

      // Need org_id for deal_memberships FK; read it off the deal.
      const { data: dealRow, error: dealErr } = await supabase
        .from("deals")
        .select("org_id")
        .eq("id", dealId)
        .single();
      if (dealErr) throw dealErr;

      const { data, error } = await supabase
        .from("deal_memberships")
        .insert({
          deal_id: dealId,
          user_id: userId,
          org_id: dealRow.org_id,
          role: payload.role,
          added_by: auth.user.id,
        })
        .select()
        .single();
      if (error) throw error;
      return data as DealMember;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: [DEALS_KEY, variables.dealId, "members"],
      });
    },
  });
}

export function useRemoveDealMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      dealId,
      userId,
    }: {
      dealId: string;
      userId: string;
    }) => {
      const supabase = getBrowserSupabase();
      const { error } = await supabase
        .from("deal_memberships")
        .delete()
        .eq("deal_id", dealId)
        .eq("user_id", userId);
      if (error) throw error;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: [DEALS_KEY, variables.dealId, "members"],
      });
    },
  });
}
