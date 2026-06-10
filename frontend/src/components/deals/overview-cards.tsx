"use client";

// Deal Overview cards: KPI strip, Project pulse, Recent meetings, Upcoming,
// Action items, and Decisions/Questions. The page owns data fetching and
// passes plain props down.

import Link from "next/link";
import {
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  Clock,
  Flag,
  HelpCircle,
  Mic,
  Play,
  RefreshCw,
  Sparkles,
  Users,
} from "lucide-react";
import { meetingDisplayState } from "@/lib/meeting-status";
import { useDealStats } from "@/hooks/use-deal-stats";
import {
  useActionItemCompletions,
  useToggleActionItem,
} from "@/hooks/use-action-item-completions";
import {
  CardActionLink,
  KindPill,
  StatTile,
  WSCard,
  avatarColor,
  initialsOf,
} from "@/components/workspace/primitives";
import {
  ExtractedAction,
  ExtractedDecision,
  ExtractedQuestion,
} from "@/hooks/use-deal-extractions";
import type { Meeting } from "@/types";

const SUGGESTED_PROMPTS = [
  "Summarize the last 5 meetings",
  "What action items are due this week?",
  "Which questions came up but never got answered?",
];

function formatMeetingWhen(m: Meeting): { date: string; time: string } {
  const d = m.meeting_date ? new Date(m.meeting_date) : new Date(m.created_at);
  return {
    date: d.toLocaleDateString(undefined, { month: "short", day: "numeric" }),
    time: d.toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
    }),
  };
}

function meetingKind(m: Meeting): string {
  // Heuristic until call_type is exposed on meetings: bot/managed sources
  // are usually external calls; manual uploads default to External.
  if (m.source === "upload") return "External";
  if (m.source === "zoom" || m.source === "teams" || m.source === "google_meet")
    return "External";
  return "Other";
}

function meetingStatusBadge(m: Meeting): { label: string; color: string } | null {
  const state = meetingDisplayState(m);
  if (state === "live") return { label: "Live", color: "var(--ws-danger)" };
  if (state === "scheduled") return { label: "Upcoming", color: "var(--ws-muted)" };
  if (state === "not_joined") return { label: "Not joined", color: "var(--ws-faint)" };
  if (
    m.status === "transcribing" ||
    m.status === "analyzing" ||
    m.status === "uploading" ||
    m.status === "processing"
  ) {
    return { label: "Processing", color: "var(--ws-warn)" };
  }
  if (m.status === "failed") return { label: "Failed", color: "var(--ws-danger)" };
  return null;
}

export function StatsRow({
  stats,
  totalActions,
  totalDecisions,
  totalQuestions,
  liveCount,
}: {
  stats?: ReturnType<typeof useDealStats>["data"];
  totalActions: number;
  totalDecisions: number;
  totalQuestions: number;
  liveCount: number;
}) {
  const items: Array<React.ComponentProps<typeof StatTile>> = [
    {
      label: "Meetings this week",
      value: stats?.meetingsThisWeek.value ?? 0,
      delta:
        stats?.meetingsThisWeek.delta != null
          ? stats.meetingsThisWeek.delta >= 0
            ? `+${stats.meetingsThisWeek.delta}`
            : String(stats.meetingsThisWeek.delta)
          : undefined,
      trend: stats?.meetingsThisWeek.trend,
      sub: stats?.meetingsThisWeek.sub,
      icon: <Mic className="w-3 h-3" />,
    },
    {
      label: "Hours captured",
      value: stats?.hoursCaptured.value ?? 0,
      unit: "h",
      sub: stats?.hoursCaptured.sub,
      icon: <Clock className="w-3 h-3" />,
    },
    {
      label: "Action items",
      value: totalActions,
      sub:
        stats && stats.actionItems.dueThisWeek > 0
          ? `${stats.actionItems.dueThisWeek} due this week`
          : "from AI extraction",
      icon: <Flag className="w-3 h-3" />,
    },
    {
      label: "Decisions logged",
      value: totalDecisions,
      sub: "since project start",
      icon: <CheckCircle2 className="w-3 h-3" />,
    },
    {
      label: "Open questions",
      value: totalQuestions,
      sub: "AI-extracted",
      icon: <HelpCircle className="w-3 h-3" />,
    },
    {
      label: "Live now",
      value: liveCount,
      sub: liveCount > 0 ? "recording" : "no live calls",
      icon: <Users className="w-3 h-3" />,
      isLast: true,
    },
  ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 ws-card overflow-hidden">
      {items.map((it, i) => (
        <StatTile key={it.label} {...it} isLast={i === items.length - 1} />
      ))}
    </div>
  );
}

export function ProjectPulse({
  dealId,
  meetingsCount,
  actionCount,
  decisionCount,
}: {
  dealId: string;
  meetingsCount: number;
  actionCount: number;
  decisionCount: number;
}) {
  const headline = meetingsCount === 0
    ? "Start capturing meetings to build a project pulse"
    : actionCount > 0
      ? "AI extractions are flowing — review action items and decisions"
      : "Meetings captured · summary refreshes after analysis runs";
  const body = meetingsCount === 0
    ? "Schedule a notetaker bot or upload a recording. Once a meeting is transcribed and analyzed, decisions, action items, and open questions show up here automatically."
    : `Across ${meetingsCount} call${meetingsCount === 1 ? "" : "s"}, the workspace has surfaced ${decisionCount} decision${decisionCount === 1 ? "" : "s"} and ${actionCount} action item${actionCount === 1 ? "" : "s"}. Open the AI Chat tab to ask questions across the full transcript history.`;

  return (
    <div
      className="grid grid-cols-1 md:grid-cols-[1fr_360px] rounded-[10px] overflow-hidden"
      style={{ background: "var(--ws-bg)", border: "1px solid var(--ws-border)" }}
    >
      <div
        className="px-5 py-4"
        style={{
          background:
            "linear-gradient(180deg, var(--ws-ai-tint) 0%, var(--ws-bg) 65%)",
        }}
      >
        <div className="flex items-center gap-1.5 mb-2 flex-wrap">
          <span
            className="w-[22px] h-[22px] rounded-md grid place-items-center"
            style={{
              background: "linear-gradient(135deg, var(--ws-accent), var(--ws-ai-ink))",
              color: "#fff",
            }}
          >
            <Sparkles className="w-2.5 h-2.5" />
          </span>
          <span
            className="text-[10.5px] font-bold uppercase tracking-wider"
            style={{ color: "var(--ws-ai-ink)" }}
          >
            Project pulse
          </span>
          <span className="text-[11px]" style={{ color: "var(--ws-muted)" }}>
            · derived from {meetingsCount} meeting{meetingsCount === 1 ? "" : "s"}
          </span>
          <button
            type="button"
            className="ml-auto inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10.5px] font-semibold"
            style={{
              background: "transparent",
              border: "1px solid var(--ws-border)",
              color: "var(--ws-ink2)",
            }}
            disabled
            title="Auto-refreshes when new analyses complete"
          >
            <RefreshCw className="w-2.5 h-2.5" /> Refresh
          </button>
        </div>
        <div
          className="text-[17px] font-semibold leading-snug tracking-tight mb-1"
          style={{ color: "var(--ws-ink)" }}
        >
          {headline}.
        </div>
        <p
          className="m-0 text-[13.5px] leading-relaxed"
          style={{ color: "var(--ws-ink2)" }}
        >
          {body}
        </p>
      </div>

      <div
        className="px-4 py-4 flex flex-col gap-2.5"
        style={{
          borderLeft: "1px solid var(--ws-border)",
          background: "var(--ws-surface)",
        }}
      >
        <div className="flex items-center gap-1.5">
          <span className="ws-eyebrow" style={{ color: "var(--ws-muted)" }}>
            Quick ask
          </span>
          <div className="flex-1" />
          <Link
            href={`/deals/${dealId}/qa`}
            className="text-[11px] font-semibold inline-flex items-center gap-1"
            style={{ color: "var(--ws-ai-ink)" }}
          >
            Open AI Chat <ArrowRight className="w-2.5 h-2.5" />
          </Link>
        </div>
        <Link
          href={`/deals/${dealId}/qa`}
          className="flex items-center gap-2 px-2.5 py-2 rounded-[8px]"
          style={{
            background: "var(--ws-bg)",
            border: "1px solid var(--ws-border-strong)",
          }}
        >
          <Sparkles
            className="w-3 h-3 shrink-0"
            style={{ color: "var(--ws-ai-ink)" }}
          />
          <span
            className="flex-1 text-[12.5px]"
            style={{ color: "var(--ws-muted)" }}
          >
            Ask anything about this deal…
          </span>
          <span className="ws-mono text-[10px]" style={{ color: "var(--ws-faint)" }}>
            ⌘K
          </span>
        </Link>
        <div className="flex flex-col gap-1.5">
          {SUGGESTED_PROMPTS.map((p) => (
            <Link
              key={p}
              href={`/deals/${dealId}/qa?q=${encodeURIComponent(p)}`}
              className="px-2 py-1.5 text-left rounded-[5px] text-[11.5px] leading-snug"
              style={{
                background: "transparent",
                border: "1px dashed var(--ws-border-strong)",
                color: "var(--ws-ink2)",
              }}
            >
              <Sparkles
                className="w-2.5 h-2.5 align-middle inline mr-1.5"
                style={{ color: "var(--ws-ai-ink)" }}
              />
              {p}
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

export function RecentMeetings({
  dealId,
  meetings,
  loading,
}: {
  dealId: string;
  meetings: Meeting[];
  loading: boolean;
}) {
  return (
    <WSCard
      title="Recent meetings"
      action={
        <CardActionLink href={`/deals/${dealId}/meetings`}>
          View all <ArrowRight className="w-3 h-3" />
        </CardActionLink>
      }
    >
      {loading ? (
        <div className="px-3.5 py-6 text-[12.5px]" style={{ color: "var(--ws-muted)" }}>
          Loading meetings…
        </div>
      ) : meetings.length === 0 ? (
        <div className="px-3.5 py-6 text-[12.5px]" style={{ color: "var(--ws-muted)" }}>
          No meetings yet. Schedule a notetaker or upload a recording from the
          Meetings tab.
        </div>
      ) : (
        meetings.map((m, i) => {
          const w = formatMeetingWhen(m);
          const status = meetingStatusBadge(m);
          return (
            <Link
              key={m.id}
              href={`/deals/${dealId}/meetings/${m.id}`}
              className="grid grid-cols-[auto_1fr_auto] gap-3 items-center px-3.5 py-2.5 cursor-pointer transition-colors hover:bg-[var(--ws-sub)]"
              style={{
                borderTop: i > 0 ? "1px solid var(--ws-border)" : undefined,
              }}
            >
              <span
                className="w-[30px] h-[30px] rounded-md grid place-items-center shrink-0"
                style={{
                  border: "1px solid var(--ws-border)",
                  background: "var(--ws-sub)",
                  color: "var(--ws-ink)",
                }}
              >
                <Play className="w-3 h-3" />
              </span>
              <div className="min-w-0">
                <div className="flex items-baseline gap-2">
                  <span
                    className="text-[13px] font-semibold truncate"
                    style={{ color: "var(--ws-ink)" }}
                  >
                    {m.title}
                  </span>
                  <KindPill kind={meetingKind(m)} />
                  {status && (
                    <span
                      className="text-[10px] font-bold uppercase tracking-wider"
                      style={{ color: status.color }}
                    >
                      {status.label}
                    </span>
                  )}
                </div>
                <div
                  className="text-[11.5px] mt-0.5 flex items-center gap-2 flex-wrap"
                  style={{ color: "var(--ws-muted)" }}
                >
                  <span>
                    {w.date} · {w.time}
                  </span>
                  {m.duration_seconds && (
                    <>
                      <span>·</span>
                      <span className="ws-mono">
                        {Math.floor(m.duration_seconds / 60)} min
                      </span>
                    </>
                  )}
                </div>
              </div>
              <ChevronRight
                className="w-3 h-3"
                style={{ color: "var(--ws-faint)" }}
              />
            </Link>
          );
        })
      )}
    </WSCard>
  );
}

export function UpcomingCard({
  upcoming,
  dealId,
}: {
  upcoming: Meeting[];
  dealId: string;
}) {
  return (
    <WSCard
      title="Upcoming"
      action={
        <span className="text-[11px]" style={{ color: "var(--ws-muted)" }}>
          {upcoming.length} scheduled
        </span>
      }
    >
      {upcoming.length === 0 ? (
        <div className="px-3.5 py-5 text-[12px]" style={{ color: "var(--ws-muted)" }}>
          Nothing scheduled. Schedule a notetaker bot to populate this.
        </div>
      ) : (
        upcoming.map((u, i) => {
          const d = new Date(u.meeting_date || u.created_at);
          const month = d.toLocaleDateString(undefined, { month: "short" });
          const day = d.getDate();
          const time = d.toLocaleTimeString(undefined, {
            hour: "2-digit",
            minute: "2-digit",
          });
          return (
            <Link
              key={u.id}
              href={`/deals/${dealId}/meetings/${u.id}`}
              className="grid grid-cols-[auto_1fr_auto] gap-2.5 items-center px-3.5 py-2.5"
              style={{
                borderTop: i > 0 ? "1px solid var(--ws-border)" : undefined,
              }}
            >
              <div
                className="w-[38px] py-0.5 text-center rounded-[5px]"
                style={{ background: "var(--ws-sub)" }}
              >
                <div
                  className="text-[9.5px] font-semibold uppercase tracking-wide leading-none"
                  style={{ color: "var(--ws-muted)" }}
                >
                  {month}
                </div>
                <div
                  className="text-[13px] font-bold leading-tight ws-mono"
                  style={{ color: "var(--ws-ink)" }}
                >
                  {day}
                </div>
              </div>
              <div className="min-w-0">
                <div
                  className="text-[12.5px] font-semibold truncate"
                  style={{ color: "var(--ws-ink)" }}
                >
                  {u.title}
                </div>
                <div
                  className="text-[11px] mt-0.5"
                  style={{ color: "var(--ws-muted)" }}
                >
                  {time} {u.bot_enabled && "· bot scheduled"}
                </div>
              </div>
              <KindPill kind={meetingKind(u)} />
            </Link>
          );
        })
      )}
    </WSCard>
  );
}

export function ActionsCard({
  actions,
  dealId,
}: {
  actions: ExtractedAction[];
  dealId: string;
}) {
  const items = actions.slice(0, 5);
  const { data: completions } = useActionItemCompletions(dealId);
  const toggle = useToggleActionItem();
  return (
    <WSCard
      title="Action items extracted by AI"
      action={
        <CardActionLink href={`/deals/${dealId}/action-items`}>
          {actions.length} total
        </CardActionLink>
      }
    >
      {items.length === 0 ? (
        <div className="px-3.5 py-5 text-[12px]" style={{ color: "var(--ws-muted)" }}>
          No action items yet. They appear here once meeting analyses run.
        </div>
      ) : (
        items.map((a, i) => {
          const ownerInitials = a.owner ? initialsOf(a.owner) : null;
          const isDone = completions?.has(a.id) || a.status === "done";
          const stColor =
            a.status === "open"
              ? "var(--ws-warn)"
              : a.status === "in_review"
                ? "var(--ws-ai-ink)"
                : a.status === "scheduled"
                  ? "var(--ws-accent)"
                  : "var(--ws-success)";
          return (
            <div
              key={a.id}
              className="grid grid-cols-[auto_1fr_auto_auto] gap-2.5 items-start px-3.5 py-2.5"
              style={{
                borderTop: i > 0 ? "1px solid var(--ws-border)" : undefined,
              }}
            >
              <input
                type="checkbox"
                className="mt-1"
                style={{ accentColor: "var(--ws-accent)" }}
                checked={isDone}
                onChange={(e) => {
                  toggle.mutate({
                    dealId,
                    actionKey: a.id,
                    actionText: a.text,
                    analysisId: a.analysisId,
                    completed: e.target.checked,
                  });
                }}
              />
              <div className="min-w-0">
                <div
                  className="text-[12.5px] font-medium leading-snug"
                  style={{ color: "var(--ws-ink)" }}
                >
                  {a.text}
                </div>
                <Link
                  href={`/deals/${dealId}/meetings/${a.meetingId}`}
                  className="text-[10.5px] mt-1 flex items-center gap-1.5 flex-wrap"
                  style={{ color: "var(--ws-muted)" }}
                >
                  <Sparkles
                    className="w-2.5 h-2.5"
                    style={{ color: "var(--ws-ai-ink)" }}
                  />
                  <span>
                    From{" "}
                    <span style={{ color: "var(--ws-ink2)", fontWeight: 500 }}>
                      {a.meetingTitle}
                    </span>
                  </span>
                  {a.timestamp && (
                    <span
                      className="ws-mono"
                      style={{ color: "var(--ws-faint)" }}
                    >
                      {a.timestamp}
                    </span>
                  )}
                </Link>
              </div>
              <span
                className="px-1.5 py-px rounded-[3px] text-[10px] font-semibold capitalize whitespace-nowrap"
                style={{ background: `${stColor}15`, color: stColor }}
              >
                {a.status.replace("_", " ")}
              </span>
              {ownerInitials ? (
                <span
                  className="inline-flex items-center justify-center rounded-full text-white text-[9.5px] font-semibold"
                  style={{
                    width: 20,
                    height: 20,
                    background: avatarColor(a.owner),
                  }}
                  title={a.owner}
                >
                  {ownerInitials}
                </span>
              ) : (
                <span />
              )}
            </div>
          );
        })
      )}
    </WSCard>
  );
}

export function ExtractionsCard({
  decisions,
  questions,
  dealId,
}: {
  decisions: ExtractedDecision[];
  questions: ExtractedQuestion[];
  dealId: string;
}) {
  return (
    <WSCard
      title="Decisions & open questions"
      action={
        <CardActionLink href={`/deals/${dealId}/action-items`}>
          {decisions.length + questions.length} extracted
        </CardActionLink>
      }
    >
      {decisions.slice(0, 3).map((d, i) => (
        <div
          key={d.id}
          className="grid grid-cols-[auto_1fr] gap-2.5 px-3.5 py-2.5 items-start"
          style={{
            borderTop: i > 0 ? "1px solid var(--ws-border)" : undefined,
          }}
        >
          <CheckCircle2
            className="w-3 h-3 mt-1 shrink-0"
            style={{ color: "var(--ws-success)" }}
          />
          <div className="min-w-0">
            <div
              className="text-[12.5px] font-medium leading-snug"
              style={{ color: "var(--ws-ink)" }}
            >
              {d.text}
            </div>
            <Link
              href={`/deals/${dealId}/meetings/${d.meetingId}`}
              className="text-[10.5px] mt-0.5 block"
              style={{ color: "var(--ws-muted)" }}
            >
              {d.meetingTitle}
              {d.timestamp && (
                <>
                  {" · "}
                  <span className="ws-mono" style={{ color: "var(--ws-faint)" }}>
                    {d.timestamp}
                  </span>
                </>
              )}
            </Link>
          </div>
        </div>
      ))}
      {questions.slice(0, 3).map((q, i) => (
        <div
          key={q.id}
          className="grid grid-cols-[auto_1fr] gap-2.5 px-3.5 py-2.5 items-start"
          style={{
            borderTop: "1px solid var(--ws-border)",
          }}
        >
          <HelpCircle
            className="w-3 h-3 mt-1 shrink-0"
            style={{ color: "var(--ws-warn)" }}
          />
          <div className="min-w-0">
            <div
              className="text-[12.5px] font-medium leading-snug"
              style={{ color: "var(--ws-ink)" }}
            >
              {q.text}
            </div>
            <Link
              href={`/deals/${dealId}/meetings/${q.meetingId}`}
              className="text-[10.5px] mt-0.5 block"
              style={{ color: "var(--ws-muted)" }}
            >
              Raised in {q.meetingTitle}
            </Link>
          </div>
        </div>
      ))}
      {decisions.length === 0 && questions.length === 0 && (
        <div className="px-3.5 py-5 text-[12px]" style={{ color: "var(--ws-muted)" }}>
          No extractions yet. Decisions and open questions surface here as
          meeting analyses complete.
        </div>
      )}
    </WSCard>
  );
}
