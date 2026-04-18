"use client";

// The live transcript scroll panel, extracted from
// app/(app)/deals/[dealId]/meetings/[meetingId]/live/page.tsx so the
// meeting detail page can embed it as a "Live" tab while the bot is
// recording.

import { useEffect, useRef } from "react";
import { Circle, Radio } from "lucide-react";
import { useLiveTranscript } from "@/hooks/use-live-transcript";
import { LoadingState } from "@/components/shared/loading-state";

const SPEAKER_COLORS = [
  "text-emerald-700",
  "text-blue-700",
  "text-purple-700",
  "text-amber-700",
  "text-rose-700",
  "text-sky-700",
];

function speakerColor(label: string): string {
  let hash = 0;
  for (let i = 0; i < label.length; i++) {
    hash = (hash + label.charCodeAt(i)) >>> 0;
  }
  return SPEAKER_COLORS[hash % SPEAKER_COLORS.length];
}

function formatClock(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

export function LiveTranscriptPanel({
  meetingId,
  heightClass = "h-[70vh]",
}: {
  meetingId: string;
  heightClass?: string;
}) {
  const { segments, isConnected, isInitialLoading } = useLiveTranscript(meetingId);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const stickToBottomRef = useRef(true);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el || !stickToBottomRef.current) return;
    el.scrollTop = el.scrollHeight;
  }, [segments]);

  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    stickToBottomRef.current = atBottom;
  };

  if (isInitialLoading) {
    return <LoadingState message="Connecting to live transcript…" />;
  }

  return (
    <div className={`flex flex-col gap-3 ${heightClass}`}>
      <div className="flex items-center justify-end gap-2">
        {isConnected ? (
          <>
            <Radio className="h-4 w-4 text-emerald-500 animate-pulse" />
            <span className="text-xs font-data uppercase tracking-widest text-emerald-600">
              Live
            </span>
          </>
        ) : (
          <>
            <Circle className="h-4 w-4 text-[#1A1A1A]/20" />
            <span className="text-xs font-data uppercase tracking-widest text-[#1A1A1A]/40">
              Disconnected
            </span>
          </>
        )}
      </div>
      <div
        ref={scrollRef}
        onScroll={onScroll}
        className="flex-1 overflow-y-auto rounded-2xl border border-[#1A1A1A]/5 bg-white p-6 space-y-3"
      >
        {segments.length === 0 ? (
          <p className="text-sm text-[#1A1A1A]/40">
            Waiting for the meeting to start — words will appear here as
            people speak.
          </p>
        ) : (
          segments.map((seg) => (
            <div key={seg.recall_segment_id || seg.id} className="flex gap-3">
              <div className="flex-shrink-0 w-14 pt-0.5 text-[10px] font-data uppercase text-[#1A1A1A]/30">
                {formatClock(seg.start_time)}
              </div>
              <div className="flex-1 min-w-0">
                <div
                  className={`text-xs font-heading font-bold ${speakerColor(seg.speaker_label)}`}
                >
                  {seg.speaker_name || seg.speaker_label}
                </div>
                <p
                  className={`text-sm leading-relaxed ${
                    seg.is_partial
                      ? "italic text-[#1A1A1A]/50"
                      : "text-[#1A1A1A]/85"
                  }`}
                >
                  {seg.text}
                </p>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
