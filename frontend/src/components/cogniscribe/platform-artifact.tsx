"use client";

import { useEffect, useState } from "react";
import { Eyebrow } from "./primitives";
import { useScribeTheme } from "./theme-provider";
import { I } from "./icons";
import { PRODUCTS } from "./products";

function PanelVDR({ active }: { active: boolean }) {
  const { isDark } = useScribeTheme();
  const items = [
    { label: "3.1 · Historical financial statements", status: "Complete", c: "text-emerald-400" },
    { label: "3.2 · Revenue breakdown by segment", status: "Complete", c: "text-emerald-400" },
    { label: "3.3 · EBITDA bridge & adjustments", status: "AI filling", c: "text-indigo-400" },
    {
      label: "3.4 · Working capital analysis",
      status: "Queued",
      c: isDark ? "text-white/35" : "text-black/35",
    },
  ];
  return (
    <div
      className={`absolute inset-0 p-5 transition-all duration-500 ${
        active ? "opacity-100 translate-x-0" : "opacity-0 translate-x-6 pointer-events-none"
      }`}
    >
      <Eyebrow className="mb-3">Project Lyra · Request list</Eyebrow>
      <div className="flex flex-col gap-1.5 mb-3">
        {items.map((it, i) => (
          <div
            key={i}
            className={`flex items-center justify-between py-2 px-3 rounded-lg text-[11px] ${
              isDark ? "bg-white/[0.03] border border-white/5" : "bg-[#fafafa] border border-black/[0.05]"
            }`}
          >
            <span className={isDark ? "text-white/70" : "text-black/70"}>{it.label}</span>
            <span className={`text-[10px] font-mono ${it.c}`}>{it.status}</span>
          </div>
        ))}
      </div>
      <div
        className={`rounded-lg p-3 border ${
          isDark ? "bg-emerald-500/5 border-emerald-500/20" : "bg-emerald-50 border-emerald-200/70"
        }`}
      >
        <div className="flex items-center gap-1.5 mb-1.5">
          <I.Sparkles size={11} className="text-emerald-500" />
          <span
            className={`text-[10px] font-medium tracking-wider uppercase ${
              isDark ? "text-emerald-300" : "text-emerald-700"
            }`}
          >
            Ask the vault
          </span>
        </div>
        <p className={`text-[11px] italic ${isDark ? "text-white/45" : "text-black/55"}`}>
          &ldquo;What are the QoE adjustments?&rdquo;
        </p>
        <p className={`text-[11px] mt-1 ${isDark ? "text-white/80" : "text-black/80"}`}>
          Adj. EBITDA of $28.4M after $2M non-recurring legal, $500K severance, $1.1M owner comp…
        </p>
      </div>
    </div>
  );
}

function PanelMic({ active }: { active: boolean }) {
  const { isDark } = useScribeTheme();
  const lines = [
    { s: "M. Huang", t: "Q4 revenue closed at $64.1M, up 23.7% year over year.", time: "02:15", c: "border-l-amber-400" },
    { s: "R. Okafor", t: "Adjusted EBITDA margin expanded to 23.5%.", time: "04:32", c: "border-l-sky-400" },
    { s: "You", t: "Walk us through net retention.", time: "06:18", c: "border-l-violet-400" },
  ];
  return (
    <div
      className={`absolute inset-0 p-5 transition-all duration-500 ${
        active ? "opacity-100 translate-x-0" : "opacity-0 translate-x-6 pointer-events-none"
      }`}
    >
      <div className="flex items-center justify-between mb-3">
        <Eyebrow>Cascade Industrial · Mgmt call</Eyebrow>
        <span className="text-[10px] font-mono text-red-500 inline-flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-red-500 breathe"></span>
          28:14
        </span>
      </div>
      <div className="flex flex-col gap-1.5 mb-3">
        {lines.map((l, i) => (
          <div
            key={i}
            className={`py-1.5 px-3 rounded-lg border-l-2 ${l.c} ${
              isDark ? "bg-white/[0.03]" : "bg-[#fafafa]"
            }`}
          >
            <div className="flex items-center justify-between mb-0.5">
              <span className={`text-[10px] font-semibold ${isDark ? "text-white/80" : "text-black/80"}`}>{l.s}</span>
              <span className={`text-[9px] font-mono ${isDark ? "text-white/35" : "text-black/35"}`}>{l.time}</span>
            </div>
            <p className={`text-[11px] ${isDark ? "text-white/60" : "text-black/65"}`}>{l.t}</p>
          </div>
        ))}
      </div>
      <div
        className={`rounded-lg p-3 border ${
          isDark ? "bg-amber-500/5 border-amber-500/20" : "bg-amber-50 border-amber-200/70"
        }`}
      >
        <div className="flex items-center gap-1.5 mb-2">
          <I.Brain size={11} className={isDark ? "text-amber-300" : "text-amber-700"} />
          <span
            className={`text-[10px] font-medium tracking-wider uppercase ${
              isDark ? "text-amber-300" : "text-amber-700"
            }`}
          >
            AI analysis
          </span>
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <p className={`text-[9px] font-mono ${isDark ? "text-white/40" : "text-black/40"}`}>Sentiment</p>
            <p className="text-[12px] font-semibold text-emerald-500">Positive</p>
          </div>
          <div>
            <p className={`text-[9px] font-mono ${isDark ? "text-white/40" : "text-black/40"}`}>Topics</p>
            <p className={`text-[12px] font-semibold ${isDark ? "text-white/90" : "text-black/90"}`}>7</p>
          </div>
          <div>
            <p className={`text-[9px] font-mono ${isDark ? "text-white/40" : "text-black/40"}`}>Action items</p>
            <p className={`text-[12px] font-semibold ${isDark ? "text-white/90" : "text-black/90"}`}>3</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export function PlatformArtifact() {
  const { isDark, aiDemosPlaying } = useScribeTheme();
  const [active, setActive] = useState(0);
  const products = Object.values(PRODUCTS);

  useEffect(() => {
    if (!aiDemosPlaying) return;
    const t = setInterval(() => setActive((i) => (i + 1) % products.length), 4200);
    return () => clearInterval(t);
  }, [aiDemosPlaying, products.length]);

  const current = products[active];
  const tone = isDark ? "dark" : "light";
  const ringMap: Record<string, string> = {
    vdr: "rgba(16,185,129,0.35)",
    mic: "rgba(245,158,11,0.35)",
  };

  return (
    <div className="relative">
      <div
        className="absolute -inset-10 rounded-[3rem] blur-3xl transition-all duration-1000 opacity-50"
        style={{ background: `radial-gradient(ellipse at 30% 30%, ${ringMap[current.key]}, transparent 65%)` }}
      ></div>

      <div
        className={`relative rounded-2xl border overflow-hidden shadow-2xl ${
          isDark ? "border-white/10 bg-[#0e0e0e]" : "border-black/[0.08] bg-white"
        }`}
      >
        <div
          className={`flex items-center gap-1 px-3 py-2.5 border-b ${
            isDark ? "border-white/5 bg-[#0a0a0a]" : "border-black/[0.05] bg-[#fafafa]"
          }`}
        >
          {products.map((p, i) => {
            const Pi = p.icon;
            const activeT = i === active;
            return (
              <button
                key={p.key}
                onClick={() => setActive(i)}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[11px] font-medium border transition-colors ${
                  activeT
                    ? `${p.bg[tone]} ${p.text[tone]} ${p.border[tone]}`
                    : isDark
                    ? "border-transparent text-white/35 hover:text-white/60"
                    : "border-transparent text-black/40 hover:text-black/70"
                }`}
              >
                <Pi size={12} />
                {p.name}
              </button>
            );
          })}
          <div className="flex-1"></div>
          <div
            className={`hidden sm:flex items-center gap-1.5 text-[10px] font-mono ${
              isDark ? "text-white/35" : "text-black/35"
            }`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 breathe"></span>
            app.cognisuite.ai
          </div>
        </div>

        <div className="relative h-[360px] overflow-hidden">
          <PanelVDR active={active === 0} />
          <PanelMic active={active === 1} />
        </div>

        <div
          className={`flex items-center justify-center gap-2 py-3 border-t ${
            isDark ? "border-white/5" : "border-black/[0.05]"
          }`}
        >
          {products.map((p, i) => (
            <button
              key={p.key}
              onClick={() => setActive(i)}
              aria-label={`Show ${p.name}`}
              className={`h-1.5 rounded-full transition-all duration-500 ${
                i === active ? `w-7 ${p.dotCls}` : `w-1.5 ${isDark ? "bg-white/20" : "bg-black/15"}`
              }`}
            ></button>
          ))}
        </div>
      </div>
    </div>
  );
}
