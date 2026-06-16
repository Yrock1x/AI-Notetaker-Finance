import { MutationCache, QueryClient } from "@tanstack/react-query";
import { toast } from "@/lib/toast-store";

export function createQueryClient(): QueryClient {
  return new QueryClient({
    // Surface mutation failures globally — these are always user-initiated
    // (upload, schedule, generate, send-event), so a silent failure is the
    // worst case (the row looks saved but nothing happened). Queries are left
    // to component-level isError handling to avoid noise from background
    // refetches.
    mutationCache: new MutationCache({
      onError: (error) => {
        toast.error(
          error instanceof Error && error.message
            ? error.message
            : "Something went wrong. Please try again."
        );
      },
    }),
    defaultOptions: {
      queries: {
        // Treat data as fresh for 30s — covers tab-switch round-trips
        // without re-fetching on every component mount.
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
