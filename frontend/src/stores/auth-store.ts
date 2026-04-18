"use client";

// Thin compatibility shim over Supabase Auth. The source of truth is the
// Supabase session cookie (managed by @supabase/ssr). This store mirrors
// that state into a Zustand store so existing consumers (topbar, layouts,
// settings page, etc.) keep working without a rewrite.

import { create } from "zustand";
import { QueryClient } from "@tanstack/react-query";
import type { User, AuthTokens } from "@/types";
import { getBrowserSupabase } from "@/lib/supabase/browser";

let queryClientRef: QueryClient | null = null;

export function setQueryClientRef(qc: QueryClient) {
  queryClientRef = qc;
}

interface AuthState {
  user: User | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  initialize: () => void;
  login: (user: User, tokens: AuthTokens) => void;
  logout: () => void;
  setUser: (user: User) => void;
  setLoading: (loading: boolean) => void;
}

let listenerWired = false;

function mapSupabaseUser(
  sbUser: { id: string; email?: string | null; user_metadata?: Record<string, unknown> } | null,
  orgId: string | null
): User | null {
  if (!sbUser) return null;
  const meta = sbUser.user_metadata || {};
  return {
    id: sbUser.id,
    email: sbUser.email ?? "",
    full_name:
      (meta.full_name as string) ||
      (meta.name as string) ||
      (sbUser.email ? sbUser.email.split("@")[0] : ""),
    avatar_url: meta.avatar_url as string | undefined,
    org_id: orgId ?? "",
    role: "member",
    is_active: true,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  tokens: null,
  isAuthenticated: false,
  isLoading: true,

  initialize: () => {
    if (listenerWired) return;
    listenerWired = true;

    const supabase = getBrowserSupabase();
    const orgId =
      typeof window !== "undefined" ? localStorage.getItem("org_id") : null;

    supabase.auth.getSession().then(({ data: { session } }) => {
      set({
        user: mapSupabaseUser(session?.user ?? null, orgId),
        tokens: session
          ? {
              access_token: session.access_token,
              refresh_token: "",
              expires_in: session.expires_in ?? 3600,
              token_type: session.token_type ?? "Bearer",
            }
          : null,
        isAuthenticated: !!session,
        isLoading: false,
      });
    });

    supabase.auth.onAuthStateChange((event, session) => {
      const currentOrg =
        typeof window !== "undefined" ? localStorage.getItem("org_id") : null;
      if (event === "SIGNED_OUT") {
        localStorage.removeItem("org_id");
        if (queryClientRef) queryClientRef.clear();
        set({ user: null, tokens: null, isAuthenticated: false });
        return;
      }
      set({
        user: mapSupabaseUser(session?.user ?? null, currentOrg),
        tokens: session
          ? {
              access_token: session.access_token,
              refresh_token: "",
              expires_in: session.expires_in ?? 3600,
              token_type: session.token_type ?? "Bearer",
            }
          : null,
        isAuthenticated: !!session,
      });
    });
  },

  // `login` is kept for API shape compatibility, but Supabase owns the
  // session — callers just update local profile bits.
  login: (user, tokens) => {
    if (typeof window !== "undefined" && user.org_id) {
      localStorage.setItem("org_id", user.org_id);
    }
    set({ user, tokens, isAuthenticated: true, isLoading: false });
  },

  logout: () => {
    const supabase = getBrowserSupabase();
    supabase.auth.signOut().catch(() => {});
    if (typeof window !== "undefined") {
      localStorage.removeItem("org_id");
    }
    if (queryClientRef) queryClientRef.clear();
    set({ user: null, tokens: null, isAuthenticated: false, isLoading: false });
  },

  setUser: (user) => set({ user, isAuthenticated: true }),
  setLoading: (loading) => set({ isLoading: loading }),
}));
