"use client";

// Shared modal used to attach a calendar-synced meeting (deal_id=null) to
// a specific deal. Opened from the Dashboard "Upcoming meetings to
// assign" widget and from clicking an Unassigned card on the Calendar.
//
// - Auto-suggests a deal when the meeting title clearly points at one.
// - PATCHes the meeting via the worker REST API (PATCH /meetings/{id}),
//   which enforces org scoping server-side.

import { useMemo, useState, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { X, Bot, Sparkles, CalendarClock } from "lucide-react";
import { useDeals } from "@/hooks/use-deals";
import { useUpdateMeeting } from "@/hooks/use-meetings";
import { suggestDealForMeeting } from "@/lib/deal-matcher";
import { sendInngestEvent } from "@/lib/inngest-send";
import { ToggleSwitch } from "@/components/ui/toggle-switch";
import type { Meeting } from "@/types";

interface AssignMeetingDialogProps {
  meeting: Meeting | null;
  open: boolean;
  onClose: () => void;
}

export function AssignMeetingDialog({
  meeting,
  open,
  onClose,
}: AssignMeetingDialogProps) {
  const queryClient = useQueryClient();
  const { data: dealsPage } = useDeals({ limit: 100 });
  const deals = useMemo(() => dealsPage?.items ?? [], [dealsPage]);
  const updateMeeting = useUpdateMeeting(undefined);

  const suggestion = useMemo(
    () => (meeting ? suggestDealForMeeting(meeting, deals) : null),
    [meeting, deals]
  );

  const [dealId, setDealId] = useState("");
  const [botEnabled, setBotEnabled] = useState(true);
  const [error, setError] = useState("");

  // Reset + re-run the suggestion whenever the dialog is reopened for a
  // different meeting, or the deals list arrives after first paint.
  useEffect(() => {
    if (!open || !meeting) return;
    setDealId(suggestion?.deal_id ?? "");
    setBotEnabled(meeting.bot_enabled ?? true);
    setError("");
  }, [open, meeting, suggestion]);

  const assign = useMutation({
    mutationFn: async () => {
      if (!meeting) throw new Error("no meeting");
      if (!dealId) throw new Error("Please pick a deal.");
      await updateMeeting.mutateAsync({
        meetingId: meeting.id,
        patch: { deal_id: dealId, bot_enabled: botEnabled },
      });

      // Kick auto-schedule immediately so the bot spawns in seconds.
      // Without this nudge we'd wait for the next 5-min cron tick,
      // which is easy to miss when a user assigns a meeting that's
      // about to start (or just started).
      if (botEnabled) {
        try {
          await sendInngestEvent("bot/auto-schedule.requested");
        } catch (err) {
          // Non-fatal — the 5-min cron will catch it on the next tick. Log so a
          // persistent relay failure is visible rather than silently swallowed.
          console.warn("bot auto-schedule nudge failed", err);
        }
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["calendar", "meetings"] });
      queryClient.invalidateQueries({ queryKey: ["meetings"] });
      queryClient.invalidateQueries({
        queryKey: ["dashboard", "upcoming-unassigned"],
      });
      onClose();
    },
    onError: (e: unknown) => {
      setError(e instanceof Error ? e.message : "Failed to assign meeting.");
    },
  });

  if (!open || !meeting) return null;

  const suggestedId = suggestion?.deal_id;
  const meetingTime = meeting.meeting_date || meeting.created_at;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="mx-4 w-full max-w-lg rounded-lg bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CalendarClock className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-semibold">Assign meeting to a deal</h2>
          </div>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="mt-4 rounded-md border bg-muted/40 p-3 text-sm">
          <p className="font-medium">{meeting.title}</p>
          <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
            <span>
              {new Date(meetingTime).toLocaleString([], {
                weekday: "short",
                month: "short",
                day: "numeric",
                hour: "numeric",
                minute: "2-digit",
              })}
            </span>
            <span>·</span>
            <span>{meeting.source}</span>
          </div>
          {meeting.source_url && (
            <a
              href={meeting.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1 block truncate text-xs text-primary hover:underline"
            >
              {meeting.source_url}
            </a>
          )}
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            assign.mutate();
          }}
          className="mt-4 space-y-4"
        >
          {error && (
            <div className="rounded-md bg-red-50 p-3 text-sm text-red-800">
              {error}
            </div>
          )}

          <div>
            <div className="flex items-center justify-between">
              <label
                className="block text-sm font-medium"
                htmlFor="assign-deal"
              >
                Deal *
              </label>
              {suggestedId && dealId === suggestedId && (
                <span className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-emerald-600">
                  <Sparkles className="h-3 w-3" />
                  suggested
                </span>
              )}
            </div>
            <select
              id="assign-deal"
              value={dealId}
              onChange={(e) => setDealId(e.target.value)}
              required
              className="mt-1 w-full rounded-md border px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="">Select a deal…</option>
              {deals.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                  {d.target_company ? ` — ${d.target_company}` : ""}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center justify-between rounded-md border p-3">
            <div className="flex items-center gap-2 text-sm">
              <Bot className="h-4 w-4 text-primary" />
              <span>Auto-join with CogniSuite notetaker</span>
            </div>
            <ToggleSwitch
              enabled={botEnabled}
              onToggle={() => setBotEnabled((v) => !v)}
              title={
                botEnabled
                  ? "Bot will join when the meeting starts"
                  : "Bot disabled for this meeting"
              }
            />
          </div>

          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-muted"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!dealId || assign.isPending}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {assign.isPending ? "Assigning…" : "Assign"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
