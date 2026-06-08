"use client";

// Session hook — now backed by the worker's GET /auth/session endpoint
// (cookie-authenticated) instead of supabase.auth. Kept under the original
// filename + export name so consumers don't change.
//
// TODO: remove once all consumers migrated — this file no longer touches
// src/lib/supabase/*.

import { useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, ApiError } from "@/lib/worker-api";
import { signOut as workerSignOut } from "@/lib/auth";

// Shape returned by GET /api/v1/auth/session.
export interface SessionUser {
  id: string;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
}

export interface SupabaseSessionState {
  user: SessionUser | null;
  // Retained for source compatibility; the worker session is cookie-based so
  // there's no client-visible session object anymore.
  session: null;
  isLoading: boolean;
  isAuthenticated: boolean;
  signOut: () => Promise<void>;
}

const SESSION_KEY = ["auth", "session"];

export function userDisplayName(user: SessionUser | null): string {
  if (!user) return "";
  if (user.full_name && user.full_name.trim()) return user.full_name.trim();
  return user.email ? user.email.split("@")[0] : "";
}

export function useSupabaseSession(): SupabaseSessionState {
  const queryClient = useQueryClient();

  const query = useQuery<SessionUser | null>({
    queryKey: SESSION_KEY,
    queryFn: async () => {
      try {
        return await apiGet<SessionUser>("/auth/session");
      } catch (e) {
        // 401 = not signed in: treat as null rather than an error so the
        // AuthGuard can redirect cleanly.
        if (e instanceof ApiError && e.status === 401) return null;
        throw e;
      }
    },
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const signOut = useCallback(async () => {
    await workerSignOut();
    queryClient.setQueryData(SESSION_KEY, null);
    queryClient.clear();
  }, [queryClient]);

  const user = query.data ?? null;

  return {
    user,
    session: null,
    isLoading: query.isLoading,
    isAuthenticated: user !== null,
    signOut,
  };
}
