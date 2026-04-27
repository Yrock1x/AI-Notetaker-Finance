"use client";

// Workspace live-recording banner — appears at the top of the deal
// workspace whenever any meeting in the deal has an active bot session
// (status: scheduled / joining / recording). Streams the latest transcript
// segments via the existing `useLiveTranscript` hook so the banner mirrors
// the live page's content without the user having to navigate there.

import { useEffect, useState } from "react";
import Link from "next/link";
import { Mic, Pause, Sparkles } from "lucide-react";
import { useBotSessions } from "@/hooks/use-bot-sessions";
import { useLiveTranscript } from "@/hooks/use-live-transcript";
import { useMeeting } from "@/hooks/use-meetings";
import { Avatar, avatarColor, initialsOf, LiveDot } from "./primitives";

interface LiveBannerProps {
  dealId: string;
}

// "Live" = bot is actually capturing audio. Scheduled means the bot
// hasn't joined yet, and joining is a short-lived transition with no
// transcript content yet — neither belongs on the banner. Anything else
// (completed / failed / cancelled) is also not live.
const LIVE_STATUSES = new Set(["recording"]);

function formatElapsed(startedAt: string | null | undefined): string {
  if (!startedAt) return "00:00";
  const start = new Date(startedAt).getTime();
  if (Number.isNaN(start)) return "00:00";
  const sec = Math.max(0, Math.floor((Date.now() - start) / 1000));
  const mm = Math.floor(sec / 60);
  const ss = sec % 60;
  if (mm >= 60) {
    const hh = Math.floor(mm / 60);
    return `${hh}:${(mm % 60).toString().padStart(2, "0")}:${ss.toString().padStart(2, "0")}`;
  }
  return `${mm.toString().padStart(2, "0")}:${ss.toString().padStart(2, "0")}`;
}

export function LiveBanner({ dealId }: LiveBannerProps) {
  const { data: sessions } = useBotSessions({ deal_id: dealId });
  const live = (sessions ?? []).find((s) => LIVE_STATUSES.has(s.status));
  if (!live || !live.meeting_id) return null;
  return (
    <LiveBannerInner
      dealId={dealId}
      sessionId={live.id}
      meetingId={live.meeting_id}
      startedAt={live.actual_start ?? live.scheduled_start ?? null}
    />
  );
}

function LiveBannerInner({
  dealId,
  meetingId,
  startedAt,
}: {
  dealId: string;
  sessionId: string;
  meetingId: string;
  startedAt: string | null;
}) {
  const { data: meeting } = useMeeting(dealId, meetingId);
  const { segments, isConnected } = useLiveTranscript(meetingId);
  // Force re-render every second so the elapsed timer ticks. We discard the
  // counter value itself and recompute elapsed from `startedAt` directly.
  const [, setTick] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, []);

  // Show last 3 segments. Filter partials so the cursor sits on the
  // newest actively-typed line.
  const recent = segments.slice(-3);
  const last = recent[recent.length - 1];

  return (
    <div
      className="border-b"
      style={{
        background: "linear-gradient(180deg, var(--ws-bg), rgba(220, 38, 38, 0.04))",
        borderColor: "var(--ws-border)",
      }}
    >
      <div className="px-7 py-3">
        <div className="flex flex-wrap items-center gap-2.5">
          <span
            className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10.5px] font-bold uppercase tracking-wider"
            style={{
              background: "rgba(220,38,38,0.10)",
              color: "var(--ws-danger)",
            }}
          >
            <LiveDot />
            Recording
          </span>
          <span
            className="text-[14px] font-semibold truncate max-w-[40ch]"
            style={{ color: "var(--ws-ink)" }}
          >
            {meeting?.title || "Live meeting"}
          </span>
          <span
            className="ws-mono text-[12px]"
            style={{ color: "var(--ws-muted)" }}
          >
            {formatElapsed(startedAt)}
          </span>
          <span
            className="text-[12px]"
            style={{ color: "var(--ws-faint)" }}
          >
            ·
          </span>
          <span
            className="text-[12px]"
            style={{ color: "var(--ws-muted)" }}
          >
            {isConnected ? "Streaming" : "Connecting…"}
          </span>
          <div className="flex-1" />
          <Link
            href={`/deals/${dealId}/meetings/${meetingId}/live`}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[12px] font-semibold"
            style={{
              background: "var(--ws-bg)",
              border: "1px solid var(--ws-border-strong)",
              color: "var(--ws-ink2)",
            }}
          >
            Open live
          </Link>
          <button
            type="button"
            disabled
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[12px] font-semibold opacity-60 cursor-not-allowed"
            style={{
              background: "var(--ws-bg)",
              border: "1px solid var(--ws-border-strong)",
              color: "var(--ws-ink2)",
            }}
            title="Pause is controlled from the meeting platform"
          >
            <Pause className="w-3 h-3" /> Pause
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-3 mt-2.5">
          <div
            className="rounded-md p-3 text-[12.5px] leading-snug flex flex-col gap-2 min-h-[110px]"
            style={{
              background: "var(--ws-bg)",
              border: "1px solid var(--ws-border)",
              color: "var(--ws-ink2)",
            }}
          >
            <div
              className="ws-eyebrow inline-flex items-center gap-1.5 normal-case"
              style={{ textTransform: "uppercase" }}
            >
              <Mic className="w-3 h-3" /> Live transcript
              <span
                className="ml-auto text-[10px] font-medium normal-case tracking-normal"
                style={{ color: "var(--ws-faint)" }}
              >
                auto-scroll
              </span>
            </div>
            {recent.length === 0 ? (
              <p
                className="m-0 text-[12px]"
                style={{ color: "var(--ws-faint)" }}
              >
                Waiting for the meeting to start…
              </p>
            ) : (
              recent.map((s) => {
                const isLast = s.id === last.id;
                const initials = initialsOf(s.speaker_name || s.speaker_label);
                return (
                  <div
                    key={s.id}
                    className={`flex gap-2 ${isLast ? "ws-fadeup opacity-100" : "opacity-60"}`}
                  >
                    <Avatar
                      initials={initials}
                      color={avatarColor(s.speaker_label)}
                      size={20}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-baseline gap-1.5">
                        <span
                          className="text-[11.5px] font-semibold"
                          style={{ color: "var(--ws-ink)" }}
                        >
                          {(s.speaker_name || s.speaker_label).split(" ")[0]}
                        </span>
                        <span
                          className="ws-mono text-[10px]"
                          style={{ color: "var(--ws-faint)" }}
                        >
                          {Math.floor(s.start_time / 60)
                            .toString()
                            .padStart(2, "0")}
                          :
                          {Math.floor(s.start_time % 60)
                            .toString()
                            .padStart(2, "0")}
                        </span>
                      </div>
                      <p className="m-0 text-[12.5px] leading-snug">
                        {s.text}
                        {isLast && <span className="ws-cursor" style={{ color: "var(--ws-ink2)" }} />}
                      </p>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          <div
            className="rounded-md p-3 flex flex-col gap-1.5 min-h-[110px]"
            style={{
              background: "var(--ws-ai-tint)",
              border: "1px solid var(--ws-border)",
            }}
          >
            <div
              className="ws-eyebrow inline-flex items-center gap-1.5"
              style={{ color: "var(--ws-ai-ink)" }}
            >
              <Sparkles className="w-3 h-3" /> Cogni · live extractions
              <span
                className="ml-auto text-[10px] font-medium normal-case tracking-normal"
                style={{ color: "var(--ws-muted)" }}
              >
                synthesizing as people speak
              </span>
            </div>
            <p
              className="m-0 text-[12px] italic"
              style={{ color: "var(--ws-muted)" }}
            >
              Decisions, questions, and commitments will surface here once the
              call has a few minutes of dialogue.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
