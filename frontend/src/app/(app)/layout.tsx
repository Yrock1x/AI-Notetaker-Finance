"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/hooks/use-session";
import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";
import { ErrorBoundary } from "@/components/shared/error-boundary";
import { useScribeTheme } from "@/components/cogniscribe/theme-provider";

function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useSession();
  const { isDark } = useScribeTheme();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading) {
    return (
      <div
        className={`flex h-screen items-center justify-center ${
          isDark ? "bg-[#0a0a0a] text-white/55" : "bg-[#fafafa] text-black/55"
        }`}
      >
        <p className="text-[13px] font-mono tracking-[0.22em] uppercase">Loading…</p>
      </div>
    );
  }

  if (!isAuthenticated) return null;
  return <>{children}</>;
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { isDark } = useScribeTheme();
  return (
    <AuthGuard>
      <div
        className={`relative flex h-screen overflow-hidden ${
          isDark ? "bg-[#0a0a0a] text-white" : "bg-[#fafafa] text-[#0a0a0a]"
        }`}
      >
        <Sidebar />
        <div className="flex flex-1 flex-col overflow-hidden relative z-10">
          <Topbar />
          <main className="flex-1 overflow-auto p-8 md:p-10">
            <ErrorBoundary>
              <div className="max-w-7xl mx-auto flex flex-col gap-10">{children}</div>
            </ErrorBoundary>
          </main>
        </div>
      </div>
    </AuthGuard>
  );
}
