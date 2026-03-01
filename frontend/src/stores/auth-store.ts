import { create } from "zustand";
import { QueryClient } from "@tanstack/react-query";
import type { User, AuthTokens } from "@/types";
import { getSupabase } from "@/lib/auth";

// Shared query client reference for cache clearing on logout
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

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  tokens: null,
  isAuthenticated: false,
  isLoading: true,

  initialize: () => {
    // If already authenticated (e.g., just logged in via demo), skip re-initialization
    const current = get();
    if (current.isAuthenticated && current.tokens) {
      if (current.isLoading) set({ isLoading: false });
      return;
    }

    const supabase = getSupabase();

    if (supabase) {
      // Supabase mode: listen for auth state changes and sync to localStorage
      supabase.auth.getSession().then(({ data: { session } }) => {
        if (session) {
          localStorage.setItem("access_token", session.access_token);
          localStorage.setItem("refresh_token", session.refresh_token);
          set({
            tokens: {
              access_token: session.access_token,
              refresh_token: session.refresh_token,
              expires_in: session.expires_in ?? 3600,
              token_type: session.token_type ?? "Bearer",
            },
            isAuthenticated: true,
            isLoading: false,
          });
        } else {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          localStorage.removeItem("org_id");
          set({ tokens: null, user: null, isAuthenticated: false, isLoading: false });
        }
      });

      // Keep localStorage in sync when Supabase refreshes tokens
      supabase.auth.onAuthStateChange((_event, session) => {
        if (session) {
          localStorage.setItem("access_token", session.access_token);
          localStorage.setItem("refresh_token", session.refresh_token);
          set({
            tokens: {
              access_token: session.access_token,
              refresh_token: session.refresh_token,
              expires_in: session.expires_in ?? 3600,
              token_type: session.token_type ?? "Bearer",
            },
            isAuthenticated: true,
          });
        } else {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          localStorage.removeItem("org_id");
          if (queryClientRef) {
            queryClientRef.clear();
          }
          set({ user: null, tokens: null, isAuthenticated: false });
        }
      });

      return;
    }

    // Fallback: localStorage-only mode (demo mode / no Supabase)
    const accessToken = localStorage.getItem("access_token");
    const refreshToken = localStorage.getItem("refresh_token");
    if (accessToken) {
      // Check if token looks valid (not expired)
      try {
        const payload = JSON.parse(atob(accessToken.split(".")[1]));
        if (payload.exp && payload.exp * 1000 > Date.now()) {
          set({
            tokens: {
              access_token: accessToken,
              refresh_token: refreshToken || "",
              expires_in: payload.exp ? payload.exp - Math.floor(Date.now() / 1000) : 3600,
              token_type: "Bearer",
            },
            isAuthenticated: true,
            isLoading: false,
          });
          return;
        }
      } catch {
        // Token is malformed, clear it
      }
    }
    // No valid token found
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("org_id");
    set({ tokens: null, user: null, isAuthenticated: false, isLoading: false });
  },

  login: (user: User, tokens: AuthTokens) => {
    if (typeof window !== "undefined") {
      localStorage.setItem("access_token", tokens.access_token);
      localStorage.setItem("refresh_token", tokens.refresh_token);
      if (user.org_id) {
        localStorage.setItem("org_id", user.org_id);
      }
    }
    set({ user, tokens, isAuthenticated: true, isLoading: false });
  },

  logout: () => {
    const supabase = getSupabase();
    if (supabase) {
      supabase.auth.signOut();
    }
    if (typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      localStorage.removeItem("org_id");
    }
    // Clear React Query cache on logout
    if (queryClientRef) {
      queryClientRef.clear();
    }
    set({ user: null, tokens: null, isAuthenticated: false, isLoading: false });
  },

  setUser: (user: User) => {
    set({ user, isAuthenticated: true });
  },

  setLoading: (loading: boolean) => {
    set({ isLoading: loading });
  },
}));
