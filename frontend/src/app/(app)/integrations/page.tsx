"use client";

import { useState, useEffect } from "react";
import apiClient from "@/lib/api-client";
import { LoadingState } from "@/components/shared/loading-state";
import { Link2, Video, MessageSquare, Mail } from "lucide-react";

interface Integration {
  platform: string;
  is_active: boolean;
  scopes: string | null;
  connected_at: string;
}

const PLATFORM_CONFIG: Record<
  string,
  { name: string; icon: typeof Video; description: string }
> = {
  zoom: {
    name: "Zoom",
    icon: Video,
    description: "Import meeting recordings from Zoom",
  },
  teams: {
    name: "Microsoft Teams",
    icon: Video,
    description: "Import meeting recordings from Teams",
  },
  slack: {
    name: "Slack",
    icon: MessageSquare,
    description: "Receive notifications in Slack channels",
  },
  outlook: {
    name: "Outlook Calendar",
    icon: Mail,
    description: "Sync calendar events for meeting scheduling",
  },
};

export default function IntegrationsPage() {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchIntegrations() {
      try {
        const { data } = await apiClient.get("/integrations");
        setIntegrations(data);
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    }
    fetchIntegrations();
  }, []);

  const connectedPlatforms = new Set(
    integrations.filter((i) => i.is_active).map((i) => i.platform)
  );

  const handleConnect = async (platform: string) => {
    try {
      const { data } = await apiClient.post(
        `/integrations/${platform}/connect`
      );
      if (data.authorization_url) {
        window.location.href = data.authorization_url;
      }
    } catch {
      // Handle error
    }
  };

  const handleDisconnect = async (platform: string) => {
    try {
      await apiClient.delete(`/integrations/${platform}/disconnect`);
      setIntegrations((prev) =>
        prev.filter((i) => i.platform !== platform)
      );
    } catch {
      // Handle error
    }
  };

  if (loading) {
    return <LoadingState message="Loading integrations..." />;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Integrations</h1>
        <p className="mt-1 text-muted-foreground">
          Connect your tools to import meetings and receive notifications.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {Object.entries(PLATFORM_CONFIG).map(([platform, config]) => {
          const isConnected = connectedPlatforms.has(platform);
          const Icon = config.icon;

          return (
            <div
              key={platform}
              className="flex items-center justify-between rounded-lg border bg-white p-6"
            >
              <div className="flex items-center gap-4">
                <div className="rounded-md bg-primary/10 p-3 text-primary">
                  <Icon className="h-6 w-6" />
                </div>
                <div>
                  <h3 className="font-semibold">{config.name}</h3>
                  <p className="text-sm text-muted-foreground">
                    {config.description}
                  </p>
                </div>
              </div>
              {isConnected ? (
                <button
                  onClick={() => handleDisconnect(platform)}
                  className="rounded-md border border-red-300 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50"
                >
                  Disconnect
                </button>
              ) : (
                <button
                  onClick={() => handleConnect(platform)}
                  className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
                >
                  <Link2 className="h-4 w-4" />
                  Connect
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
