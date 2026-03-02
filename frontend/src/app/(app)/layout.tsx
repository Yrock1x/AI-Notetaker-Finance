"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";
import { ErrorBoundary } from "@/components/shared/error-boundary";

function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { isAuthenticated, isLoading, initialize } = useAuthStore();

  useEffect(() => {
    initialize();
  }, [initialize]);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return <>{children}</>;
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <div className="relative flex h-screen bg-background overflow-hidden antialiased">
        <div className="noise-bg"></div>
        <Sidebar />
        <div className="flex flex-1 flex-col overflow-hidden relative z-10">
          <Topbar />
          <main className="flex-1 overflow-auto p-10 md:p-14">
            <ErrorBoundary>
              <div className="max-w-7xl mx-auto space-y-10">
                {children}
              </div>
            </ErrorBoundary>
          </main>
        </div>
      </div>
    </AuthGuard>
  );
}
