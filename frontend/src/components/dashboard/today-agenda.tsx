"use client";

import Link from "next/link";
import { ArrowRight, ExternalLink, Mic } from "lucide-react";
import { useScribeTheme } from "@/components/cogniscribe/theme-provider";
import { Eyebrow } from "@/components/cogniscribe/primitives";
import { useTodayMeetings, type TodayMeeting } from "@/hooks/use-today-meetings";
import { Skeleton } from "@/components/ui/skeleton";

function formatTime(iso?: string): string {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });
}

function meetingHref(m: TodayMeeting): string | null {
  if (!m.deal_id) return null;
  return `/deals/${m.deal_id}/meetings/${m.id}`;
}

export function TodayAgenda() {
  const { isDark } = useScribeTheme();
  const { meetings, isLoading } = useTodayMeetings();

  const todayLabel = new Date().toLocaleDateString(undefined, {
    weekday: "long",
    month: "short",
    day: "numeric",
  });

  return (
    <section
      className={`rounded-2xl border p-6 ${
        isDark
          ? "bg-[#121212] border-white/10"
          : "bg-white border-black/[0.06]"
      }`}
    >
      <div className="flex items-end justify-between mb-5">
        <div className="flex flex-col gap-1.5">
          <Eyebrow>Today</Eyebrow>
          <h2 className="text-[20px] sm:text-[22px] tracking-[-0.01em] font-medium">
            {todayLabel}
          </h2>
        </div>
        <Link
          href="/calendar"
          className={`group flex items-center gap-1.5 text-[12.5px] font-medium ${
            isDark ? "text-white/65 hover:text-white" : "text-black/65 hover:text-black"
          }`}
        >
          View calendar
          <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
        </Link>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : meetings.length === 0 ? (
        <p className={`text-sm ${isDark ? "text-white/40" : "text-black/40"}`}>
          Nothing on your schedule today.
        </p>
      ) : (
        <ul className="space-y-1.5">
          {meetings.map((m) => {
            const href = meetingHref(m);
            const Wrapper = href
              ? ({ children }: { children: React.ReactNode }) => (
                  <Link href={href} className="block">
                    {children}
                  </Link>
                )
              : ({ children }: { children: React.ReactNode }) => (
                  <div>{children}</div>
                );
            return (
              <li key={m.id}>
                <Wrapper>
                  <div
                    className={`flex items-center gap-3 rounded-lg px-3 py-2.5 transition-colors ${
                      isDark ? "hover:bg-white/[0.04]" : "hover:bg-black/[0.03]"
                    }`}
                  >
                    <span
                      className={`font-data tabular-nums text-[12px] w-14 shrink-0 ${
                        isDark ? "text-white/45" : "text-black/45"
                      }`}
                    >
                      {formatTime(m.meeting_date)}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{m.title}</p>
                      <p
                        className={`truncate text-[11.5px] ${
                          isDark ? "text-white/45" : "text-black/45"
                        }`}
                      >
                        {m.deal_name || "Unassigned"}
                      </p>
                    </div>
                    {m.isLive && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-red-500/10 px-2 py-0.5 text-[10px] font-semibold text-red-500">
                        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-red-500" />
                        LIVE
                      </span>
                    )}
                    {m.joinUrl && !m.isLive && (
                      <a
                        href={m.joinUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10.5px] font-medium ${
                          isDark
                            ? "bg-white/[0.06] text-white/75 hover:bg-white/[0.1]"
                            : "bg-black/[0.05] text-black/75 hover:bg-black/[0.08]"
                        }`}
                      >
                        Join <ExternalLink className="h-2.5 w-2.5" />
                      </a>
                    )}
                    {m.isLive && href && (
                      <span
                        className={`inline-flex items-center gap-1 text-[10.5px] font-medium ${
                          isDark ? "text-white/55" : "text-black/55"
                        }`}
                      >
                        <Mic className="h-3 w-3" />
                      </span>
                    )}
                  </div>
                </Wrapper>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
