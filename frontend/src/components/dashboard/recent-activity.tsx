"use client";

import Link from "next/link";
import { Activity } from "lucide-react";
import { useScribeTheme } from "@/components/cogniscribe/theme-provider";
import { Eyebrow } from "@/components/cogniscribe/primitives";
import { useRecentActivity, type ActivityRow } from "@/hooks/use-recent-activity";
import { Skeleton } from "@/components/ui/skeleton";

const RESOURCE_NOUN: Record<string, string> = {
  deals: "deal",
  meetings: "meeting",
  documents: "document",
  deliverables: "deliverable",
  analyses: "analysis",
  org_memberships: "team member",
  deal_memberships: "deal member",
  meeting_bot_sessions: "bot session",
};

const ACTION_VERB: Record<string, string> = {
  create: "added",
  update: "updated",
  delete: "removed",
  insert: "added",
};

function describe(row: ActivityRow): string {
  const verb = ACTION_VERB[row.action] ?? row.action;
  const noun = RESOURCE_NOUN[row.resource_type] ?? row.resource_type.replace(/_/g, " ");
  return `${verb} a ${noun}`;
}

function relativeTime(iso: string): string {
  const t = new Date(iso).getTime();
  const diff = Date.now() - t;
  const min = Math.floor(diff / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 7) return `${day}d ago`;
  return new Date(iso).toLocaleDateString();
}

function actorName(row: ActivityRow): string {
  if (!row.user) return "Someone";
  return row.user.full_name?.trim() || row.user.email.split("@")[0];
}

function activityHref(row: ActivityRow): string | null {
  if (row.deal_id) return `/deals/${row.deal_id}`;
  return null;
}

export function RecentActivity() {
  const { isDark } = useScribeTheme();
  const { data: rows = [], isLoading } = useRecentActivity(15);

  return (
    <section
      className={`rounded-2xl border p-6 ${
        isDark
          ? "bg-[#121212] border-white/10"
          : "bg-white border-black/[0.06]"
      }`}
    >
      <div className="flex items-center gap-2 mb-5">
        <Activity className={`h-4 w-4 ${isDark ? "text-white/60" : "text-black/60"}`} />
        <Eyebrow>Recent activity</Eyebrow>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <p className={`text-sm ${isDark ? "text-white/40" : "text-black/40"}`}>
          No recent activity yet. Workspace events will appear here as the team works.
        </p>
      ) : (
        <ul className="space-y-2.5">
          {rows.map((row) => {
            const href = activityHref(row);
            const body = (
              <div className="min-w-0 flex-1">
                <p className={`text-[13px] leading-snug ${isDark ? "text-white/85" : "text-black/85"}`}>
                  <span className="font-medium">{actorName(row)}</span>{" "}
                  <span className={isDark ? "text-white/65" : "text-black/65"}>
                    {describe(row)}
                  </span>
                  {row.deal && (
                    <>
                      {" "}
                      <span className={isDark ? "text-white/55" : "text-black/55"}>·</span>{" "}
                      <span className={isDark ? "text-white/75" : "text-black/75"}>
                        {row.deal.name}
                      </span>
                    </>
                  )}
                </p>
                <p
                  className={`text-[10.5px] tabular-nums mt-0.5 ${
                    isDark ? "text-white/40" : "text-black/40"
                  }`}
                >
                  {relativeTime(row.created_at)}
                </p>
              </div>
            );
            return (
              <li key={row.id}>
                {href ? (
                  <Link
                    href={href}
                    className={`flex items-start gap-3 rounded-lg px-3 py-2 -mx-3 transition-colors ${
                      isDark ? "hover:bg-white/[0.04]" : "hover:bg-black/[0.03]"
                    }`}
                  >
                    {body}
                  </Link>
                ) : (
                  <div className="flex items-start gap-3 px-3 py-2 -mx-3">{body}</div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
