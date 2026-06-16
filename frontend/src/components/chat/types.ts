// Shared shapes for the global AI Chat: the deal/meeting scope union, the
// message model, and the citation deep-link helper.

import type { Citation } from "@/types";

export type Scope =
  | { kind: "deal"; dealId: string }
  | { kind: "meeting"; dealId: string; meetingId: string };

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
