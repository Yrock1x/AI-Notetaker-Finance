import { QueryClient } from "@tanstack/react-query";

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Treat data as fresh for 30s — covers tab-switch round-trips
        // without re-hammering Supabase on every component mount.
        staleTime: 30 * 1000,
        // Keep idle queries in cache for 10 min, then drop them. Default is
        // 5 min; bumping to 10 means a quick back-nav on the same deal/
        // meeting doesn't re-fetch. Memory ceiling: ~10k query entries per
        // tab is comfortable in modern browsers, and our queries are small.
        gcTime: 10 * 60 * 1000,
        retry: 1,
        refetchOnWindowFocus: false,
      },
      mutations: {
        retry: 0,
      },
    },
  });
}
