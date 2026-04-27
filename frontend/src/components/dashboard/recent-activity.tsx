"use client";

import Link from "next/link";
import { useScribeTheme } from "@/components/cogniscribe/theme-provider";
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

const RESOURCE_TONE: Record<string, { dot: string; ring: string }> = {
  deals: { dot: "bg-indigo-500", ring: "ring-indigo-200" },
  meetings: { dot: "bg-emerald-500", ring: "ring-emerald-200" },
  documents: { dot: "bg-sky-500", ring: "ring-sky-200" },
  deliverables: { dot: "bg-violet-500", ring: "ring-violet-200" },
  analyses: { dot: "bg-fuchsia-500", ring: "ring-fuchsia-200" },
  org_memberships: { dot: "bg-amber-500", ring: "ring-amber-200" },
  deal_memberships: { dot: "bg-amber-500", ring: "ring-amber-200" },
  meeting_bot_sessions: { dot: "bg-rose-500", ring: "ring-rose-200" },
};

const FALLBACK_TONE = { dot: "bg-slate-400", ring: "ring-slate-200" };

function tone(resourceType: string) {
  return RESOURCE_TONE[resourceType] ?? FALLBACK_TONE;
}

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

function actorInitials(row: ActivityRow): string {
  const name = actorName(row);
  const parts = name.split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0]!.slice(0, 2).toUpperCase();
  return (parts[0]![0]! + parts[1]![0]!).toUpperCase();
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
      <div className="flex items-center gap-3 mb-5">
        <span className="inline-block h-5 w-1 rounded-full bg-gradient-to-b from-indigo-400 to-violet-600" />
        <span
          className={`text-[10px] font-medium tracking-[0.22em] uppercase ${
            isDark ? "text-indigo-300/80" : "text-indigo-600"
          }`}
        >
          Recent activity
        </span>
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
        <ul className="space-y-1">
          {rows.map((row) => {
            const href = activityHref(row);
            const t = tone(row.resource_type);
            const body = (
              <div className="flex items-start gap-3">
                <div className="relative flex h-8 w-8 shrink-0 items-center justify-center">
                  <span
                    className={`inline-flex h-7 w-7 items-center justify-center rounded-full text-[10px] font-semibold ${
                      isDark
                        ? "bg-white/[0.06] text-white/70"
                        : "bg-black/[0.04] text-black/65"
                    }`}
                  >
                    {actorInitials(row)}
                  </span>
                  <span
                    className={`absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full ring-2 ${t.dot} ${
                      isDark ? "ring-[#121212]" : "ring-white"
                    }`}
                  />
                </div>
                <div className="min-w-0 flex-1">
                  <p className={`text-[13px] leading-snug ${isDark ? "text-white/85" : "text-black/85"}`}>
                    <span className="font-medium">{actorName(row)}</span>{" "}
                    <span className={isDark ? "text-white/60" : "text-black/60"}>
                      {describe(row)}
                    </span>
                    {row.deal && (
                      <>
                        {" "}
                        <span className={isDark ? "text-white/45" : "text-black/45"}>·</span>{" "}
                        <span className={isDark ? "text-white/80" : "text-black/80"}>
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
              </div>
            );
            return (
              <li key={row.id}>
                {href ? (
                  <Link
                    href={href}
                    className={`block rounded-xl px-3 py-2 -mx-3 transition-colors ${
                      isDark ? "hover:bg-white/[0.04]" : "hover:bg-black/[0.03]"
                    }`}
                  >
                    {body}
                  </Link>
                ) : (
                  <div className="px-3 py-2 -mx-3">{body}</div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
