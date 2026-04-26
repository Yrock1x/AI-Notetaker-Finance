"use client";

// Transcripts tab — three-column layout matching the design:
//
//   [meeting list rail]  [scrubber + transcript stream]  [AI extractions rail]
//
// Each column reads live data: the rail lists every meeting that has a
// completed transcript, the center column streams its segments, and the
// right rail surfaces the action items / decisions / questions extracted
// from that meeting's analyses.

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import {
  CheckCircle2,
  Download,
  HelpCircle,
  Play,
  Search,
  Sparkles,
} from "lucide-react";
import { useMeetings } from "@/hooks/use-meetings";
import {
  useTranscript,
  useTranscriptSegments,
} from "@/hooks/use-transcripts";
import { useDealExtractions } from "@/hooks/use-deal-extractions";
import { LoadingState } from "@/components/shared/loading-state";
import {
  Avatar,
  KindPill,
  PillButton,
  WSCard,
  avatarColor,
  initialsOf,
} from "@/components/workspace/primitives";
import { formatTimestamp } from "@/lib/utils";
import type { Meeting, TranscriptSegment } from "@/types";

function meetingHasTranscriptStatus(s: string): boolean {
  return ["transcribed", "analyzed", "ready", "analyzing"].includes(s);
}

export default function TranscriptsPage() {
  const params = useParams<{ dealId: string }>();
  const search = useSearchParams();
  const dealId = params.dealId;
  const initialId = search.get("meeting");
  const { data: meetingsResp } = useMeetings(dealId);
  const meetings = (meetingsResp?.items ?? []).filter((m) =>
    meetingHasTranscriptStatus(m.status),
  );

  const [activeId, setActiveId] = useState<string | null>(initialId);

  useEffect(() => {
    if (!activeId && meetings.length > 0) {
      setActiveId(meetings[0].id);
    }
  }, [activeId, meetings]);

  return (
    <div
      className="grid grid-cols-1 lg:grid-cols-[240px_1fr_280px] gap-3.5 px-7 pt-4 pb-10 items-start"
      style={{ background: "var(--ws-sub)", minHeight: "100%" }}
    >
      <MeetingsRail
        meetings={meetings}
        activeId={activeId}
        onSelect={setActiveId}
      />
      <div className="min-w-0">
        {activeId ? (
          <TranscriptViewer meetingId={activeId} dealId={dealId} />
        ) : (
          <div
            className="rounded-md p-6 text-[12.5px]"
            style={{
              background: "var(--ws-bg)",
              border: "1px solid var(--ws-border)",
              color: "var(--ws-muted)",
            }}
          >
            No transcribed meetings yet. Once a meeting finishes processing,
            its transcript appears here.
          </div>
        )}
      </div>
      <ExtractionsRail
        dealId={dealId}
        meetingId={activeId}
        meeting={meetings.find((m) => m.id === activeId)}
      />
    </div>
  );
}

function MeetingsRail({
  meetings,
  activeId,
  onSelect,
}: {
  meetings: Meeting[];
  activeId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <div
      className="ws-card overflow-hidden lg:sticky lg:top-3"
      style={{ alignSelf: "flex-start" }}
    >
      <div
        className="ws-card-header"
        style={{ background: "var(--ws-surface)" }}
      >
        <span className="ws-eyebrow">Transcripts · {meetings.length}</span>
      </div>
      {meetings.length === 0 ? (
        <div className="px-3.5 py-4 text-[12px]" style={{ color: "var(--ws-muted)" }}>
          No transcripts yet.
        </div>
      ) : (
        meetings.map((m, i) => {
          const isActive = m.id === activeId;
          const d = m.meeting_date ? new Date(m.meeting_date) : new Date(m.created_at);
          return (
            <div
              key={m.id}
              onClick={() => onSelect(m.id)}
              className="px-3.5 py-2.5 cursor-pointer transition-colors"
              style={{
                borderTop: i > 0 ? "1px solid var(--ws-border)" : undefined,
                background: isActive ? "var(--ws-ai-tint)" : "transparent",
                borderLeft: `2px solid ${isActive ? "var(--ws-ai-ink)" : "transparent"}`,
              }}
            >
              <div
                className="text-[12px] font-semibold truncate"
                style={{ color: "var(--ws-ink)" }}
              >
                {m.title}
              </div>
              <div
                className="text-[10.5px] mt-0.5 flex items-center gap-1.5 ws-mono"
                style={{ color: "var(--ws-muted)" }}
              >
                <span>{d.toLocaleDateString(undefined, { month: "short", day: "numeric" })}</span>
                {m.duration_seconds && (
                  <>
                    <span>·</span>
                    <span>{Math.floor(m.duration_seconds / 60)}m</span>
                  </>
                )}
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}

function TranscriptViewer({
  meetingId,
  dealId,
}: {
  meetingId: string;
  dealId: string;
}) {
  const { data: transcript } = useTranscript(meetingId);
  const { data: segmentsResp, isLoading } = useTranscriptSegments(meetingId);
  const [search, setSearch] = useState("");

  const segments = segmentsResp?.items ?? [];
  const filtered = useMemo(() => {
    if (!search.trim()) return segments;
    const s = search.toLowerCase();
    return segments.filter((seg) => seg.text.toLowerCase().includes(s));
  }, [search, segments]);

  // Auto-derive simple chapters at fixed intervals (every 8 minutes) until
  // the worker exposes a real chapter model. This mirrors the design's
  // visual without inventing fake content.
  const chapters = useMemo(() => {
    if (segments.length === 0) return [];
    const last = segments[segments.length - 1];
    const total = last.end_time;
    const interval = Math.max(60 * 8, Math.floor(total / 6));
    const out: { start: number; label: string }[] = [];
    for (let t = 0; t <= total; t += interval) {
      out.push({
        start: t,
        label: `${formatTimestamp(t)}`,
      });
    }
    return out;
  }, [segments]);

  return (
    <div className="ws-card overflow-hidden">
      <div
        className="px-4 py-3"
        style={{
          background: "linear-gradient(180deg, var(--ws-surface), var(--ws-bg))",
          borderBottom: "1px solid var(--ws-border)",
        }}
      >
        <div className="flex items-baseline gap-2 flex-wrap">
          <h3
            className="m-0 text-[14px] font-semibold tracking-tight"
            style={{ color: "var(--ws-ink)" }}
          >
            {transcript ? "Transcript" : "Loading…"}
          </h3>
          {transcript && (
            <span
              className="text-[11px]"
              style={{ color: "var(--ws-muted)" }}
            >
              {transcript.word_count.toLocaleString()} words ·{" "}
              {transcript.language?.toUpperCase()}
              {transcript.confidence_score != null && (
                <>
                  {" · "}
                  {Math.round(transcript.confidence_score * 100)}% confidence
                </>
              )}
            </span>
          )}
          <KindPill kind="External" />
          <div className="flex-1" />
          <Link href={`/deals/${dealId}/qa`}>
            <PillButton>
              <Sparkles
                className="w-2.5 h-2.5"
                style={{ color: "var(--ws-ai-ink)" }}
              />{" "}
              Ask about this
            </PillButton>
          </Link>
          <PillButton>
            <Download className="w-2.5 h-2.5" /> Export
          </PillButton>
        </div>

        {chapters.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-3">
            {chapters.map((c) => (
              <button
                key={c.start}
                type="button"
                className="px-2 py-1 rounded text-[10.5px] ws-mono"
                style={{
                  background: "var(--ws-bg)",
                  border: "1px solid var(--ws-border)",
                  color: "var(--ws-muted)",
                }}
              >
                {c.label}
              </button>
            ))}
          </div>
        )}
      </div>

      <div
        className="px-4 py-3 flex items-center gap-3"
        style={{ borderBottom: "1px solid var(--ws-border)" }}
      >
        <button
          type="button"
          className="w-[30px] h-[30px] rounded-full grid place-items-center"
          style={{
            background: "var(--ws-ink)",
            color: "#fff",
            border: "none",
          }}
        >
          <Play className="w-3 h-3" />
        </button>
        <span className="ws-mono text-[11.5px]" style={{ color: "var(--ws-muted)" }}>
          00:00
        </span>
        <div
          className="flex-1 h-1 rounded relative"
          style={{ background: "var(--ws-sub2)" }}
        >
          <div
            className="absolute left-0 top-0 h-full rounded"
            style={{ width: "0%", background: "var(--ws-ink)" }}
          />
        </div>
        <span className="ws-mono text-[11.5px]" style={{ color: "var(--ws-muted)" }}>
          {segments.length > 0
            ? formatTimestamp(segments[segments.length - 1].end_time)
            : "00:00"}
        </span>
      </div>

      <div
        className="px-4 py-2.5 flex items-center gap-2.5 flex-wrap"
        style={{ borderBottom: "1px solid var(--ws-border)" }}
      >
        <div
          className="flex-1 min-w-[240px] flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[12px]"
          style={{
            background: "var(--ws-surface)",
            border: "1px solid var(--ws-border)",
            color: "var(--ws-muted)",
          }}
        >
          <Search className="w-3 h-3" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search this transcript…"
            className="flex-1 bg-transparent outline-none border-none"
            style={{ color: "var(--ws-ink2)" }}
          />
          <span className="ws-mono text-[10px]" style={{ color: "var(--ws-faint)" }}>
            ⌘F
          </span>
        </div>
      </div>

      <div className="px-4 py-3 flex flex-col gap-3 max-h-[60vh] overflow-y-auto">
        {isLoading ? (
          <LoadingState message="Loading transcript…" />
        ) : filtered.length === 0 ? (
          <p className="text-[12px]" style={{ color: "var(--ws-muted)" }}>
            {search ? "No matches." : "No segments yet."}
          </p>
        ) : (
          filtered.map((seg) => <TranscriptLine key={seg.id} seg={seg} />)
        )}
      </div>
    </div>
  );
}

function TranscriptLine({ seg }: { seg: TranscriptSegment }) {
  const display = seg.speaker_name || seg.speaker_label;
  return (
    <div className="flex gap-3">
      <Avatar
        initials={initialsOf(display)}
        color={avatarColor(seg.speaker_label)}
        size={22}
      />
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2">
          <span
            className="text-[12px] font-semibold"
            style={{ color: "var(--ws-ink)" }}
          >
            {display}
          </span>
          <span
            className="ws-mono text-[10.5px]"
            style={{ color: "var(--ws-faint)" }}
          >
            {formatTimestamp(seg.start_time)}
          </span>
        </div>
        <p
          className="m-0 text-[13px] leading-relaxed"
          style={{ color: "var(--ws-ink2)" }}
        >
          {seg.text}
        </p>
      </div>
    </div>
  );
}

function ExtractionsRail({
  dealId,
  meetingId,
  meeting,
}: {
  dealId: string;
  meetingId: string | null;
  meeting?: Meeting;
}) {
  const { data: extractions } = useDealExtractions(dealId);
  if (!meetingId || !extractions) return <div />;

  const actions = extractions.actions.filter((a) => a.meetingId === meetingId);
  const decisions = extractions.decisions.filter((d) => d.meetingId === meetingId);
  const questions = extractions.questions.filter((q) => q.meetingId === meetingId);
  const quotes = extractions.quotes.filter((q) => q.meetingId === meetingId);

  return (
    <div className="flex flex-col gap-3 lg:sticky lg:top-3" style={{ alignSelf: "flex-start" }}>
      {meeting && (
        <WSCard title="Meeting">
          <div className="px-3.5 py-2.5">
            <div
              className="text-[13px] font-semibold leading-snug"
              style={{ color: "var(--ws-ink)" }}
            >
              {meeting.title}
            </div>
            <div
              className="text-[11px] mt-0.5"
              style={{ color: "var(--ws-muted)" }}
            >
              {(meeting.meeting_date
                ? new Date(meeting.meeting_date)
                : new Date(meeting.created_at)
              ).toLocaleString(undefined, {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })}
              {meeting.duration_seconds && (
                <> · {Math.round(meeting.duration_seconds / 60)} min</>
              )}
            </div>
          </div>
        </WSCard>
      )}

      <WSCard
        title="Action items"
        action={
          <span className="text-[11px] ws-mono" style={{ color: "var(--ws-muted)" }}>
            {actions.length}
          </span>
        }
      >
        {actions.length === 0 ? (
          <div className="px-3.5 py-3 text-[11.5px] italic" style={{ color: "var(--ws-faint)" }}>
            None extracted.
          </div>
        ) : (
          actions.map((a, i) => (
            <div
              key={a.id}
              className="px-3.5 py-2"
              style={{
                borderTop: i > 0 ? "1px solid var(--ws-border)" : undefined,
              }}
            >
              <div
                className="text-[12px] font-medium leading-snug"
                style={{ color: "var(--ws-ink)" }}
              >
                {a.text}
              </div>
              {(a.owner || a.due) && (
                <div
                  className="text-[10.5px] mt-0.5"
                  style={{ color: "var(--ws-muted)" }}
                >
                  {a.owner && <>{a.owner}</>}
                  {a.due && <> · due {a.due}</>}
                </div>
              )}
            </div>
          ))
        )}
      </WSCard>

      <WSCard
        title="Decisions"
        action={
          <span className="text-[11px] ws-mono" style={{ color: "var(--ws-muted)" }}>
            {decisions.length}
          </span>
        }
      >
        {decisions.length === 0 ? (
          <div className="px-3.5 py-3 text-[11.5px] italic" style={{ color: "var(--ws-faint)" }}>
            None logged.
          </div>
        ) : (
          decisions.map((d, i) => (
            <div
              key={d.id}
              className="flex gap-2 items-start px-3.5 py-2"
              style={{
                borderTop: i > 0 ? "1px solid var(--ws-border)" : undefined,
              }}
            >
              <CheckCircle2
                className="w-3 h-3 mt-0.5 shrink-0"
                style={{ color: "var(--ws-success)" }}
              />
              <div
                className="text-[12px] leading-snug"
                style={{ color: "var(--ws-ink2)" }}
              >
                {d.text}
              </div>
            </div>
          ))
        )}
      </WSCard>

      <WSCard
        title="Open questions"
        action={
          <span className="text-[11px] ws-mono" style={{ color: "var(--ws-muted)" }}>
            {questions.length}
          </span>
        }
      >
        {questions.length === 0 ? (
          <div className="px-3.5 py-3 text-[11.5px] italic" style={{ color: "var(--ws-faint)" }}>
            None.
          </div>
        ) : (
          questions.map((q, i) => (
            <div
              key={q.id}
              className="flex gap-2 items-start px-3.5 py-2"
              style={{
                borderTop: i > 0 ? "1px solid var(--ws-border)" : undefined,
              }}
            >
              <HelpCircle
                className="w-3 h-3 mt-0.5 shrink-0"
                style={{
                  color: q.answered ? "var(--ws-success)" : "var(--ws-warn)",
                }}
              />
              <div
                className="text-[12px] leading-snug"
                style={{ color: "var(--ws-ink2)" }}
              >
                {q.text}
              </div>
            </div>
          ))
        )}
      </WSCard>

      {quotes.length > 0 && (
        <WSCard title="Pull-quotes">
          {quotes.map((q, i) => (
            <div
              key={q.id}
              className="px-3.5 py-2.5"
              style={{
                borderTop: i > 0 ? "1px solid var(--ws-border)" : undefined,
              }}
            >
              <p
                className="m-0 text-[12px] italic leading-snug"
                style={{ color: "var(--ws-ink)" }}
              >
                “{q.text}”
              </p>
              {(q.speaker || q.timestamp) && (
                <div
                  className="text-[10.5px] mt-1"
                  style={{ color: "var(--ws-muted)" }}
                >
                  {q.speaker}
                  {q.timestamp && (
                    <span
                      className="ws-mono"
                      style={{ color: "var(--ws-faint)" }}
                    >
                      {" · "}
                      {q.timestamp}
                    </span>
                  )}
                </div>
              )}
            </div>
          ))}
        </WSCard>
      )}
    </div>
  );
}
