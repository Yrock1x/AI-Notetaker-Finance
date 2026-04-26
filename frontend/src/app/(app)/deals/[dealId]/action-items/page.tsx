"use client";

// Action Items tab — kanban + by-owner views over the AI-extracted action
// items pulled from analyses.structured_output. Decisions + open questions
// trail below as cards. Read-only for now; checkbox toggles are visual
// only until the worker exposes a write endpoint for the extraction
// store.

import { useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  CheckCircle2,
  Grid3x3,
  HelpCircle,
  List,
  Plus,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { useDealExtractions, type ExtractedAction } from "@/hooks/use-deal-extractions";
import {
  Avatar,
  PillButton,
  Segmented,
  WSCard,
  avatarColor,
  initialsOf,
} from "@/components/workspace/primitives";

type View = "kanban" | "byOwner";

const STATUS_COLUMNS: { key: ExtractedAction["status"]; label: string; tone: string }[] = [
  { key: "open", label: "Open", tone: "var(--ws-warn)" },
  { key: "in_review", label: "In review", tone: "var(--ws-ai-ink)" },
  { key: "scheduled", label: "Scheduled", tone: "var(--ws-accent)" },
  { key: "done", label: "Done", tone: "var(--ws-success)" },
];

export default function ActionItemsPage() {
  const params = useParams<{ dealId: string }>();
  const dealId = params.dealId;
  const { data, isLoading } = useDealExtractions(dealId);
  const [view, setView] = useState<View>("kanban");

  const actions = data?.actions ?? [];
  const decisions = data?.decisions ?? [];
  const questions = data?.questions ?? [];

  const byStatus = useMemo(() => {
    const groups: Record<ExtractedAction["status"], ExtractedAction[]> = {
      open: [],
      in_review: [],
      scheduled: [],
      done: [],
    };
    for (const a of actions) groups[a.status].push(a);
    return groups;
  }, [actions]);

  const byOwner = useMemo(() => {
    const map = new Map<string, ExtractedAction[]>();
    for (const a of actions) {
      const k = a.owner || "Unassigned";
      const arr = map.get(k) ?? [];
      arr.push(a);
      map.set(k, arr);
    }
    return [...map.entries()].sort((a, b) => b[1].length - a[1].length);
  }, [actions]);

  return (
    <div
      className="flex flex-col gap-4 px-7 pt-4 pb-10"
      style={{ background: "var(--ws-sub)", minHeight: "100%" }}
    >
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex-1 min-w-0">
          <h2
            className="m-0 text-[16px] font-semibold"
            style={{ color: "var(--ws-ink)" }}
          >
            Action items
          </h2>
          <p
            className="m-0 mt-1 text-[12.5px] flex items-center gap-1.5 flex-wrap"
            style={{ color: "var(--ws-muted)" }}
          >
            <Sparkles
              className="w-2.5 h-2.5 inline"
              style={{ color: "var(--ws-ai-ink)" }}
            />
            <span>
              Extracted by Cogni from {data ? new Set(actions.map((a) => a.meetingId)).size : 0}{" "}
              meeting{actions.length === 1 ? "" : "s"} · {actions.length} total
            </span>
          </p>
        </div>
        <Segmented<View>
          value={view}
          onChange={setView}
          options={[
            { value: "kanban", label: "By status", icon: <Grid3x3 className="w-3 h-3" /> },
            { value: "byOwner", label: "By owner", icon: <List className="w-3 h-3" /> },
          ]}
        />
        <PillButton>
          <RefreshCw className="w-3 h-3" /> Re-extract
        </PillButton>
      </div>

      {isLoading ? (
        <div
          className="rounded-md p-6 text-[12.5px]"
          style={{
            background: "var(--ws-bg)",
            border: "1px solid var(--ws-border)",
            color: "var(--ws-muted)",
          }}
        >
          Loading action items…
        </div>
      ) : actions.length === 0 ? (
        <div
          className="rounded-md p-8 text-center"
          style={{
            background: "var(--ws-bg)",
            border: "1px solid var(--ws-border)",
          }}
        >
          <Sparkles
            className="w-5 h-5 mx-auto mb-2"
            style={{ color: "var(--ws-ai-ink)" }}
          />
          <p
            className="m-0 text-[13px] font-semibold"
            style={{ color: "var(--ws-ink)" }}
          >
            No action items extracted yet
          </p>
          <p
            className="m-0 mt-1 text-[12px]"
            style={{ color: "var(--ws-muted)" }}
          >
            Once a meeting is transcribed and analyzed, action items appear
            here grouped by status and owner.
          </p>
        </div>
      ) : view === "kanban" ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3.5">
          {STATUS_COLUMNS.map((col) => (
            <KanbanColumn
              key={col.key}
              dealId={dealId}
              label={col.label}
              tone={col.tone}
              items={byStatus[col.key]}
            />
          ))}
        </div>
      ) : (
        <ActionsByOwner dealId={dealId} groups={byOwner} />
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 mt-1">
        <WSCard
          title="Decisions logged"
          action={
            <span className="text-[11px]" style={{ color: "var(--ws-muted)" }}>
              {decisions.length} total
            </span>
          }
        >
          {decisions.length === 0 ? (
            <div className="px-3.5 py-5 text-[12px]" style={{ color: "var(--ws-muted)" }}>
              No decisions extracted yet.
            </div>
          ) : (
            decisions.map((d, i) => (
              <Link
                key={d.id}
                href={`/deals/${dealId}/meetings/${d.meetingId}`}
                className="flex gap-2.5 items-start px-3.5 py-2.5"
                style={{
                  borderTop: i > 0 ? "1px solid var(--ws-border)" : undefined,
                }}
              >
                <CheckCircle2
                  className="w-3 h-3 mt-1 shrink-0"
                  style={{ color: "var(--ws-success)" }}
                />
                <div className="flex-1 min-w-0">
                  <div
                    className="text-[12.5px] font-medium leading-snug"
                    style={{ color: "var(--ws-ink)" }}
                  >
                    {d.text}
                  </div>
                  <div
                    className="text-[10.5px] mt-0.5"
                    style={{ color: "var(--ws-muted)" }}
                  >
                    {d.meetingTitle}
                    {d.timestamp && (
                      <>
                        {" · "}
                        <span className="ws-mono" style={{ color: "var(--ws-faint)" }}>
                          {d.timestamp}
                        </span>
                      </>
                    )}
                  </div>
                </div>
              </Link>
            ))
          )}
        </WSCard>
        <WSCard
          title="Open questions"
          action={
            <span className="text-[11px]" style={{ color: "var(--ws-muted)" }}>
              {questions.filter((q) => !q.answered).length} unresolved
            </span>
          }
        >
          {questions.length === 0 ? (
            <div className="px-3.5 py-5 text-[12px]" style={{ color: "var(--ws-muted)" }}>
              No open questions extracted.
            </div>
          ) : (
            questions.map((q, i) => (
              <div
                key={q.id}
                className="grid grid-cols-[auto_1fr_auto] gap-2.5 items-start px-3.5 py-2.5"
                style={{
                  borderTop: i > 0 ? "1px solid var(--ws-border)" : undefined,
                }}
              >
                <HelpCircle
                  className="w-3 h-3 mt-1 shrink-0"
                  style={{
                    color: q.answered ? "var(--ws-success)" : "var(--ws-warn)",
                  }}
                />
                <Link
                  href={`/deals/${dealId}/meetings/${q.meetingId}`}
                  className="min-w-0"
                >
                  <div
                    className="text-[12.5px] font-medium leading-snug"
                    style={{ color: "var(--ws-ink)" }}
                  >
                    {q.text}
                  </div>
                  <div
                    className="text-[10.5px] mt-0.5"
                    style={{ color: "var(--ws-muted)" }}
                  >
                    Raised in {q.meetingTitle}
                  </div>
                </Link>
                <Link
                  href={`/deals/${dealId}/qa?q=${encodeURIComponent(q.text)}`}
                  className="px-2 py-0.5 rounded-md text-[11px] font-semibold"
                  style={{
                    background: "var(--ws-bg)",
                    border: "1px solid var(--ws-border)",
                    color: "var(--ws-ink2)",
                  }}
                >
                  Ask AI
                </Link>
              </div>
            ))
          )}
        </WSCard>
      </div>
    </div>
  );
}

function KanbanColumn({
  dealId,
  label,
  tone,
  items,
}: {
  dealId: string;
  label: string;
  tone: string;
  items: ExtractedAction[];
}) {
  return (
    <div
      className="ws-card flex flex-col min-h-[200px]"
    >
      <div
        className="ws-card-header"
        style={{ background: "var(--ws-surface)" }}
      >
        <span
          className="w-1.5 h-1.5 rounded-full inline-block"
          style={{ background: tone }}
        />
        <span>{label}</span>
        <span
          className="text-[10.5px] px-1.5 rounded-[9px] font-semibold ws-mono"
          style={{ background: "var(--ws-sub2)", color: "var(--ws-muted)" }}
        >
          {items.length}
        </span>
        <div className="flex-1" />
        <button
          type="button"
          className="grid place-items-center"
          style={{ background: "transparent", color: "var(--ws-faint)" }}
        >
          <Plus className="w-3 h-3" />
        </button>
      </div>
      <div className="p-2 flex flex-col gap-2 flex-1">
        {items.length === 0 && (
          <div className="text-[11.5px] italic" style={{ color: "var(--ws-faint)" }}>
            No items
          </div>
        )}
        {items.map((a) => (
          <ActionCard key={a.id} dealId={dealId} a={a} />
        ))}
      </div>
    </div>
  );
}

function ActionCard({ dealId, a }: { dealId: string; a: ExtractedAction }) {
  const ownerInitials = a.owner ? initialsOf(a.owner) : null;
  return (
    <div
      className="rounded-md p-2.5 flex flex-col gap-1.5"
      style={{
        background: "var(--ws-bg)",
        border: "1px solid var(--ws-border)",
        boxShadow: "0 1px 2px rgba(0,0,0,0.02)",
      }}
    >
      <div className="flex items-start gap-2">
        <input
          type="checkbox"
          className="mt-0.5"
          style={{ accentColor: "var(--ws-accent)" }}
        />
        <span
          className="flex-1 text-[12.5px] font-medium leading-snug"
          style={{ color: "var(--ws-ink)" }}
        >
          {a.text}
        </span>
      </div>
      <Link
        href={`/deals/${dealId}/meetings/${a.meetingId}`}
        className="flex items-center gap-1.5 text-[10.5px] pl-[22px]"
        style={{ color: "var(--ws-muted)" }}
      >
        <Sparkles
          className="w-2.5 h-2.5"
          style={{ color: "var(--ws-ai-ink)" }}
        />
        <span
          className="font-medium truncate"
          style={{ color: "var(--ws-ink2)" }}
        >
          {a.meetingTitle}
        </span>
        {a.timestamp && (
          <span className="ws-mono ml-auto" style={{ color: "var(--ws-faint)" }}>
            {a.timestamp}
          </span>
        )}
      </Link>
      <div className="flex items-center gap-1.5 pl-[22px]">
        {ownerInitials ? (
          <Avatar
            initials={ownerInitials}
            color={avatarColor(a.owner)}
            size={18}
          />
        ) : (
          <span
            className="w-[18px] h-[18px] rounded-full"
            style={{ background: "var(--ws-sub2)" }}
          />
        )}
        <span className="text-[11px]" style={{ color: "var(--ws-ink2)" }}>
          {a.owner || "Unassigned"}
        </span>
        <span className="flex-1" />
        {a.due && (
          <span className="text-[10.5px] ws-mono" style={{ color: "var(--ws-faint)" }}>
            due {a.due}
          </span>
        )}
      </div>
    </div>
  );
}

function ActionsByOwner({
  dealId,
  groups,
}: {
  dealId: string;
  groups: [string, ExtractedAction[]][];
}) {
  return (
    <div
      className="ws-card overflow-hidden"
    >
      {groups.map(([owner, items], i) => (
        <div
          key={owner}
          style={{
            borderTop: i > 0 ? "1px solid var(--ws-border)" : undefined,
          }}
        >
          <div
            className="flex items-center gap-2 px-3.5 py-2.5"
            style={{ background: "var(--ws-surface)" }}
          >
            <Avatar
              initials={initialsOf(owner)}
              color={avatarColor(owner)}
              size={22}
            />
            <span
              className="text-[12.5px] font-semibold"
              style={{ color: "var(--ws-ink)" }}
            >
              {owner}
            </span>
            <span className="flex-1" />
            <span
              className="text-[11px] ws-mono"
              style={{ color: "var(--ws-muted)" }}
            >
              {items.length} action{items.length === 1 ? "" : "s"}
            </span>
          </div>
          {items.map((a) => (
            <Link
              key={a.id}
              href={`/deals/${dealId}/meetings/${a.meetingId}`}
              className="grid grid-cols-[auto_1fr_130px_90px_100px] gap-3 items-center px-3.5 py-2.5 text-[12.5px]"
              style={{ borderTop: "1px solid var(--ws-border)" }}
            >
              <input
                type="checkbox"
                style={{ accentColor: "var(--ws-accent)" }}
                onClick={(e) => e.stopPropagation()}
              />
              <span
                className="font-medium"
                style={{ color: "var(--ws-ink)" }}
              >
                {a.text}
              </span>
              <span
                className="text-[10.5px] inline-flex items-center gap-1"
                style={{ color: "var(--ws-muted)" }}
              >
                <Sparkles
                  className="w-2.5 h-2.5"
                  style={{ color: "var(--ws-ai-ink)" }}
                />
                <span className="truncate">{a.meetingTitle}</span>
              </span>
              <span
                className="px-1.5 py-0.5 rounded text-[10.5px] font-semibold capitalize text-center"
                style={{
                  background:
                    a.status === "open"
                      ? "rgba(161,98,7,0.12)"
                      : a.status === "in_review"
                        ? "var(--ws-ai-tint)"
                        : a.status === "scheduled"
                          ? "var(--ws-accent-soft)"
                          : "rgba(21,128,61,0.12)",
                  color:
                    a.status === "open"
                      ? "var(--ws-warn)"
                      : a.status === "in_review"
                        ? "var(--ws-ai-ink)"
                        : a.status === "scheduled"
                          ? "var(--ws-accent)"
                          : "var(--ws-success)",
                }}
              >
                {a.status.replace("_", " ")}
              </span>
              <span
                className="text-[11px] text-right ws-mono"
                style={{ color: "var(--ws-faint)" }}
              >
                {a.due ? `due ${a.due}` : "—"}
              </span>
            </Link>
          ))}
        </div>
      ))}
    </div>
  );
}
