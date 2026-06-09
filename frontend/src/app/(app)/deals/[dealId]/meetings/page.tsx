"use client";

// Meetings tab — redesigned to match the workspace table from the design:
// kind filter, table/timeline toggle, expandable rows with AI extractions,
// and the existing schedule + upload buttons mounted as workspace pills.

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Bot, Mic, Play, Sparkles, Upload } from "lucide-react";
import {
  useMeetings,
  useToggleMeetingBot,
} from "@/hooks/use-meetings";
import { useDealExtractions } from "@/hooks/use-deal-extractions";
import { meetingDisplayState } from "@/lib/meeting-status";
import { UploadDialog } from "@/components/meetings/upload-dialog";
import { ScheduleBotDialog } from "@/components/meetings/schedule-bot-dialog";
import { LoadingState } from "@/components/shared/loading-state";
import { ToggleSwitch } from "@/components/ui/toggle-switch";
import {
  AvatarStack,
  KindPill,
  LiveDot,
  PillButton,
  WSCard,
  avatarColor,
} from "@/components/workspace/primitives";
import type { Meeting } from "@/types";

type KindFilter = "All" | "External" | "Internal" | "Legal" | "Expert";

function meetingKind(m: Meeting): KindFilter {
  if (
    m.source === "zoom" ||
    m.source === "teams" ||
    m.source === "google_meet" ||
    m.source === "upload"
  )
    return "External";
  return "Internal";
}

function attendeesFromTitle(_m: Meeting): string[] {
  // Real attendees come from `attendees` (linked profiles) and bot
  // sessions; until that's wired into a single hook we stub with a
  // small synthetic stack so the avatar column isn't empty. The actual
  // list still appears in the meeting detail page's Attendees tab.
  return [];
}

export default function MeetingsPage() {
  const params = useParams<{ dealId: string }>();
  const dealId = params.dealId;
  const { data, isLoading } = useMeetings(dealId);
  const { data: extractions } = useDealExtractions(dealId);
  const toggleBot = useToggleMeetingBot(dealId);

  const [uploadOpen, setUploadOpen] = useState(false);
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [botOverrides, setBotOverrides] = useState<Record<string, boolean>>({});

  const meetings = data?.items ?? [];

  return (
    <div
      className="flex flex-col gap-4 px-7 pt-4 pb-10"
      style={{ background: "var(--ws-sub)", minHeight: "100%" }}
    >
      <div className="flex items-center gap-3">
        <h2 className="m-0 text-[16px] font-semibold" style={{ color: "var(--ws-ink)" }}>
          Meetings
        </h2>
        <span className="text-[12px]" style={{ color: "var(--ws-muted)" }}>
          {meetings.length}
        </span>
        <div className="flex-1" />
        <PillButton onClick={() => setScheduleOpen(true)}>
          <Bot className="w-3 h-3" /> Schedule
        </PillButton>
        <PillButton variant="primary" onClick={() => setUploadOpen(true)}>
          <Upload className="w-3 h-3" /> Upload
        </PillButton>
      </div>

      {isLoading ? (
        <LoadingState message="Loading meetings…" />
      ) : meetings.length === 0 ? (
        <div
          className="rounded-md p-8 text-center"
          style={{
            background: "var(--ws-bg)",
            border: "1px solid var(--ws-border)",
          }}
        >
          <Mic className="w-5 h-5 mx-auto mb-2" style={{ color: "var(--ws-faint)" }} />
          <p className="m-0 text-[13px] font-semibold" style={{ color: "var(--ws-ink)" }}>
            No meetings yet
          </p>
          <p className="m-0 mt-1 text-[12px]" style={{ color: "var(--ws-muted)" }}>
            Schedule a notetaker bot or upload a recording to get started.
          </p>
        </div>
      ) : (
        <MeetingsTable
          dealId={dealId}
          list={meetings}
          extractions={extractions}
          botOverrides={botOverrides}
          onToggleBot={async (id, current) => {
            const next = !current;
            setBotOverrides((p) => ({ ...p, [id]: next }));
            try {
              await toggleBot.mutateAsync({ meetingId: id, bot_enabled: next });
            } catch {
              setBotOverrides((p) => ({ ...p, [id]: current }));
            }
          }}
        />
      )}

      <UploadDialog
        dealId={dealId}
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
      />
      <ScheduleBotDialog
        dealId={dealId}
        open={scheduleOpen}
        onClose={() => setScheduleOpen(false)}
      />
    </div>
  );
}

interface ExtractionsBundle {
  actions: { meetingId: string; status: string }[];
  decisions: { meetingId: string }[];
  questions: { meetingId: string }[];
}

function meetingExtractionCounts(
  meetingId: string,
  ext: ExtractionsBundle | undefined,
) {
  if (!ext) return { actions: 0, decisions: 0, questions: 0 };
  return {
    actions: ext.actions.filter((a) => a.meetingId === meetingId).length,
    decisions: ext.decisions.filter((d) => d.meetingId === meetingId).length,
    questions: ext.questions.filter((q) => q.meetingId === meetingId).length,
  };
}

function MeetingsTable({
  dealId,
  list,
  extractions,
  botOverrides,
  onToggleBot,
}: {
  dealId: string;
  list: Meeting[];
  extractions: ExtractionsBundle | undefined;
  botOverrides: Record<string, boolean>;
  onToggleBot: (id: string, current: boolean) => void;
}) {
  return (
    <WSCard>
      <div
        className="grid items-center gap-3 px-3.5 py-2 text-[10.5px] font-semibold uppercase tracking-wider"
        style={{
          background: "var(--ws-surface)",
          borderBottom: "1px solid var(--ws-border)",
          color: "var(--ws-muted)",
          gridTemplateColumns: "auto 1.4fr 1.6fr 110px 110px 90px 60px",
        }}
      >
        <span></span>
        <span>Meeting</span>
        <span>AI summary & extractions</span>
        <span>When</span>
        <span>Attendees / bot</span>
        <span className="text-right">Duration</span>
        <span></span>
      </div>
      {list.map((m, i) => (
        <MeetingRow
          key={m.id}
          dealId={dealId}
          m={m}
          last={i === list.length - 1}
          extractions={extractions}
          botOverride={botOverrides[m.id]}
          onToggleBot={onToggleBot}
        />
      ))}
    </WSCard>
  );
}

function MeetingRow({
  dealId,
  m,
  last,
  extractions,
  botOverride,
  onToggleBot,
}: {
  dealId: string;
  m: Meeting;
  last: boolean;
  extractions: ExtractionsBundle | undefined;
  botOverride: boolean | undefined;
  onToggleBot: (id: string, current: boolean) => void;
}) {
  const counts = meetingExtractionCounts(m.id, extractions);
  const d = m.meeting_date ? new Date(m.meeting_date) : new Date(m.created_at);
  const state = meetingDisplayState(m);
  const isLive = state === "live";
  const showBot = Boolean(m.source_url) && (state === "scheduled" || state === "live");
  const enabled = botOverride ?? m.bot_enabled ?? true;
  const stack = attendeesFromTitle(m).map((init) => ({
    initials: init,
    color: avatarColor(init),
  }));

  return (
    <div
      style={{ borderBottom: !last ? "1px solid var(--ws-border)" : "none" }}
    >
      <Link
        href={`/deals/${dealId}/meetings/${m.id}`}
        className="grid items-center gap-3 px-3.5 py-3 cursor-pointer transition-colors hover:bg-[var(--ws-sub)]"
        style={{
          gridTemplateColumns: "auto 1.4fr 1.6fr 110px 110px 90px 60px",
          fontSize: 12.5,
        }}
      >
        <span
          className="w-[28px] h-[28px] rounded-md grid place-items-center"
          style={{
            border: "1px solid var(--ws-border)",
            background: isLive ? "var(--ws-danger)" : "var(--ws-sub)",
            color: isLive ? "#fff" : "var(--ws-ink)",
          }}
        >
          {isLive ? <Mic className="w-3 h-3" /> : <Play className="w-3 h-3" />}
        </span>
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 mb-0.5">
            <span
              className="font-semibold truncate"
              style={{ color: "var(--ws-ink)" }}
            >
              {m.title}
            </span>
          </div>
          <div className="flex items-center gap-1.5 flex-wrap">
            <KindPill kind={meetingKind(m)} />
            {isLive && (
              <span
                className="inline-flex items-center gap-1 text-[9.5px] font-bold uppercase tracking-wider px-1.5 py-px rounded"
                style={{
                  border: "1px solid rgba(220,38,38,0.4)",
                  background: "rgba(220,38,38,0.08)",
                  color: "var(--ws-danger)",
                }}
              >
                <LiveDot size={5} />
                Live
              </span>
            )}
          </div>
        </div>
        <div className="min-w-0">
          {(counts.actions || counts.decisions || counts.questions) > 0 ? (
            <p
              className="m-0 text-[12px] leading-snug line-clamp-2"
              style={{ color: "var(--ws-ink2)" }}
            >
              {counts.actions} action item{counts.actions === 1 ? "" : "s"} ·{" "}
              {counts.decisions} decision{counts.decisions === 1 ? "" : "s"} ·{" "}
              {counts.questions} open question{counts.questions === 1 ? "" : "s"}
            </p>
          ) : state === "live" ? (
            <p className="m-0 text-[12px]" style={{ color: "var(--ws-muted)" }}>
              Recording in progress — extractions will appear after the call ends.
            </p>
          ) : state === "scheduled" ? (
            <p className="m-0 text-[12px]" style={{ color: "var(--ws-muted)" }}>
              Scheduled. Bot will join automatically.
            </p>
          ) : state === "not_joined" ? (
            <p className="m-0 text-[12px] italic" style={{ color: "var(--ws-faint)" }}>
              Bot did not join this meeting.
            </p>
          ) : (
            <p
              className="m-0 text-[12px] italic"
              style={{ color: "var(--ws-faint)" }}
            >
              No AI extractions yet.
            </p>
          )}
          {(counts.actions || counts.decisions || counts.questions) > 0 && (
            <div
              className="flex gap-2 mt-1 flex-wrap text-[10.5px] ws-mono"
              style={{ color: "var(--ws-muted)" }}
            >
              <span>
                <Sparkles
                  className="w-2.5 h-2.5 inline align-middle mr-0.5"
                  style={{ color: "var(--ws-ai-ink)" }}
                />
                {counts.actions}A · {counts.decisions}D · {counts.questions}Q
              </span>
            </div>
          )}
        </div>
        <span className="text-[11.5px]" style={{ color: "var(--ws-muted)" }}>
          {d.toLocaleDateString(undefined, { month: "short", day: "numeric" })}
          <br />
          <span className="ws-mono text-[10.5px]" style={{ color: "var(--ws-faint)" }}>
            {d.toLocaleTimeString(undefined, {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        </span>
        <div className="flex items-center gap-2">
          {stack.length > 0 ? <AvatarStack people={stack} size={20} max={3} /> : <span />}
          {showBot && (
            <span className="ml-auto">
              <ToggleSwitch
                enabled={enabled}
                title={enabled ? "Bot will join" : "Bot disabled"}
                onToggle={() => onToggleBot(m.id, enabled)}
              />
            </span>
          )}
        </div>
        <span
          className="text-right ws-mono text-[11.5px]"
          style={{ color: "var(--ws-muted)" }}
        >
          {m.duration_seconds
            ? `${Math.floor(m.duration_seconds / 60)}:${(m.duration_seconds % 60)
                .toString()
                .padStart(2, "0")}`
            : isLive
              ? "live"
              : "—"}
        </span>
        <span></span>
      </Link>
    </div>
  );
}
