"use client";

// Schedule a Recall.ai notetaker for any meeting URL, from inside a deal
// context (dealId provided) or the global calendar (dealId needs to be
// picked). Writes a meeting_bot_sessions row and fires bot/scheduled;
// the Inngest function turns that into a live bot against Recall.ai.

import { useState, useEffect } from "react";
import { X, Bot, Sparkles } from "lucide-react";
import { useScheduleBot, type BotSession } from "@/hooks/use-bot-sessions";
import { useDeals } from "@/hooks/use-deals";
import { getBrowserSupabase } from "@/lib/supabase/browser";

interface ScheduleBotDialogProps {
  open: boolean;
  onClose: () => void;
  dealId?: string;
}

function detectPlatform(url: string): BotSession["platform"] | null {
  const u = url.toLowerCase();
  if (u.includes("zoom.us")) return "zoom";
  if (u.includes("teams.microsoft.com") || u.includes("teams.live.com"))
    return "teams";
  if (u.includes("meet.google.com")) return "google_meet";
  return null;
}

export function ScheduleBotDialog({
  open,
  onClose,
  dealId: presetDealId,
}: ScheduleBotDialogProps) {
  const [meetingUrl, setMeetingUrl] = useState("");
  const [title, setTitle] = useState("");
  const [titleWasAutofilled, setTitleWasAutofilled] = useState(false);
  const [platform, setPlatform] = useState<BotSession["platform"]>("zoom");
  const [dealId, setDealId] = useState<string>(presetDealId ?? "");
  const [scheduledStart, setScheduledStart] = useState<string>("");
  const [matchedMeetingId, setMatchedMeetingId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const { data: deals } = useDeals(presetDealId ? undefined : { limit: 100 });
  const scheduleBot = useScheduleBot();

  // Auto-pick platform when the user pastes a URL.
  useEffect(() => {
    const detected = detectPlatform(meetingUrl);
    if (detected) setPlatform(detected);
  }, [meetingUrl]);

  // Auto-fill the title (and reuse the meeting_id) when the pasted URL
  // matches a calendar-synced meeting we already have. Debounced so we
  // don't hit Supabase on every keystroke. Only overrides the title when
  // the user hasn't typed one of their own.
  useEffect(() => {
    if (!meetingUrl) {
      setMatchedMeetingId(null);
      if (titleWasAutofilled) setTitle("");
      return;
    }
    const handle = setTimeout(async () => {
      const supabase = getBrowserSupabase();
      const { data } = await supabase
        .from("meetings")
        .select("id, title")
        .eq("source_url", meetingUrl)
        .limit(1);
      const hit = data?.[0];
      if (hit) {
        setMatchedMeetingId(hit.id);
        if (!title || titleWasAutofilled) {
          setTitle(hit.title ?? "");
          setTitleWasAutofilled(true);
        }
      } else {
        setMatchedMeetingId(null);
        if (titleWasAutofilled) {
          setTitle("");
          setTitleWasAutofilled(false);
        }
      }
    }, 300);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meetingUrl]);

  // When the parent-provided dealId changes (e.g. dialog reused across deals),
  // reset the local value so we don't carry stale state across opens.
  useEffect(() => {
    if (presetDealId) setDealId(presetDealId);
  }, [presetDealId]);

  if (!open) return null;

  const reset = () => {
    setMeetingUrl("");
    setTitle("");
    setTitleWasAutofilled(false);
    setMatchedMeetingId(null);
    setPlatform("zoom");
    setScheduledStart("");
    setError("");
    if (!presetDealId) setDealId("");
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!dealId) {
      setError("Please pick a deal.");
      return;
    }
    if (!meetingUrl) {
      setError("Please paste the meeting URL.");
      return;
    }

    setSubmitting(true);
    try {
      await scheduleBot.mutateAsync({
        deal_id: dealId,
        platform,
        meeting_url: meetingUrl,
        scheduled_start: scheduledStart || null,
        title: title.trim() || null,
        meeting_id: matchedMeetingId,
      });
      reset();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to schedule bot");
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="mx-4 w-full max-w-lg rounded-lg bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-semibold">Schedule Notetaker</h2>
          </div>
          <button
            onClick={reset}
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <p className="mt-2 text-xs text-muted-foreground">
          The Recall.ai bot will join the call, record it, and stream a live
          transcript. Works with Zoom, Teams, and Google Meet links.
        </p>

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          {error && (
            <div className="rounded-md bg-red-50 p-3 text-sm text-red-800">
              {error}
            </div>
          )}

          {/* Deal picker — only when no preset dealId was passed */}
          {!presetDealId && (
            <div>
              <label className="block text-sm font-medium" htmlFor="bot-deal">
                Deal *
              </label>
              <select
                id="bot-deal"
                value={dealId}
                onChange={(e) => setDealId(e.target.value)}
                required
                className="mt-1 w-full rounded-md border px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="">Select a deal…</option>
                {(deals?.items ?? []).map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                    {d.target_company ? ` — ${d.target_company}` : ""}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div>
            <div className="flex items-center justify-between">
              <label className="block text-sm font-medium" htmlFor="bot-title">
                Meeting title
              </label>
              {titleWasAutofilled && matchedMeetingId && (
                <span className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-emerald-600">
                  <Sparkles className="h-3 w-3" />
                  matched from calendar
                </span>
              )}
            </div>
            <input
              id="bot-title"
              type="text"
              value={title}
              onChange={(e) => {
                setTitle(e.target.value);
                if (titleWasAutofilled) setTitleWasAutofilled(false);
              }}
              placeholder="e.g. Acme Corp — management presentation"
              className="mt-1 w-full rounded-md border px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>

          <div>
            <label className="block text-sm font-medium" htmlFor="bot-url">
              Meeting URL *
            </label>
            <input
              id="bot-url"
              type="url"
              required
              value={meetingUrl}
              onChange={(e) => setMeetingUrl(e.target.value)}
              placeholder="https://zoom.us/j/... or https://teams.microsoft.com/l/..."
              className="mt-1 w-full rounded-md border px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label
                className="block text-sm font-medium"
                htmlFor="bot-platform"
              >
                Platform *
              </label>
              <select
                id="bot-platform"
                value={platform}
                onChange={(e) =>
                  setPlatform(e.target.value as BotSession["platform"])
                }
                className="mt-1 w-full rounded-md border px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="zoom">Zoom</option>
                <option value="teams">Microsoft Teams</option>
                <option value="google_meet">Google Meet</option>
              </select>
            </div>

            <div>
              <label
                className="block text-sm font-medium"
                htmlFor="bot-start"
              >
                Starts at (optional)
              </label>
              <input
                id="bot-start"
                type="datetime-local"
                value={scheduledStart}
                onChange={(e) => setScheduledStart(e.target.value)}
                className="mt-1 w-full rounded-md border px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
          </div>

          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={reset}
              className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-muted"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting || !dealId || !meetingUrl}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {submitting ? "Scheduling…" : "Schedule Notetaker"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
