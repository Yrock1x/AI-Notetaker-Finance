// Shared shapes for the global AI Chat: the deal/meeting scope union, the
// message model, and the citation deep-link helper.

import type { Citation } from "@/types";

export type Scope =
  | { kind: "deal"; dealId: string }
  | { kind: "meeting"; dealId: string; meetingId: string }
  | { kind: "meetings"; dealId: string; meetingIds: string[] };

// The selected meeting ids implied by a scope ([] for deal-wide / no scope).
export function selectedMeetingIds(scope: Scope | null): string[] {
  if (!scope) return [];
  if (scope.kind === "meeting") return [scope.meetingId];
  if (scope.kind === "meetings") return scope.meetingIds;
  return [];
}

// Collapse a selection set back to the narrowest scope within a deal:
// none → deal, one → single-meeting (optimized path), many → subset.
export function scopeFromMeetingIds(dealId: string, ids: string[]): Scope {
  if (ids.length === 0) return { kind: "deal", dealId };
  if (ids.length === 1) return { kind: "meeting", dealId, meetingId: ids[0] };
  return { kind: "meetings", dealId, meetingIds: ids };
}

export interface ChatMsg {
  id: string;
  role: "user" | "ai";
  text: string;
  citations?: Citation[];
  pending?: boolean;
  scope: Scope;
  groundingScore?: number;
}

export const SUGGESTIONS = [
  "Summarize this deal's last 5 meetings",
  "What action items are due this week?",
  "Which questions came up but never got answered?",
  "Compare what management said vs the CFO",
  "Draft an IC pre-read from this week's calls",
];

export function citationHref(c: Citation, dealId: string): string | null {
  type CWithMeta = Citation & { meeting_id?: string; start_time?: number };
  const cm = c as CWithMeta;
  if (c.source_type === "transcript_segment" && cm.meeting_id) {
    const frag = cm.start_time != null ? `#t=${cm.start_time}` : "";
    return `/deals/${dealId}/meetings/${cm.meeting_id}${frag}`;
  }
  return null;
}
