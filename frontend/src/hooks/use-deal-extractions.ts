"use client";

// Aggregates AI extractions (action items, decisions, open questions, key
// quotes) for an entire deal by reading every meeting's analyses rows from
// Supabase and pulling them out of `analyses.structured_output`.
//
// The pipeline today writes a freeform jsonb blob keyed by `analysis_type`,
// so we accept the common keys (action_items / decisions / questions /
// open_questions / pull_quotes / key_quotes / chapters) and normalize them
// into a single shape the workspace UI can consume.

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/worker-api";
import { useMeetings } from "./use-meetings";

export interface ExtractedAction {
  id: string;
  text: string;
  owner?: string;
  due?: string;
  status: "open" | "in_review" | "scheduled" | "done";
  meetingId: string;
  meetingTitle: string;
  meetingDate?: string | null;
  timestamp?: string;
  // Source analysis row — needed by the completion-persistence FK.
  analysisId: string;
}

export interface ExtractedDecision {
  id: string;
  text: string;
  meetingId: string;
  meetingTitle: string;
  meetingDate?: string | null;
  timestamp?: string;
}

export interface ExtractedQuestion {
  id: string;
  text: string;
  meetingId: string;
  meetingTitle: string;
  meetingDate?: string | null;
  answered?: boolean;
}

export interface ExtractedQuote {
  id: string;
  text: string;
  speaker?: string;
  timestamp?: string;
  meetingId: string;
  meetingTitle: string;
}

export interface DealExtractions {
  actions: ExtractedAction[];
  decisions: ExtractedDecision[];
  questions: ExtractedQuestion[];
  quotes: ExtractedQuote[];
}

interface AnalysisRow {
  id: string;
  meeting_id: string;
  structured_output: unknown;
  created_at: string;
}

interface MeetingRow {
  id: string;
  title: string | null;
  meeting_date: string | null;
}

function asArray(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}

function pick(obj: Record<string, unknown>, keys: string[]): unknown {
  for (const k of keys) {
    if (k in obj) return obj[k];
  }
  return undefined;
}

function str(v: unknown): string | undefined {
  if (typeof v === "string") return v.trim() || undefined;
  return undefined;
}

function normalizeStatus(v: unknown): ExtractedAction["status"] {
  const s = (str(v) || "").toLowerCase();
  if (s === "in_review" || s === "review" || s === "in review") return "in_review";
  if (s === "scheduled") return "scheduled";
  if (s === "done" || s === "completed" || s === "complete") return "done";
  return "open";
}

export function useDealExtractions(dealId: string | undefined) {
  // Reuse the shared ["meetings", dealId] query for meeting titles/dates rather
  // than fetching /meetings again here (it was the 3rd duplicate fetch per deal
  // navigation); only /extractions is fetched below, once meetings are ready.
  const meetingsQ = useMeetings(dealId);
  return useQuery<DealExtractions>({
    queryKey: ["deal-extractions", dealId],
    enabled: !!dealId && meetingsQ.isSuccess,
    staleTime: 60_000,
    queryFn: async () => {
      const meetings = meetingsQ.data?.items ?? [];
      const analyses = await apiGet<AnalysisRow[]>(
        `/deals/${dealId}/extractions`,
      );

      const meetingMap = new Map<string, MeetingRow>(
        meetings.map((m) => [
          m.id,
          { id: m.id, title: m.title ?? null, meeting_date: m.meeting_date ?? null },
        ]),
      );

      const actions: ExtractedAction[] = [];
      const decisions: ExtractedDecision[] = [];
      const questions: ExtractedQuestion[] = [];
      const quotes: ExtractedQuote[] = [];

      for (const a of analyses) {
        const m = meetingMap.get(a.meeting_id);
        const meetingTitle = m?.title || "Untitled meeting";
        const meetingDate = m?.meeting_date ?? null;

        const out =
          a.structured_output && typeof a.structured_output === "object"
            ? (a.structured_output as Record<string, unknown>)
            : {};

        // Action items
        const aiList = asArray(pick(out, ["action_items", "actions", "tasks"]));
        aiList.forEach((raw, i) => {
          if (raw && typeof raw === "object") {
            const r = raw as Record<string, unknown>;
            const text = str(pick(r, ["text", "task", "description", "title"]));
            if (!text) return;
            actions.push({
              id: `${a.id}-act-${i}`,
              analysisId: a.id,
              text,
              owner: str(pick(r, ["owner", "assignee", "responsible"])),
              due: str(pick(r, ["due", "due_date", "deadline"])),
              status: normalizeStatus(pick(r, ["status", "state"])),
              timestamp: str(pick(r, ["timestamp", "at", "ts"])),
              meetingId: a.meeting_id,
              meetingTitle,
              meetingDate,
            });
          } else if (typeof raw === "string" && raw.trim()) {
            actions.push({
              id: `${a.id}-act-${i}`,
              analysisId: a.id,
              text: raw,
              status: "open",
              meetingId: a.meeting_id,
              meetingTitle,
              meetingDate,
            });
          }
        });

        // Decisions
        const decList = asArray(pick(out, ["decisions", "decisions_made"]));
        decList.forEach((raw, i) => {
          const text =
            typeof raw === "string"
              ? raw
              : str(
                  pick(raw as Record<string, unknown>, [
                    "text",
                    "decision",
                    "title",
                    "description",
                  ]),
                );
          if (!text) return;
          const r = (typeof raw === "object" ? raw : {}) as Record<string, unknown>;
          decisions.push({
            id: `${a.id}-dec-${i}`,
            text,
            timestamp: str(pick(r, ["timestamp", "at", "ts"])),
            meetingId: a.meeting_id,
            meetingTitle,
            meetingDate,
          });
        });

        // Open questions
        const qList = asArray(
          pick(out, ["open_questions", "questions", "unanswered_questions"]),
        );
        qList.forEach((raw, i) => {
          const text =
            typeof raw === "string"
              ? raw
              : str(
                  pick(raw as Record<string, unknown>, [
                    "text",
                    "question",
                    "title",
                  ]),
                );
          if (!text) return;
          const r = (typeof raw === "object" ? raw : {}) as Record<string, unknown>;
          questions.push({
            id: `${a.id}-q-${i}`,
            text,
            answered: Boolean(pick(r, ["answered", "is_answered"])),
            meetingId: a.meeting_id,
            meetingTitle,
            meetingDate,
          });
        });

        // Pull quotes
        const qtList = asArray(
          pick(out, ["pull_quotes", "key_quotes", "highlights"]),
        );
        qtList.forEach((raw, i) => {
          const text =
            typeof raw === "string"
              ? raw
              : str(
                  pick(raw as Record<string, unknown>, [
                    "text",
                    "quote",
                    "body",
                  ]),
                );
          if (!text) return;
          const r = (typeof raw === "object" ? raw : {}) as Record<string, unknown>;
          quotes.push({
            id: `${a.id}-qt-${i}`,
            text,
            speaker: str(pick(r, ["speaker", "sp", "speaker_label"])),
            timestamp: str(pick(r, ["timestamp", "at", "ts"])),
            meetingId: a.meeting_id,
            meetingTitle,
          });
        });
      }

      return { actions, decisions, questions, quotes };
    },
  });
}
