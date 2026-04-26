"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Eyebrow, useInView } from "./primitives";
import { useScribeTheme } from "./theme-provider";

type Line = {
  speaker: string;
  role: string;
  time: string;
  color: string;
  text: string;
};

const TRANSCRIPT: Line[] = [
  {
    speaker: "M. Huang",
    role: "CEO, Cascade Industrial",
    time: "00:02:15",
    color: "border-l-amber-400",
    text: "Q4 revenue closed at $64.1M, up 23.7% year over year — the enterprise pipeline was the single biggest contributor.",
  },
  {
    speaker: "R. Okafor",
    role: "CFO, Cascade Industrial",
    time: "00:04:32",
    color: "border-l-sky-400",
    text: "Adjusted EBITDA margin expanded to 23.5%, primarily from SaaS operational efficiencies and a 130 bps gross margin lift.",
  },
  {
    speaker: "You",
    role: "Analyst, Ridgewater Capital",
    time: "00:06:18",
    color: "border-l-violet-400",
    text: "Walk us through net retention — where are you on enterprise cohort expansion versus churn?",
  },
  {
    speaker: "R. Okafor",
    role: "CFO, Cascade Industrial",
    time: "00:06:41",
    color: "border-l-sky-400",
    text: "NRR is 118% across enterprise. Logo churn held below 4% — the largest retained account grew 2.1× in the period.",
  },
];

export function LiveTranscriptDemo() {
  const { isDark, aiDemosPlaying } = useScribeTheme();
  const [ref, inView] = useInView(0.25);
  const [lineIdx, setLineIdx] = useState(0);
  const [chars, setChars] = useState(0);
  const [typing, setTyping] = useState(false);
  const started = useRef(false);
  const charInterval = useRef<ReturnType<typeof setInterval> | null>(null);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  const clearAll = useCallback(() => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    if (charInterval.current) {
      clearInterval(charInterval.current);
      charInterval.current = null;
    }
  }, []);

  const typeLine = useCallback((idx: number) => {
    if (idx >= TRANSCRIPT.length) return;
    const text = TRANSCRIPT[idx].text;
    setLineIdx(idx);
    setChars(0);
    setTyping(true);
    let c = 0;
    charInterval.current = setInterval(() => {
      c++;
      setChars(c);
      if (c >= text.length) {
        if (charInterval.current) {
          clearInterval(charInterval.current);
          charInterval.current = null;
        }
        setTyping(false);
        if (idx + 1 < TRANSCRIPT.length) {
          const t = setTimeout(() => typeLine(idx + 1), 700);
          timers.current.push(t);
        } else {
          const t = setTimeout(() => typeLine(0), 4500);
          timers.current.push(t);
        }
      }
    }, 22);
  }, []);

  useEffect(() => {
    if (!inView || started.current || !aiDemosPlaying) return;
    started.current = true;
    typeLine(0);
    return clearAll;
  }, [inView, aiDemosPlaying, typeLine, clearAll]);

  useEffect(() => () => clearAll(), [clearAll]);

  useEffect(() => {
    if (!aiDemosPlaying && started.current) {
      clearAll();
      setLineIdx(TRANSCRIPT.length - 1);
      setChars(TRANSCRIPT[TRANSCRIPT.length - 1].text.length);
      setTyping(false);
    }
  }, [aiDemosPlaying, clearAll]);

  return (
    <div ref={ref}>
      <div className="flex items-center justify-between mb-5">
        <Eyebrow>Live transcript · Management presentation</Eyebrow>
        <span className="inline-flex items-center gap-1.5">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-500 opacity-60"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
          </span>
          <span className="text-[10px] font-mono uppercase tracking-wider text-red-500">Rec</span>
        </span>
      </div>

      <div className="flex flex-col gap-4">
        {TRANSCRIPT.map((line, i) => {
          const shown = i <= lineIdx;
          const current = i === lineIdx && typing;
          const display = current ? line.text.slice(0, chars) : shown ? line.text : "";
          return (
            <div
              key={i}
              className="transition-all duration-500"
              style={{ opacity: shown ? 1 : 0.15, transform: shown ? "translateY(0)" : "translateY(4px)" }}
            >
              <div className={`border-l-2 ${line.color} pl-4`}>
                <div className="flex items-baseline gap-2 mb-1.5 flex-wrap">
                  <span className={`text-[12px] font-semibold ${isDark ? "text-white/90" : "text-black/85"}`}>
                    {line.speaker}
                  </span>
                  <span className={`text-[10px] ${isDark ? "text-white/35" : "text-black/35"}`}>{line.role}</span>
                  <span
                    className={`text-[10px] font-mono ml-auto ${isDark ? "text-white/40" : "text-black/40"}`}
                  >
                    {line.time}
                  </span>
                </div>
                <p className={`text-[13px] leading-relaxed ${isDark ? "text-white/65" : "text-black/70"}`}>
                  {display}
                  {current && <span className="caret"></span>}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
