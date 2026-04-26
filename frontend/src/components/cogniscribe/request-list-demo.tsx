"use client";

import { useEffect, useRef, useState } from "react";
import { Eyebrow, useInView } from "./primitives";
import { useScribeTheme } from "./theme-provider";
import { I } from "./icons";

type Status = "Linked" | "Drafted" | "Pending";
type Item = { req: string; status: Status; file: string; size: string };

const REQUEST_ITEMS: Item[] = [
  {
    req: "3-year audited financial statements",
    status: "Linked",
    file: "FY22-24_Audited_Financials.pdf",
    size: "4.2 MB",
  },
  {
    req: "Customer concentration analysis",
    status: "Linked",
    file: "Top_25_Customers_FY24.xlsx",
    size: "820 KB",
  },
  {
    req: "Material contracts summary",
    status: "Linked",
    file: "Key_Contracts_Schedule.xlsx",
    size: "1.1 MB",
  },
  {
    req: "Employee benefit plans",
    status: "Drafted",
    file: "Extracted from Benefits_Overview.pdf",
    size: "AI-drafted",
  },
  {
    req: "Environmental compliance reports",
    status: "Pending",
    file: "No matching document yet",
    size: "—",
  },
];

export function RequestListDemo() {
  const { isDark, aiDemosPlaying } = useScribeTheme();
  const [ref, inView] = useInView(0.3);
  const [visible, setVisible] = useState(0);
  const [processing, setProcessing] = useState(-1);
  const started = useRef(false);

  useEffect(() => {
    if (!inView || !aiDemosPlaying || started.current) return;
    started.current = true;
    const timeouts: ReturnType<typeof setTimeout>[] = [];
    REQUEST_ITEMS.forEach((_, i) => {
      timeouts.push(setTimeout(() => setProcessing(i), i * 900));
      timeouts.push(
        setTimeout(() => {
          setVisible(i + 1);
          setProcessing(-1);
        }, i * 900 + 550)
      );
    });
    return () => {
      timeouts.forEach(clearTimeout);
    };
  }, [inView, aiDemosPlaying]);

  useEffect(() => {
    if (!aiDemosPlaying && inView) {
      setVisible(REQUEST_ITEMS.length);
      setProcessing(-1);
    }
  }, [aiDemosPlaying, inView]);

  const linked = REQUEST_ITEMS.slice(0, visible).filter((x) => x.status === "Linked").length;
  const drafted = REQUEST_ITEMS.slice(0, visible).filter((x) => x.status === "Drafted").length;
  const pct = Math.round(((linked + drafted * 0.5) / REQUEST_ITEMS.length) * 100);

  return (
    <div ref={ref}>
      <div className="flex items-center justify-between mb-6">
        <Eyebrow>Diligence request list — auto-filled</Eyebrow>
        <span className={`text-[10px] font-mono ${isDark ? "text-white/35" : "text-black/35"}`}>
          {visible}/{REQUEST_ITEMS.length}
        </span>
      </div>

      <div className="flex flex-col gap-2">
        {REQUEST_ITEMS.map((item, i) => {
          const shown = i < visible;
          const proc = i === processing;
          const statusColor =
            item.status === "Linked"
              ? isDark
                ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/25"
                : "bg-emerald-50 text-emerald-700 border-emerald-200/70"
              : item.status === "Drafted"
              ? isDark
                ? "bg-indigo-500/10 text-indigo-300 border-indigo-500/25"
                : "bg-indigo-50 text-indigo-700 border-indigo-200/70"
              : isDark
              ? "bg-white/5 text-white/40 border-white/10"
              : "bg-black/[0.04] text-black/40 border-black/10";

          return (
            <div
              key={item.req}
              className={`group flex items-start gap-3 rounded-lg border p-3 transition-all duration-500 ${
                isDark ? "border-white/[0.07] bg-white/[0.02]" : "border-black/[0.06] bg-[#fafafa]"
              } ${shown ? "opacity-100 translate-y-0" : proc ? "opacity-80 translate-y-0" : "opacity-25 translate-y-0.5"}`}
            >
              <div className="mt-0.5 shrink-0">
                {proc ? (
                  <I.Loader
                    size={15}
                    className={`${isDark ? "text-indigo-300" : "text-indigo-600"} animate-spin`}
                  />
                ) : (
                  <I.CheckCircle
                    size={15}
                    className={
                      !shown
                        ? isDark
                          ? "text-white/15"
                          : "text-black/15"
                        : item.status === "Linked"
                        ? "text-emerald-500"
                        : item.status === "Drafted"
                        ? "text-indigo-500"
                        : isDark
                        ? "text-white/20"
                        : "text-black/20"
                    }
                  />
                )}
              </div>

              <div className="flex-1 min-w-0">
                <p className={`text-[13px] font-medium ${isDark ? "text-white/85" : "text-black/85"} leading-tight`}>
                  {item.req}
                </p>
                <div className="mt-1.5 flex items-center gap-2 flex-wrap">
                  {proc ? (
                    <>
                      <span
                        className={`text-[10px] font-medium rounded-full px-2 py-0.5 border ${
                          isDark
                            ? "bg-indigo-500/10 text-indigo-300 border-indigo-500/25"
                            : "bg-indigo-50 text-indigo-700 border-indigo-200/70"
                        }`}
                      >
                        Scanning
                      </span>
                      <span className="inline-flex gap-0.5">
                        <span
                          className="w-1 h-1 rounded-full bg-indigo-400 animate-bounce"
                          style={{ animationDelay: "0ms" }}
                        ></span>
                        <span
                          className="w-1 h-1 rounded-full bg-indigo-400 animate-bounce"
                          style={{ animationDelay: "150ms" }}
                        ></span>
                        <span
                          className="w-1 h-1 rounded-full bg-indigo-400 animate-bounce"
                          style={{ animationDelay: "300ms" }}
                        ></span>
                      </span>
                    </>
                  ) : shown ? (
                    <>
                      <span
                        className={`text-[10px] font-medium rounded-full px-2 py-0.5 border ${statusColor}`}
                      >
                        {item.status}
                      </span>
                      <span
                        className={`text-[11px] font-mono truncate ${
                          isDark ? "text-white/45" : "text-black/45"
                        }`}
                      >
                        {item.file}
                      </span>
                      <span
                        className={`text-[10px] font-mono ml-auto ${
                          isDark ? "text-white/30" : "text-black/30"
                        }`}
                      >
                        {item.size}
                      </span>
                    </>
                  ) : (
                    <span className={`text-[11px] ${isDark ? "text-white/25" : "text-black/25"}`}>
                      Awaiting scan…
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div
        className={`mt-5 pt-5 border-t ${
          isDark ? "border-white/5" : "border-black/[0.06]"
        } flex items-end justify-between`}
      >
        <div>
          <Eyebrow>Completion</Eyebrow>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="font-display text-5xl tabular-nums">{pct}</span>
            <span className={`font-display text-2xl ${isDark ? "text-white/35" : "text-black/35"}`}>%</span>
          </div>
        </div>
        <div className="flex-1 max-w-[220px] ml-8">
          <div className={`h-[3px] rounded-full overflow-hidden ${isDark ? "bg-white/10" : "bg-black/10"}`}>
            <div
              className="h-full bg-emerald-500 transition-all duration-700 ease-out"
              style={{ width: `${pct}%` }}
            ></div>
          </div>
          <div className="flex items-center justify-between mt-2.5 gap-3 text-[10px] font-mono">
            <span className={isDark ? "text-white/40" : "text-black/40"}>
              <span className="text-emerald-500">●</span> {linked} linked
            </span>
            <span className={isDark ? "text-white/40" : "text-black/40"}>
              <span className="text-indigo-500">●</span> {drafted} drafted
            </span>
            <span className={isDark ? "text-white/30" : "text-black/30"}>
              {REQUEST_ITEMS.length - linked - drafted} open
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
