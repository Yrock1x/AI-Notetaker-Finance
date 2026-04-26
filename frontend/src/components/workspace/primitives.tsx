"use client";

// Workspace UI primitives — the small set of atoms used across the deal
// workspace pages (Overview, Meetings, AI Chat, Action Items, Transcripts).
// Mirrors the design's tokens via CSS variables defined in globals.css
// under [data-workspace], so all workspace pages share one warm-gray skin.

import { ReactNode } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";

// Stable color rotation for attendee avatars. Hash the speaker label /
// initials into this palette so the same person always shows the same
// hue across the workspace.
const AVATAR_COLORS = [
  "#0ea5e9",
  "#10b981",
  "#f59e0b",
  "#8b5cf6",
  "#f43f5e",
  "#06b6d4",
  "#84cc16",
  "#ec4899",
];

export function avatarColor(seed: string | undefined | null): string {
  if (!seed) return "#64748b";
  let hash = 0;
  for (let i = 0; i < seed.length; i++) {
    hash = (hash + seed.charCodeAt(i) * (i + 1)) >>> 0;
  }
  return AVATAR_COLORS[hash % AVATAR_COLORS.length];
}

export function initialsOf(name: string | null | undefined, fallback = "??") {
  if (!name) return fallback;
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

interface AvatarProps {
  initials: string;
  color?: string;
  size?: number;
  ring?: boolean;
  title?: string;
}

export function Avatar({
  initials,
  color,
  size = 24,
  ring = false,
  title,
}: AvatarProps) {
  const bg = color || avatarColor(initials);
  return (
    <span
      title={title}
      className="inline-flex items-center justify-center rounded-full font-medium text-white shrink-0"
      style={{
        width: size,
        height: size,
        fontSize: Math.round(size * 0.42),
        background: bg,
        boxShadow: ring ? "0 0 0 2px var(--ws-bg)" : undefined,
      }}
    >
      {initials}
    </span>
  );
}

interface AvatarStackProps {
  people: { initials: string; color?: string; name?: string }[];
  max?: number;
  size?: number;
}

export function AvatarStack({ people, max = 4, size = 22 }: AvatarStackProps) {
  const visible = people.slice(0, max);
  const rest = people.length - visible.length;
  return (
    <span className="inline-flex items-center">
      {visible.map((p, i) => (
        <span
          key={i}
          style={{ marginLeft: i === 0 ? 0 : -Math.round(size * 0.32) }}
        >
          <Avatar initials={p.initials} color={p.color} size={size} ring title={p.name} />
        </span>
      ))}
      {rest > 0 && (
        <span
          className="inline-flex items-center justify-center rounded-full font-semibold shrink-0 ws-mono"
          style={{
            width: size,
            height: size,
            fontSize: Math.round(size * 0.42),
            background: "var(--ws-sub2)",
            color: "var(--ws-muted)",
            marginLeft: -Math.round(size * 0.32),
            boxShadow: "0 0 0 2px var(--ws-bg)",
          }}
        >
          +{rest}
        </span>
      )}
    </span>
  );
}

// Meeting kind chip — tints by call type. Used in meeting rows + cards.
const KIND_PALETTE: Record<string, { bg: string; color: string }> = {
  External: { bg: "var(--ws-ai-tint)", color: "var(--ws-ai-ink)" },
  Internal: { bg: "var(--ws-sub)", color: "var(--ws-muted)" },
  Legal: { bg: "rgba(124,58,237,0.10)", color: "#7c3aed" },
  Expert: { bg: "rgba(8,145,178,0.10)", color: "#0891b2" },
  Diligence: { bg: "rgba(217,119,6,0.10)", color: "#a16207" },
  Customer: { bg: "rgba(15,118,110,0.10)", color: "#0f766e" },
  Other: { bg: "var(--ws-sub)", color: "var(--ws-muted)" },
};

export function KindPill({ kind }: { kind: string }) {
  const tone = KIND_PALETTE[kind] ?? KIND_PALETTE.Other;
  return (
    <span
      className="inline-flex items-center px-1.5 py-px rounded-[3px] text-[10px] font-semibold tracking-wide"
      style={{ background: tone.bg, color: tone.color }}
    >
      {kind}
    </span>
  );
}

// Card primitive: surface with header + body slot. Used everywhere.
interface CardProps {
  title?: ReactNode;
  action?: ReactNode;
  padding?: number | string;
  children?: ReactNode;
  className?: string;
}

export function WSCard({ title, action, padding = 0, children, className }: CardProps) {
  return (
    <div className={cn("ws-card", className)}>
      {(title || action) && (
        <div className="ws-card-header">
          {title && <h3 className="m-0 text-[12.5px] font-semibold">{title}</h3>}
          <div className="flex-1" />
          {action}
        </div>
      )}
      <div style={{ padding }}>{children}</div>
    </div>
  );
}

// Section eyebrow label.
export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cn("ws-eyebrow", className)}>{children}</span>;
}

// Pill button — used for "Refresh", "Export", filter toggles.
export function PillButton({
  children,
  onClick,
  className,
  disabled,
  type = "button",
  variant = "default",
}: {
  children: ReactNode;
  onClick?: () => void;
  className?: string;
  disabled?: boolean;
  type?: "button" | "submit" | "reset";
  variant?: "default" | "primary" | "danger";
}) {
  const styles =
    variant === "primary"
      ? "text-white"
      : variant === "danger"
        ? "text-white"
        : "";
  const inline =
    variant === "primary"
      ? { background: "var(--ws-ink)", border: "none" }
      : variant === "danger"
        ? { background: "var(--ws-danger)", border: "none" }
        : {
            background: "var(--ws-bg)",
            border: "1px solid var(--ws-border)",
            color: "var(--ws-ink2)",
          };
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      style={inline}
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[12px] font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed",
        styles,
        className,
      )}
    >
      {children}
    </button>
  );
}

// Segmented toggle — used for view switches (Table/Timeline, Kanban/By owner).
interface SegmentedProps<T extends string> {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: ReactNode; icon?: ReactNode }[];
  size?: "sm" | "md";
}

export function Segmented<T extends string>({
  value,
  onChange,
  options,
  size = "md",
}: SegmentedProps<T>) {
  const padY = size === "sm" ? "py-1" : "py-1.5";
  return (
    <div
      className="inline-flex gap-0.5 p-0.5 rounded-md"
      style={{
        background: "var(--ws-surface)",
        border: "1px solid var(--ws-border)",
      }}
    >
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            onClick={() => onChange(o.value)}
            className={cn(
              "inline-flex items-center gap-1 rounded-[5px] px-2.5 text-[11.5px] font-semibold transition-colors",
              padY,
            )}
            style={{
              background: active ? "var(--ws-bg)" : "transparent",
              color: active ? "var(--ws-ink)" : "var(--ws-muted)",
              boxShadow: active ? "0 1px 2px rgba(0,0,0,0.04)" : undefined,
            }}
          >
            {o.icon}
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

// Eyebrow stat tile (used in Overview KPI strip).
interface StatTileProps {
  label: string;
  value: ReactNode;
  unit?: string;
  delta?: string;
  trend?: "up" | "down" | "flat";
  sub?: string;
  icon?: ReactNode;
  isLast?: boolean;
}

export function StatTile({
  label,
  value,
  unit,
  delta,
  trend,
  sub,
  icon,
  isLast,
}: StatTileProps) {
  const trendColor =
    trend === "up"
      ? "var(--ws-success)"
      : trend === "down"
        ? "var(--ws-danger)"
        : "var(--ws-muted)";
  const arrow = trend === "up" ? "↑" : trend === "down" ? "↓" : "→";
  return (
    <div
      className="flex flex-col gap-1 px-3.5 py-3"
      style={{
        borderRight: !isLast ? "1px solid var(--ws-border)" : "none",
      }}
    >
      <div
        className="flex items-center gap-1.5 text-[11px] font-medium"
        style={{ color: "var(--ws-muted)" }}
      >
        {icon}
        <span>{label}</span>
      </div>
      <div className="flex items-baseline gap-1">
        <span
          className="ws-mono text-[22px] font-semibold tracking-tight"
          style={{ color: "var(--ws-ink)" }}
        >
          {value}
        </span>
        {unit && (
          <span
            className="text-[13px] font-medium"
            style={{ color: "var(--ws-muted)" }}
          >
            {unit}
          </span>
        )}
        {delta && (
          <span
            className="ml-auto text-[11px] font-semibold ws-mono"
            style={{ color: trendColor }}
          >
            {arrow} {delta}
          </span>
        )}
      </div>
      {sub && (
        <span className="text-[10.5px]" style={{ color: "var(--ws-faint)" }}>
          {sub}
        </span>
      )}
    </div>
  );
}

// Live recording dot — pulsing red.
export function LiveDot({ size = 7 }: { size?: number }) {
  return (
    <span
      className="ws-live-pulse rounded-full inline-block shrink-0"
      style={{
        width: size,
        height: size,
        background: "var(--ws-live)",
      }}
    />
  );
}

// Status pill for action items / meetings (open / in_review / scheduled / done).
export function StatusPill({ status }: { status: string }) {
  const map: Record<string, { color: string; bg: string; label: string }> = {
    open: { color: "var(--ws-warn)", bg: "rgba(161,98,7,0.12)", label: "Open" },
    in_review: { color: "var(--ws-ai-ink)", bg: "var(--ws-ai-tint)", label: "In review" },
    scheduled: { color: "var(--ws-accent)", bg: "var(--ws-accent-soft)", label: "Scheduled" },
    done: { color: "var(--ws-success)", bg: "rgba(21,128,61,0.12)", label: "Done" },
    completed: { color: "var(--ws-success)", bg: "rgba(21,128,61,0.12)", label: "Completed" },
    cancelled: { color: "var(--ws-faint)", bg: "var(--ws-sub2)", label: "Cancelled" },
  };
  const tone = map[status] ?? { color: "var(--ws-muted)", bg: "var(--ws-sub2)", label: status };
  return (
    <span
      className="inline-flex items-center px-1.5 py-px rounded-[3px] text-[10px] font-semibold capitalize"
      style={{ background: tone.bg, color: tone.color }}
    >
      {tone.label}
    </span>
  );
}

// Link arrow used in Card actions.
export function CardActionLink({
  href,
  children,
  onClick,
}: {
  href?: string;
  onClick?: () => void;
  children: ReactNode;
}) {
  const content = (
    <span
      className="inline-flex items-center gap-1 text-[11.5px] font-medium cursor-pointer"
      style={{ color: "var(--ws-muted)" }}
      onClick={onClick}
    >
      {children}
    </span>
  );
  return href ? <Link href={href}>{content}</Link> : content;
}
