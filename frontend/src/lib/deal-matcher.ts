// Pre-fills the deal picker when a synced meeting obviously belongs to
// one specific deal. Conservative by design: we only return a match when
// the top score beats the runner-up, so ambiguous cases (generic titles,
// two similarly-named deals) still fall back to manual selection.

import type { Deal, Meeting } from "@/types";

const STOP_WORDS = new Set([
  "and",
  "the",
  "for",
  "with",
  "meeting",
  "call",
  "sync",
  "review",
  "weekly",
  "monthly",
  "prep",
  "kickoff",
  "follow",
  "followup",
]);

function tokenize(text: string | null | undefined): Set<string> {
  if (!text) return new Set();
  return new Set(
    text
      .toLowerCase()
      .split(/[\s\-_/|,.:;()&]+/)
      .filter((w) => w.length >= 3 && !STOP_WORDS.has(w))
  );
}

export interface DealSuggestion {
  deal_id: string;
  reason: "target_company" | "name";
}

export function suggestDealForMeeting(
  meeting: Pick<Meeting, "title">,
  deals: Deal[]
): DealSuggestion | null {
  const titleTokens = tokenize(meeting.title);
  if (titleTokens.size === 0) return null;

  let best: { deal: Deal; score: number; reason: DealSuggestion["reason"] } | null = null;
  let runnerUp = 0;

  for (const deal of deals) {
    const target = tokenize(deal.target_company);
    const name = tokenize(deal.name);

    let score = 0;
    let reason: DealSuggestion["reason"] = "name";
    for (const t of titleTokens) {
      if (target.has(t)) {
        score += 2;
        reason = "target_company";
      } else if (name.has(t)) {
        score += 1;
      }
    }

    if (!best || score > best.score) {
      runnerUp = best?.score ?? 0;
      best = { deal, score, reason };
    } else if (score > runnerUp) {
      runnerUp = score;
    }
  }

  // Require a clear winner: score ≥ 2 AND strictly greater than the
  // runner-up so two deals that both match weakly don't produce a
  // misleading pre-fill.
  if (!best || best.score < 2 || best.score <= runnerUp) return null;
  return { deal_id: best.deal.id, reason: best.reason };
}
