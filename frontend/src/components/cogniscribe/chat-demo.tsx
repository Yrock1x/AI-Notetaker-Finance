"use client";

import { useEffect, useRef, useState } from "react";
import { Eyebrow, useInView } from "./primitives";
import { useScribeTheme } from "./theme-provider";
import { I } from "./icons";

const USER_TEXT = "Summarise the QoE adjustments and flag any risk.";
const AI_TEXT =
  "Adjusted EBITDA of $28.4M — $2.0M non-recurring legal, $0.5M one-time severance, $1.1M owner comp, normalised rent of $0.3M.";
const CITATIONS = [
  { file: "Project_Lyra_QoE_Report.pdf", page: "p. 14" },
  { file: "FY24_Financials_Final.xlsx", page: "Sheet 3" },
];
const FOLLOWUP =
  "Customer concentration sits at 38% top-5 — worth raising in buyer conversations.";

export function ChatDemo() {
  const { isDark, aiDemosPlaying } = useScribeTheme();
  const [ref, inView] = useInView(0.3);
  const [phase, setPhase] = useState(0);
  const [userTxt, setUserTxt] = useState("");
  const [aiTxt, setAiTxt] = useState("");
  const started = useRef(false);

  useEffect(() => {
    if (!inView || started.current || !aiDemosPlaying) return;
    started.current = true;
    const timeouts: ReturnType<typeof setTimeout>[] = [];
    let userInt: ReturnType<typeof setInterval> | null = null;
    let aiInt: ReturnType<typeof setInterval> | null = null;

    let u = 0;
    userInt = setInterval(() => {
      u++;
      setUserTxt(USER_TEXT.slice(0, u));
      if (u >= USER_TEXT.length) {
        if (userInt) clearInterval(userInt);
        timeouts.push(setTimeout(() => setPhase(1), 300));
        timeouts.push(setTimeout(() => setPhase(2), 900));
        timeouts.push(
          setTimeout(() => {
            setPhase(3);
            let a = 0;
            aiInt = setInterval(() => {
              a++;
              setAiTxt(AI_TEXT.slice(0, a));
              if (a >= AI_TEXT.length) {
                if (aiInt) clearInterval(aiInt);
                timeouts.push(setTimeout(() => setPhase(4), 400));
              }
            }, 18);
          }, 2400)
        );
      }
    }, 35);

    return () => {
      if (userInt) clearInterval(userInt);
      if (aiInt) clearInterval(aiInt);
      timeouts.forEach(clearTimeout);
    };
  }, [inView, aiDemosPlaying]);

  useEffect(() => {
    if (!aiDemosPlaying && started.current) {
      setUserTxt(USER_TEXT);
      setAiTxt(AI_TEXT);
      setPhase(4);
    }
  }, [aiDemosPlaying]);

  const bubbleClass = isDark ? "bg-white/[0.04] border-white/10" : "bg-white border-black/[0.06]";
  const aiBubbleClass = isDark
    ? "bg-emerald-500/[0.06] border-emerald-500/20"
    : "bg-emerald-50/60 border-emerald-200/60";

  return (
    <div ref={ref} className="flex flex-col gap-4">
      <div className="flex items-center justify-between mb-1">
        <Eyebrow>Ask your data room</Eyebrow>
        <div className="flex items-center gap-1.5">
          <I.Sparkles size={11} className="text-emerald-500" />
          <span className={`text-[10px] font-mono ${isDark ? "text-white/40" : "text-black/40"}`}>
            Project Lyra
          </span>
        </div>
      </div>

      <div className={`flex gap-3 transition-opacity duration-500 ${phase >= 0 ? "opacity-100" : "opacity-0"}`}>
        <div
          className={`shrink-0 h-7 w-7 rounded-full flex items-center justify-center text-[10px] font-semibold ${
            isDark ? "bg-white/10 text-white/70" : "bg-black/[0.06] text-black/70"
          }`}
        >
          AS
        </div>
        <div className={`flex-1 rounded-xl border px-4 py-2.5 ${bubbleClass}`}>
          <p className={`text-[13px] ${isDark ? "text-white/85" : "text-black/85"}`}>
            {userTxt}
            {phase === 0 && userTxt.length < USER_TEXT.length && <span className="caret"></span>}
          </p>
        </div>
      </div>

      {phase === 2 && (
        <div className="flex gap-3">
          <div className="shrink-0 h-7 w-7 rounded-full flex items-center justify-center bg-emerald-500/15">
            <I.Sparkles size={12} className="text-emerald-400" />
          </div>
          <div className={`rounded-xl border px-4 py-3 ${aiBubbleClass}`}>
            <div className="flex items-center gap-2">
              <span className={`text-[11px] font-mono ${isDark ? "text-white/50" : "text-black/50"}`}>
                Retrieving
              </span>
              <span className="inline-flex gap-0.5">
                <span
                  className="w-1 h-1 rounded-full bg-emerald-400 animate-bounce"
                  style={{ animationDelay: "0ms" }}
                ></span>
                <span
                  className="w-1 h-1 rounded-full bg-emerald-400 animate-bounce"
                  style={{ animationDelay: "160ms" }}
                ></span>
                <span
                  className="w-1 h-1 rounded-full bg-emerald-400 animate-bounce"
                  style={{ animationDelay: "320ms" }}
                ></span>
              </span>
            </div>
          </div>
        </div>
      )}

      {phase >= 3 && (
        <div className="flex gap-3 fade-up">
          <div className="shrink-0 h-7 w-7 rounded-full flex items-center justify-center bg-emerald-500/15">
            <I.Sparkles size={12} className="text-emerald-400" />
          </div>
          <div className={`flex-1 rounded-xl border px-4 py-3 ${aiBubbleClass}`}>
            <p className={`text-[13px] leading-relaxed ${isDark ? "text-white/90" : "text-black/85"}`}>
              {aiTxt}
              {phase === 3 && aiTxt.length < AI_TEXT.length && <span className="caret"></span>}
            </p>

            {phase >= 4 && (
              <>
                <div className="flex flex-wrap gap-1.5 mt-3">
                  {CITATIONS.map((c, i) => (
                    <span
                      key={i}
                      className={`inline-flex items-center gap-1.5 text-[10px] font-mono rounded-md px-2 py-1 border ${
                        isDark
                          ? "bg-white/[0.04] border-white/10 text-white/70"
                          : "bg-white border-black/10 text-black/60"
                      }`}
                    >
                      <I.File size={10} />
                      <span className="truncate max-w-[160px]">{c.file}</span>
                      <span className={isDark ? "text-white/30" : "text-black/30"}>·</span>
                      <span className={isDark ? "text-white/40" : "text-black/40"}>{c.page}</span>
                    </span>
                  ))}
                </div>
                <p
                  className={`text-[12px] mt-3 pt-3 border-t ${
                    isDark ? "border-white/5 text-white/55" : "border-black/[0.06] text-black/55"
                  } italic`}
                >
                  <span
                    className={`not-italic text-[10px] font-mono uppercase tracking-wider mr-2 ${
                      isDark ? "text-white/35" : "text-black/35"
                    }`}
                  >
                    Flag
                  </span>
                  {FOLLOWUP}
                </p>
              </>
            )}
          </div>
        </div>
      )}

      <div
        className={`mt-2 rounded-xl border flex items-center gap-2 px-3 py-2 ${
          isDark ? "bg-white/[0.03] border-white/10" : "bg-white border-black/[0.08]"
        }`}
      >
        <I.Sparkles size={13} className={isDark ? "text-white/30" : "text-black/30"} />
        <span className={`text-[12px] flex-1 ${isDark ? "text-white/30" : "text-black/30"}`}>
          Ask about financials, contracts, customers…
        </span>
        <span
          className={`text-[10px] font-mono rounded px-1.5 py-0.5 ${
            isDark ? "bg-white/5 text-white/30" : "bg-black/[0.05] text-black/40"
          }`}
        >
          ↵
        </span>
      </div>
    </div>
  );
}
