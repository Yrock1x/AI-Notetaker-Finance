// Shared, time-aware derivation of meeting / bot "live" state.
//
// The DB `status` field alone is misleading: a bot that crashed or never
// finalized can be stuck at "recording" forever, and a "scheduled" meeting
// whose time has long passed isn't really upcoming. These helpers add a time
// gate so the UI doesn't show months-old calls as Live / Scheduled.

const STALE_LIVE_MS = 4 * 60 * 60 * 1000; // a real call won't run longer than this

export type MeetingDisplayState = "live" | "scheduled" | "not_joined" | "other";

type MeetingLike = {
  status: string;
  meeting_date?: string | null;
  created_at: string;
};

export function meetingDisplayState(m: MeetingLike): MeetingDisplayState {
  const whenMs = new Date(m.meeting_date || m.created_at).getTime();
  const now = Date.now();
  if (m.status === "recording") {
    // Live only if it started recently; otherwise the bot never finalized.
    return Number.isFinite(whenMs) && now - whenMs > STALE_LIVE_MS
      ? "not_joined"
      : "live";
  }
  if (m.status === "scheduled") {
    // Scheduled time passed and it never recorded → the bot didn't join.
    return Number.isFinite(whenMs) && whenMs < now ? "not_joined" : "scheduled";
  }
  return "other";
}

type BotSessionLike = {
  status: string;
  scheduled_start?: string | null;
  actual_start?: string | null;
  created_at?: string | null;
};

// A bot session is genuinely live only if it's recording/joining AND started
// recently — guards against stale sessions stuck in "recording".
export function isBotSessionLive(s: BotSessionLike): boolean {
  if (s.status !== "recording" && s.status !== "joining") return false;
  const ref = s.actual_start || s.scheduled_start || s.created_at;
  if (!ref) return true; // no timestamp to judge by → trust the status
  const whenMs = new Date(ref).getTime();
  return !Number.isFinite(whenMs) || Date.now() - whenMs <= STALE_LIVE_MS;
}
