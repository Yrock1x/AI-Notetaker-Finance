"use client";

// A compact, always-visible CogniVault entry point for the deal header (it
// renders inside the deal workspace shell, so it persists across all tabs).
// Not connected → a "Connect to CogniVault" button that kicks off the OAuth
// flow; connected → a status chip linking to Settings, where the share-scope
// toggles (the full CogniVaultShareCard) live. Reuses the existing hooks so
// there is one connection source of truth.

import Link from "next/link";
import { Database } from "lucide-react";
import { useVdrConnection, useConnectVdr } from "@/hooks/use-cognivault";
import { toast } from "@/lib/toast-store";

export function CogniVaultHeaderChip({ dealId }: { dealId: string }) {
  const { data: connection, isLoading } = useVdrConnection(dealId);
  const connect = useConnectVdr();

  // Avoid header flicker before we know the connection state.
  if (isLoading) return null;

  if (connection?.connected) {
    return (
      <Link
        href={`/deals/${dealId}/settings`}
        title={`Shared into ${connection.vdr_name ?? connection.vdr_id ?? "a CogniVault VDR"}`}
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[12px] font-medium whitespace-nowrap shrink-0"
        style={{
          background: "var(--ws-ai-tint)",
          border: "1px solid var(--ws-border)",
          color: "var(--ws-ai-ink)",
        }}
      >
        <span
          className="h-1.5 w-1.5 rounded-full"
          style={{ background: "var(--ws-success)" }}
        />
        CogniVault connected
      </Link>
    );
  }

  const handleConnect = async () => {
    try {
      const { authorization_url } = await connect.mutateAsync(dealId);
      // Full-page navigation to CogniVault's consent screen (VDR-admin gated).
      window.location.href = authorization_url;
    } catch {
      toast.error("Couldn't start the CogniVault connection. Please try again.");
    }
  };

  return (
    <button
      type="button"
      onClick={handleConnect}
      disabled={connect.isPending}
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[12px] font-medium whitespace-nowrap shrink-0 disabled:opacity-50"
      style={{
        background: "transparent",
        border: "1px solid var(--ws-border)",
        color: "var(--ws-ink2)",
      }}
    >
      <Database className="w-3 h-3" />
      {connect.isPending ? "Connecting…" : "Connect to CogniVault"}
    </button>
  );
}
