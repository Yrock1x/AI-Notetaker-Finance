"use client";

import { useState, useEffect } from "react";
import apiClient from "@/lib/api-client";
import { LoadingState } from "@/components/shared/loading-state";
import {
  Video,
  MessageSquare,
  Calendar,
  Check,
  Loader2,
  Link2,
  Bot,
} from "lucide-react";

interface Integration {
  platform: string;
  is_active: boolean;
  scopes: string | null;
  connected_at: string;
}

const PLATFORM_CONFIG: Record<
  string,
  {
    name: string;
    icon: typeof Video;
    description: string;
    color: string;
    bgColor: string;
    supportsBot: boolean;
  }
> = {
  zoom: {
    name: "Zoom",
    icon: Video,
    description: "Record meetings, import transcripts, and deploy AI notetaker bots",
    color: "text-blue-600",
    bgColor: "bg-blue-50",
    supportsBot: true,
  },
  teams: {
    name: "Microsoft Teams",
    icon: Video,
    description: "Record Teams meetings and capture live transcription data",
    color: "text-indigo-600",
    bgColor: "bg-indigo-50",
    supportsBot: true,
  },
  slack: {
    name: "Slack",
    icon: MessageSquare,
    description: "Push deal updates, analysis alerts, and meeting summaries to channels",
    color: "text-purple-600",
    bgColor: "bg-purple-50",
    supportsBot: false,
  },
  outlook: {
    name: "Outlook Calendar",
    icon: Calendar,
    description: "Sync calendar events to auto-schedule meeting bots",
    color: "text-sky-600",
    bgColor: "bg-sky-50",
    supportsBot: false,
  },
};

export default function IntegrationsPage() {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState<string | null>(null);

  const fetchIntegrations = async () => {
    try {
      const { data } = await apiClient.get("/integrations");
      setIntegrations(data);
    } catch {
      // Use default empty state
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIntegrations();
  }, []);

  const connectedPlatforms = new Set(
    integrations.filter((i) => i.is_active).map((i) => i.platform)
  );

  const handleConnect = async (platform: string) => {
    setConnecting(platform);
    try {
      const { data } = await apiClient.post(
        `/integrations/${platform}/connect`
      );
      if (data.authorization_url) {
        window.location.href = data.authorization_url;
        return;
      }
      // Demo mode: connected immediately
      await fetchIntegrations();
    } catch {
      // Handle error
    } finally {
      setTimeout(() => setConnecting(null), 400);
    }
  };

  const handleDisconnect = async (platform: string) => {
    try {
      await apiClient.delete(`/integrations/${platform}/disconnect`);
      await fetchIntegrations();
    } catch {
      // Handle error
    }
  };

  if (loading) {
    return <LoadingState message="Loading integrations..." />;
  }

  const connectedCount = connectedPlatforms.size;

  return (
    <div className="space-y-8 antialiased">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-heading font-extrabold text-primary">
          Integrations
        </h2>
        <p className="text-sm text-[#1A1A1A]/50 font-medium mt-1">
          Connect your meeting and communication platforms to unlock AI-powered workflows.
        </p>
      </div>

      {/* Status bar */}
      <div className="flex items-center gap-3 rounded-2xl border border-[#1A1A1A]/5 bg-white px-5 py-3.5">
        <div className="flex items-center gap-2">
          <div
            className={`h-2.5 w-2.5 rounded-full ${
              connectedCount > 0 ? "bg-emerald-500" : "bg-[#1A1A1A]/20"
            }`}
          />
          <span className="text-sm font-bold text-primary">
            {connectedCount} of 4 connected
          </span>
        </div>
        <span className="text-xs text-[#1A1A1A]/40">
          Connect platforms to enable meeting recording, calendar sync, and notifications.
        </span>
      </div>

      {/* Platform cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {Object.entries(PLATFORM_CONFIG).map(([platform, config]) => {
          const isConnected = connectedPlatforms.has(platform);
          const isConnecting = connecting === platform;
          const Icon = config.icon;

          return (
            <div
              key={platform}
              className={`relative rounded-2xl border bg-white p-6 transition-all hover:shadow-md ${
                isConnected
                  ? "border-emerald-200 shadow-sm"
                  : "border-[#1A1A1A]/5"
              }`}
            >
              {/* Connected badge */}
              {isConnected && (
                <div className="absolute right-4 top-4 flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1">
                  <div className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                  <span className="text-[11px] font-bold text-emerald-700">
                    Connected
                  </span>
                </div>
              )}

              <div className="flex items-start gap-4">
                <div className={`rounded-xl p-3 ${config.bgColor}`}>
                  <Icon className={`h-6 w-6 ${config.color}`} />
                </div>
                <div className="flex-1">
                  <h3 className="font-heading font-bold text-primary">
                    {config.name}
                  </h3>
                  <p className="mt-1 text-xs text-[#1A1A1A]/40 leading-relaxed">
                    {config.description}
                  </p>

                  {/* Bot badge for Zoom/Teams */}
                  {config.supportsBot && (
                    <div className="mt-2.5 inline-flex items-center gap-1.5 rounded-lg bg-accent/5 px-2.5 py-1">
                      <Bot className="h-3 w-3 text-accent" />
                      <span className="text-[10px] font-bold text-accent">
                        AI Notetaker Bot
                      </span>
                    </div>
                  )}
                </div>
              </div>

              <div className="mt-5">
                {isConnected ? (
                  <button
                    onClick={() => handleDisconnect(platform)}
                    className="w-full rounded-xl border border-[#1A1A1A]/10 py-2.5 text-xs font-bold text-[#1A1A1A]/40 transition-all hover:border-red-300 hover:text-red-500"
                  >
                    Disconnect
                  </button>
                ) : (
                  <button
                    onClick={() => handleConnect(platform)}
                    disabled={isConnecting}
                    className="flex w-full items-center justify-center gap-2 rounded-xl bg-accent py-2.5 text-xs font-bold text-white shadow-sm transition-all hover:shadow-md disabled:opacity-60"
                  >
                    {isConnecting ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        Connecting...
                      </>
                    ) : (
                      <>
                        <Link2 className="h-3.5 w-3.5" />
                        Connect {config.name}
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Meeting bot section */}
      <div className="rounded-2xl border border-[#1A1A1A]/5 bg-white p-6">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-accent/10 p-3">
            <Bot className="h-5 w-5 text-accent" />
          </div>
          <div>
            <h3 className="font-heading font-bold text-primary">
              AI Notetaker Bot
            </h3>
            <p className="text-xs text-[#1A1A1A]/40 mt-0.5">
              Automatically joins Zoom or Teams meetings to record, transcribe, and analyze conversations.
            </p>
          </div>
        </div>

        <div className="mt-4 rounded-xl bg-[#F2F0E9]/30 p-4">
          {connectedPlatforms.has("zoom") || connectedPlatforms.has("teams") ? (
            <div className="flex items-center gap-2">
              <Check className="h-4 w-4 text-emerald-600" />
              <span className="text-xs font-bold text-emerald-700">
                Bot ready — connect a meeting platform above, then schedule a bot from any deal.
              </span>
            </div>
          ) : (
            <p className="text-xs text-[#1A1A1A]/40">
              Connect Zoom or Microsoft Teams above to enable the AI notetaker bot for your meetings.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
