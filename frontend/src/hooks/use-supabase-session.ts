"use client";

// Thin React hook over the Supabase browser client's session. Replaces the
// old Zustand auth-store — the session lives in httpOnly cookies, and React
// components just subscribe to auth-state changes.

import { useCallback, useEffect, useState } from "react";
import type { Session, User } from "@supabase/supabase-js";
import { useQueryClient } from "@tanstack/react-query";
import { getBrowserSupabase } from "@/lib/supabase/browser";

export interface SupabaseSessionState {
  user: User | null;
  session: Session | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  signOut: () => Promise<void>;
}

export function useSupabaseSession(): SupabaseSessionState {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const queryClient = useQueryClient();

  useEffect(() => {
    const supabase = getBrowserSupabase();
    let mounted = true;

    supabase.auth.getSession().then(({ data }) => {
      if (!mounted) return;
      setSession(data.session);
      setUser(data.session?.user ?? null);
      setIsLoading(false);
    });

    const { data: sub } = supabase.auth.onAuthStateChange((event, newSession) => {
      setSession(newSession);
      setUser(newSession?.user ?? null);
      if (event === "SIGNED_OUT") {
        localStorage.removeItem("org_id");
        queryClient.clear();
      }
    });

    return () => {
      mounted = false;
      sub.subscription.unsubscribe();
    };
  }, [queryClient]);

  const signOut = useCallback(async () => {
    const supabase = getBrowserSupabase();
    await supabase.auth.signOut();
  }, []);

  return {
    user,
    session,
    isLoading,
    isAuthenticated: user !== null,
    signOut,
  };
}
