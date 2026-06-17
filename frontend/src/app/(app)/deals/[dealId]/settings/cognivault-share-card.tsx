"use client";

import {
  useVdrConnection,
  useConnectVdr,
  useUpdateVdrShareScopes,
  useDisconnectVdr,
} from "@/hooks/use-cognivault";
import { ToggleSwitch } from "@/components/ui/toggle-switch";
import { toast } from "@/lib/toast-store";
import { VDR_SHARE_SCOPES, type VdrShareScope } from "@/types";

const SCOPE_LABELS: Record<VdrShareScope, string> = {
  documents: "Documents",
  transcripts: "Transcripts",
  analyses: "Analyses & extractions",
  search: "AI search",
};

// Per-deal sharing into a CogniVault VDR. Connecting is an OAuth flow — the
// browser is redirected to CogniVault, which only lets a VDR admin authorize.
// Once connected, the toggles control which resource types CogniVault may pull.
export function CogniVaultShareCard({ dealId }: { dealId: string }) {
  const { data: connection, isLoading } = useVdrConnection(dealId);
  const connect = useConnectVdr();
  const updateScopes = useUpdateVdrShareScopes();
  const disconnect = useDisconnectVdr();

  const handleConnect = async () => {
    try {
      const { authorization_url } = await connect.mutateAsync(dealId);
      // Full-page navigation to CogniVault's consent screen.
      window.location.href = authorization_url;
    } catch {
      toast.error("Couldn't start the CogniVault connection. Please try again.");
    }
  };

  const toggleScope = async (scope: VdrShareScope) => {
    const current = connection?.share_scopes ?? [];
    const next = current.includes(scope)
      ? current.filter((s) => s !== scope)
      : [...current, scope];
    await updateScopes.mutateAsync({ dealId, shareScopes: next });
  };

  return (
    <div className="rounded-lg border bg-white p-6">
      <h3 className="font-medium">CogniVault VDR Sharing</h3>
      <p className="mt-1 text-sm text-muted-foreground">
        Share this deal&apos;s data into a CogniVault data room. You can connect
        a deal to any VDR you administer, then choose what to share.
      </p>

      {isLoading ? (
        <p className="mt-4 text-sm text-muted-foreground">Loading…</p>
      ) : connection?.connected ? (
        <div className="mt-4 space-y-4">
          <div className="flex items-center justify-between rounded-md bg-muted/40 px-3 py-2 text-sm">
            <span>
              Connected to{" "}
              <span className="font-medium">
                {connection.vdr_name ?? connection.vdr_id}
              </span>
            </span>
            <button
              onClick={() => disconnect.mutate(dealId)}
              disabled={disconnect.isPending}
              className="rounded-md border px-3 py-1 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
            >
              {disconnect.isPending ? "Disconnecting…" : "Disconnect"}
            </button>
          </div>

          <div className="space-y-3">
            <p className="text-sm font-medium">Shared with this VDR</p>
            {VDR_SHARE_SCOPES.map((scope) => (
              <div key={scope} className="flex items-center justify-between">
                <span className="text-sm">{SCOPE_LABELS[scope]}</span>
                <ToggleSwitch
                  enabled={(connection.share_scopes ?? []).includes(scope)}
                  onToggle={() => toggleScope(scope)}
                  disabled={updateScopes.isPending}
                  title={`Toggle sharing ${SCOPE_LABELS[scope]}`}
                />
              </div>
            ))}
          </div>
        </div>
      ) : (
        <button
          onClick={handleConnect}
          disabled={connect.isPending}
          className="mt-4 rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50"
        >
          {connect.isPending ? "Connecting…" : "Connect to CogniVault VDR"}
        </button>
      )}
    </div>
  );
}
