"use client";

// Global AI Chat — pick a deal (and optionally a meeting within it), then
// ask questions against the worker's /qa endpoints.

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import dynamic from "next/dynamic";
import { MessageSquare, Briefcase, Clock } from "lucide-react";
import { useDeals } from "@/hooks/use-deals";
import { useMeetings } from "@/hooks/use-meetings";
import { EmptyState } from "@/components/shared/empty-state";
import { LoadingState } from "@/components/shared/loading-state";

const QAChat = dynamic(
  () => import("@/components/qa/qa-chat").then((m) => ({ default: m.QAChat })),
  { loading: () => <LoadingState message="Loading chat…" /> }
);

const NO_MEETING = "all";

export default function ChatPage() {
  return (
    <Suspense fallback={<LoadingState message="Loading…" />}>
      <ChatContent />
    </Suspense>
  );
}

function ChatContent() {
  const router = useRouter();
  const search = useSearchParams();
  const { data: dealsResp, isLoading: dealsLoading } = useDeals();
  const deals = dealsResp?.items ?? [];

  const [dealId, setDealId] = useState<string>(search.get("deal") ?? "");
  const [meetingId, setMeetingId] = useState<string>(
    search.get("meeting") ?? NO_MEETING
  );

  // Auto-select the first deal once loaded if nothing is in the URL.
  useEffect(() => {
    if (!dealId && deals.length > 0) {
      setDealId(deals[0].id);
    }
  }, [deals, dealId]);

  // Sync URL so the choice is shareable + survives a refresh.
  useEffect(() => {
    if (!dealId) return;
    const params = new URLSearchParams();
    params.set("deal", dealId);
    if (meetingId !== NO_MEETING) params.set("meeting", meetingId);
    router.replace(`/chat?${params.toString()}`, { scroll: false });
  }, [dealId, meetingId, router]);

  const { data: meetingsResp } = useMeetings(dealId || undefined);
  const meetings = meetingsResp?.items ?? [];

  const selectedDeal = deals.find((d) => d.id === dealId);
  const selectedMeeting =
    meetingId !== NO_MEETING
      ? meetings.find((m) => m.id === meetingId)
      : undefined;

  // If the user switches deals, clear the meeting filter if it's no longer valid.
  useEffect(() => {
    if (meetingId === NO_MEETING) return;
    if (!meetings.some((m) => m.id === meetingId)) {
      setMeetingId(NO_MEETING);
    }
  }, [meetingId, meetings]);

  if (dealsLoading) {
    return <LoadingState message="Loading deals…" />;
  }

  if (deals.length === 0) {
    return (
      <EmptyState
        title="No deals yet"
        description="Create a deal and add a meeting or document to start asking questions."
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-4xl font-heading font-extrabold tracking-tight text-primary">
          AI Chat
        </h1>
        <p className="font-subheading text-[#1A1A1A]/60 text-sm font-medium">
          Ask questions about any deal&apos;s transcripts and documents. Select
          a meeting to scope the answer to that call only.
        </p>
      </div>

      {/* Selector row */}
      <div className="grid gap-3 md:grid-cols-2">
        <label className="space-y-1.5 block">
          <span className="flex items-center gap-1.5 text-xs font-data uppercase tracking-widest text-[#1A1A1A]/40 font-bold ml-1">
            <Briefcase className="h-3 w-3" />
            Deal
          </span>
          <select
            value={dealId}
            onChange={(e) => setDealId(e.target.value)}
            className="w-full rounded-[1.5rem] border border-[#1A1A1A]/10 bg-white px-6 py-4 text-sm font-subheading focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent transition-all"
          >
            {deals.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
                {d.target_company ? ` — ${d.target_company}` : ""}
              </option>
            ))}
          </select>
        </label>

        <label className="space-y-1.5 block">
          <span className="flex items-center gap-1.5 text-xs font-data uppercase tracking-widest text-[#1A1A1A]/40 font-bold ml-1">
            <Clock className="h-3 w-3" />
            Meeting (optional)
          </span>
          <select
            value={meetingId}
            onChange={(e) => setMeetingId(e.target.value)}
            disabled={meetings.length === 0}
            className="w-full rounded-[1.5rem] border border-[#1A1A1A]/10 bg-white px-6 py-4 text-sm font-subheading focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent transition-all disabled:opacity-60"
          >
            <option value={NO_MEETING}>All meetings + documents</option>
            {meetings.map((m) => (
              <option key={m.id} value={m.id}>
                {m.title}
                {m.meeting_date
                  ? ` — ${new Date(m.meeting_date).toLocaleDateString()}`
                  : ""}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* Scope hint */}
      <div className="flex items-center gap-2 rounded-2xl border border-[#1A1A1A]/5 bg-[#F2F0E9]/40 px-4 py-3 text-xs text-[#1A1A1A]/60">
        <MessageSquare className="h-3.5 w-3.5" />
        {selectedMeeting ? (
          <span>
            Asking about <strong>{selectedMeeting.title}</strong>
            {selectedDeal ? ` in ${selectedDeal.name}` : ""}.
          </span>
        ) : selectedDeal ? (
          <span>
            Asking across all transcripts + documents in{" "}
            <strong>{selectedDeal.name}</strong>.
          </span>
        ) : (
          <span>Select a deal to begin.</span>
        )}
      </div>

      {/* Chat surface */}
      {selectedDeal ? (
        selectedMeeting ? (
          <QAChat
            key={`m-${selectedMeeting.id}`}
            scope="meeting"
            meetingId={selectedMeeting.id}
            dealId={selectedDeal.id}
          />
        ) : (
          <QAChat
            key={`d-${selectedDeal.id}`}
            scope="deal"
            dealId={selectedDeal.id}
          />
        )
      ) : null}
    </div>
  );
}
