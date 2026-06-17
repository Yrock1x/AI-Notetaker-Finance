"use client";

// Deal workspace shell — project header (briefcase chip + name + target +
// stage chip + meta + team avatars + invite) followed by a sticky tab
// bar. Tabs match the Deal Workspace design (Overview, Meetings, Ask AI,
// Action Items, Transcripts, Documents, Settings); /team stays reachable by
// direct URL but is not promoted into the bar.

import Link from "next/link";
import { usePathname, useParams } from "next/navigation";
import { Briefcase, Clock, Plus } from "lucide-react";
import { useDeal, useDealMembers } from "@/hooks/use-deals";
import { useMeetings } from "@/hooks/use-meetings";
import { useDealExtractions } from "@/hooks/use-deal-extractions";
import { useDealStats } from "@/hooks/use-deal-stats";
import {
  AvatarStack,
  avatarColor,
  initialsOf,
} from "@/components/workspace/primitives";
import { LiveBanner } from "@/components/workspace/live-banner";
import { CogniVaultHeaderChip } from "@/components/deals/cognivault-header-chip";
import { cn } from "@/lib/utils";

interface TabDef {
  label: string;
  href: string;
  countKey?: "meetings" | "actions" | "chat";
}

const TABS: TabDef[] = [
  { label: "Overview", href: "" },
  { label: "Meetings", href: "/meetings", countKey: "meetings" },
  { label: "Ask AI", href: "/qa", countKey: "chat" },
  { label: "Action Items", href: "/action-items", countKey: "actions" },
  { label: "Transcripts", href: "/transcripts" },
  { label: "Documents", href: "/documents" },
  { label: "Settings", href: "/settings" },
];

export default function DealLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const params = useParams<{ dealId: string }>();
  const dealId = params.dealId;
  const basePath = `/deals/${dealId}`;

  const { data: deal } = useDeal(dealId);
  const { data: members } = useDealMembers(dealId);
  const { data: meetingsResp } = useMeetings(dealId);
  const { data: extractions } = useDealExtractions(dealId);
  const { data: stats } = useDealStats(dealId);

  const counts = {
    meetings: meetingsResp?.items.length ?? 0,
    actions: extractions?.actions.length ?? 0,
    chat: 0, // chat thread count: not yet persisted; left blank for now
  };

  const teamPeople = (members ?? []).map((m) => {
    const name = m.user?.full_name || m.user?.email || "User";
    return {
      initials: initialsOf(name),
      color: avatarColor(m.user?.email || m.user?.full_name || m.user_id),
      name,
    };
  });

  const hours = stats?.hoursCaptured.value ?? 0;

  return (
    <div data-workspace className="-m-8 md:-m-10 min-h-full">
      {dealId && <LiveBanner dealId={dealId} />}

      {/* Project header */}
      <div
        className="px-7 pt-4"
        style={{ background: "var(--ws-bg)" }}
      >
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2.5 shrink-0">
            <span
              className="grid place-items-center w-[26px] h-[26px] rounded-md"
              style={{
                background: "var(--ws-accent-soft)",
                color: "var(--ws-accent)",
              }}
            >
              <Briefcase className="w-3.5 h-3.5" />
            </span>
            <h1
              className="m-0 text-[20px] font-semibold leading-tight tracking-tight"
              style={{ color: "var(--ws-ink)" }}
            >
              {deal?.name ?? "Deal"}
            </h1>
          </div>
          {deal?.target_company && (
            <>
              <span style={{ color: "var(--ws-faint)" }}>·</span>
              <span
                className="text-[13px] truncate min-w-0"
                style={{ color: "var(--ws-muted)" }}
              >
                {deal.target_company}
              </span>
            </>
          )}
          {deal?.stage && (
            <span
              className="px-2 py-0.5 rounded text-[10.5px] font-semibold"
              style={{
                background: "var(--ws-accent-soft)",
                color: "var(--ws-accent)",
              }}
            >
              {deal.stage}
            </span>
          )}

          <div className="flex-1 min-w-2" />

          <div
            className="flex items-center gap-1.5 text-[11.5px] shrink-0 whitespace-nowrap"
            style={{ color: "var(--ws-muted)" }}
          >
            <Clock className="w-3 h-3" />
            <span>
              {counts.meetings} meeting{counts.meetings === 1 ? "" : "s"}
              {hours > 0 ? ` · ${hours}h captured` : ""}
            </span>
          </div>
          {teamPeople.length > 0 && (
            <AvatarStack people={teamPeople} size={22} max={5} />
          )}
          {dealId && <CogniVaultHeaderChip dealId={dealId} />}
          <Link
            href={`${basePath}/team`}
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-[12px] font-medium whitespace-nowrap shrink-0"
            style={{
              background: "transparent",
              border: "1px solid var(--ws-border)",
              color: "var(--ws-ink2)",
            }}
          >
            <Plus className="w-3 h-3" /> Invite
          </Link>
        </div>

        {/* Tabs — pulled tight under the header */}
        <nav
          className="flex gap-0.5 mt-3.5 -mb-px sticky top-0 z-10"
          style={{ background: "var(--ws-bg)" }}
        >
          {TABS.map((tab) => {
            const tabPath = `${basePath}${tab.href}`;
            const isActive =
              tab.href === ""
                ? pathname === basePath
                : pathname === tabPath || pathname.startsWith(`${tabPath}/`);
            const count = tab.countKey ? counts[tab.countKey] : undefined;
            return (
              <Link
                key={tab.label}
                href={tabPath}
                className={cn(
                  "inline-flex items-center gap-1.5 px-3 py-2 text-[13px] font-medium tracking-tight border-b-2 transition-colors",
                )}
                style={{
                  color: isActive ? "var(--ws-ink)" : "var(--ws-muted)",
                  fontWeight: isActive ? 600 : 500,
                  borderColor: isActive ? "var(--ws-ink)" : "transparent",
                }}
              >
                {tab.label}
                {count != null && count > 0 && (
                  <span
                    className="px-1.5 py-px rounded-[9px] text-[10.5px] font-semibold ws-mono"
                    style={{
                      background: isActive ? "var(--ws-sub2)" : "transparent",
                      color: isActive ? "var(--ws-ink2)" : "var(--ws-faint)",
                    }}
                  >
                    {count}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>
      </div>

      <div
        className="border-t"
        style={{ borderColor: "var(--ws-border)" }}
      >
        {children}
      </div>
    </div>
  );
}
