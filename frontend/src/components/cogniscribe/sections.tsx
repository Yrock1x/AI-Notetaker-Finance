"use client";

import Link from "next/link";
import { useState } from "react";
import { CountUp, Eyebrow, FadeUp } from "./primitives";
import { useScribeTheme } from "./theme-provider";
import { I } from "./icons";
import { LiveTranscriptDemo } from "./live-transcript-demo";
import { MIC_ACCENT, PRODUCTS } from "./products";

const accentRgb = (alpha: number) => `rgba(${MIC_ACCENT}, ${alpha})`;
const accentSolid = `rgb(${MIC_ACCENT})`;

export function ScribeHero() {
  const { isDark } = useScribeTheme();
  const metrics = [
    { label: "Revenue", end: 64.1, prefix: "$", suffix: "M", dec: 1 },
    { label: "EBITDA margin", end: 23.5, suffix: "%", dec: 1 },
    { label: "Net retention", end: 118, suffix: "%", dec: 0 },
  ];
  return (
    <section
      id="top"
      className={`relative overflow-hidden ${
        isDark ? "bg-[#0a0a0a] text-white" : "bg-[#fafafa] text-[#0a0a0a]"
      }`}
    >
      <div
        className="absolute inset-0 pointer-events-none drift"
        style={{
          background: `radial-gradient(ellipse 70% 50% at 80% 0%, ${accentRgb(isDark ? 0.18 : 0.1)}, transparent 60%)`,
        }}
      ></div>
      <div className={`absolute inset-0 noise ${isDark ? "opacity-[0.04]" : "opacity-[0.03]"} pointer-events-none`}></div>

      <div className="relative max-w-7xl mx-auto px-6 pt-36 pb-24 grid lg:grid-cols-12 gap-12 items-center">
        <div className="lg:col-span-6 order-2 lg:order-1">
          <div
            className={`rounded-2xl border p-6 md:p-7 shadow-2xl ${
              isDark ? "border-white/10 bg-[#121212]" : "border-black/[0.06] bg-white"
            }`}
            style={{
              boxShadow: isDark
                ? `0 40px 80px -30px ${accentRgb(0.3)}`
                : `0 40px 80px -40px ${accentRgb(0.5)}`,
            }}
          >
            <LiveTranscriptDemo />
            <div className={`mt-6 pt-5 border-t ${isDark ? "border-white/5" : "border-black/[0.06]"}`}>
              <Eyebrow className="mb-3">Extracted from this call</Eyebrow>
              <div className="grid grid-cols-3 gap-2">
                {metrics.map((m) => (
                  <div
                    key={m.label}
                    className={`rounded-lg border p-3 ${
                      isDark ? "bg-white/[0.03] border-white/5" : "bg-[#fafafa] border-black/[0.05]"
                    }`}
                  >
                    <p
                      className={`text-[10px] font-mono uppercase tracking-wider ${
                        isDark ? "text-white/35" : "text-black/35"
                      } mb-1`}
                    >
                      {m.label}
                    </p>
                    <p className="font-display text-2xl tabular-nums">
                      <CountUp end={m.end} prefix={m.prefix} suffix={m.suffix} decimals={m.dec} />
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="lg:col-span-6 order-1 lg:order-2">
          <div
            className="fade-up inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[11px] mb-8 backdrop-blur-sm"
            style={{
              borderColor: accentRgb(0.35),
              background: accentRgb(isDark ? 0.1 : 0.08),
              color: isDark ? "rgba(255,255,255,0.85)" : "rgba(0,0,0,0.75)",
            }}
          >
            <I.Mic size={11} />
            <span className="font-mono tracking-wider uppercase">CogniScribe · Meeting intelligence</span>
          </div>

          <h1 className="fade-up d-100 text-[52px] sm:text-[64px] lg:text-[76px] leading-[0.95] tracking-[-0.035em] font-medium mb-8">
            Every meeting.
            <br />
            <span
              className="font-display italic font-normal"
              style={{ color: isDark ? "rgba(255,255,255,0.55)" : "rgba(0,0,0,0.45)" }}
            >
              Perfect recall.
            </span>
          </h1>

          <p
            className={`fade-up d-200 text-[17px] leading-relaxed max-w-lg mb-10 ${
              isDark ? "text-white/55" : "text-black/55"
            }`}
          >
            A silent AI partner joins every call — Zoom, Meet, Teams, phone bridge. It diarizes speakers, extracts
            metrics, flags risks, and stitches the whole conversation into a searchable, cited library your team can
            question for years.
          </p>

          <div className="fade-up d-300 flex flex-col sm:flex-row items-start gap-3 mb-10">
            <a
              href="#get-started"
              className="inline-flex items-center justify-center gap-2 h-11 px-6 rounded-full text-[13px] font-medium whitespace-nowrap"
              style={{ background: accentSolid, color: "#3a1e00" }}
            >
              Start a trial <I.Arrow size={14} />
            </a>
            <a
              href="#library"
              className={`inline-flex items-center justify-center gap-2 h-11 px-6 rounded-full text-[13px] font-medium border ${
                isDark
                  ? "border-white/15 text-white/80 hover:bg-white/5"
                  : "border-black/15 text-black/75 hover:bg-black/[0.04]"
              }`}
            >
              See the library
            </a>
          </div>

          <div className="fade-up d-400 grid grid-cols-3 gap-4 max-w-md">
            {[
              { k: "100%", v: "meetings captured" },
              { k: "<30s", v: "summary latency" },
              { k: "42+", v: "languages supported" },
            ].map((s) => (
              <div key={s.v}>
                <p className="font-display text-[28px] tracking-tight tabular-nums">{s.k}</p>
                <p
                  className={`text-[10px] font-mono tracking-wider uppercase mt-1 ${
                    isDark ? "text-white/40" : "text-black/40"
                  }`}
                >
                  {s.v}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div
        className={`absolute bottom-0 left-0 right-0 h-16 pointer-events-none ${
          isDark ? "bg-gradient-to-t from-[#0a0a0a] to-transparent" : "bg-gradient-to-t from-[#fafafa] to-transparent"
        }`}
      ></div>
    </section>
  );
}

export function ScribePipeline() {
  const { isDark } = useScribeTheme();
  const stages = [
    {
      n: "01",
      t: "Join",
      d: "Calendar-connected bot joins every relevant call automatically — or on-demand.",
      Ic: I.Calendar,
    },
    {
      n: "02",
      t: "Diarize",
      d: "Real-time speaker labels, overlap handling, and attribution through breakout rooms.",
      Ic: I.Users,
    },
    {
      n: "03",
      t: "Extract",
      d: "Structured facts lifted from speech: metrics, risks, commitments, decisions, owners.",
      Ic: I.Brain,
    },
    {
      n: "04",
      t: "Connect",
      d: "Transcript and entities piped into CogniVault so docs and dialogue share one index.",
      Ic: I.Git,
    },
  ];
  return (
    <section id="how" className={`${isDark ? "bg-[#0e0e0e] text-white" : "bg-white text-black"} py-28 px-6`}>
      <div className="max-w-6xl mx-auto">
        <FadeUp className="mb-14 max-w-2xl">
          <Eyebrow className="mb-4">The pipeline</Eyebrow>
          <h2 className="text-[38px] sm:text-[54px] leading-[1.02] tracking-[-0.02em] font-medium">
            From microphone
            <br />
            <span
              className="font-display italic font-normal"
              style={{ color: isDark ? "rgba(255,255,255,0.45)" : "rgba(0,0,0,0.35)" }}
            >
              to memory, in seconds.
            </span>
          </h2>
        </FadeUp>

        <div className="grid md:grid-cols-4 gap-4">
          {stages.map((s, i) => {
            const Ic = s.Ic;
            return (
              <FadeUp key={s.n} delay={i * 80}>
                <div
                  className={`relative rounded-2xl border p-6 h-full ${
                    isDark ? "bg-[#121212] border-white/10" : "bg-[#fafafa] border-black/[0.06]"
                  }`}
                >
                  {i < stages.length - 1 && (
                    <div
                      className={`hidden md:flex absolute top-1/2 -right-3 w-6 h-6 rounded-full items-center justify-center z-10 ${
                        isDark ? "bg-[#0e0e0e] border border-white/10" : "bg-white border border-black/[0.06]"
                      }`}
                    >
                      <I.Arrow size={11} className={isDark ? "text-white/40" : "text-black/40"} />
                    </div>
                  )}
                  <div className="flex items-center justify-between mb-6">
                    <span
                      className="font-display text-4xl tabular-nums"
                      style={{ color: accentSolid }}
                    >
                      {s.n}
                    </span>
                    <div
                      className={`w-9 h-9 rounded-lg flex items-center justify-center ${
                        isDark ? "bg-white/5" : "bg-black/[0.04]"
                      }`}
                    >
                      <Ic size={15} className={isDark ? "text-white/75" : "text-black/75"} />
                    </div>
                  </div>
                  <p className={`text-[18px] font-medium mb-2 ${isDark ? "text-white/90" : "text-black/90"}`}>{s.t}</p>
                  <p className={`text-[12px] leading-relaxed ${isDark ? "text-white/55" : "text-black/60"}`}>{s.d}</p>
                </div>
              </FadeUp>
            );
          })}
        </div>
      </div>
    </section>
  );
}

type ExtractionTab = {
  k: "metrics" | "risks" | "actions";
  name: string;
  Ic: typeof I.TrendUp;
  copy: string;
  items: { l: string; v: string; src: string }[];
};

export function ScribeExtraction() {
  const { isDark } = useScribeTheme();
  const tabs: ExtractionTab[] = [
    {
      k: "metrics",
      name: "Metrics",
      Ic: I.TrendUp,
      copy: "Revenue, margin, CAC, NRR, churn — every number said on the call, with the speaker, the timestamp, and the surrounding context.",
      items: [
        { l: "Revenue (LTM)", v: "$64.1M", src: "Mgmt pres · 00:14:02 · CEO" },
        { l: "Adj. EBITDA margin", v: "23.5%", src: "Mgmt pres · 00:31:40 · CFO" },
        { l: "Net retention", v: "118%", src: "Q&A · 00:52:08 · CFO" },
        { l: "Gross margin", v: "74.2%", src: "Mgmt pres · 00:18:55 · CFO" },
      ],
    },
    {
      k: "risks",
      name: "Risks",
      Ic: I.Shield,
      copy: "Issues raised during the call — flagged by sentiment, keyword, and pattern recognition. Mapped to source quotes and linked to related documents.",
      items: [
        { l: "Customer concentration", v: "High", src: "Top-1 customer = 24% of revenue" },
        { l: "Key-person dependency", v: "Medium", src: "CTO holds all ML IP knowledge" },
        { l: "FX exposure", v: "Low", src: "<5% of revenue non-USD" },
        { l: "Pending litigation", v: "None", src: "Legal confirmed clean docket" },
      ],
    },
    {
      k: "actions",
      name: "Actions",
      Ic: I.Check,
      copy: "Commitments and follow-ups lifted in real time — with an owner, a due date, and a one-click deep-link back to the moment they were agreed.",
      items: [
        { l: "Send Top-25 customers file", v: "CFO", src: "by Apr 16" },
        { l: "Confirm IP assignment review", v: "Counsel", src: "by Apr 18" },
        { l: "Draft disclosure schedule", v: "Associate", src: "by Apr 20" },
        { l: "Schedule working-capital call", v: "VP Finance", src: "TBD" },
      ],
    },
  ];
  const [active, setActive] = useState<ExtractionTab["k"]>("metrics");
  const t = tabs.find((x) => x.k === active)!;
  const Ti = t.Ic;

  return (
    <section className={`${isDark ? "bg-[#0e0e0e] text-white" : "bg-white text-black"} py-28 px-6`}>
      <div className="max-w-6xl mx-auto grid md:grid-cols-2 gap-16 items-center">
        <FadeUp>
          <Eyebrow className="mb-4">Structured output</Eyebrow>
          <h3 className="text-[38px] sm:text-[48px] leading-[1.02] tracking-[-0.02em] font-medium mb-6">
            Not a transcript.
            <br />
            <span
              className="font-display italic font-normal"
              style={{ color: isDark ? "rgba(255,255,255,0.4)" : "rgba(0,0,0,0.35)" }}
            >
              A dataset.
            </span>
          </h3>
          <p className={`text-[15px] leading-relaxed mb-8 ${isDark ? "text-white/55" : "text-black/60"}`}>
            Transcripts are the raw material. CogniScribe turns them into structured data you can sort, filter, export
            to Excel, pipe into a model — or query as part of a broader CogniVault chat.
          </p>

          <div
            className={`inline-flex flex-wrap gap-1 rounded-full p-1 border mb-6 ${
              isDark ? "bg-white/[0.03] border-white/10" : "bg-[#fafafa] border-black/[0.06]"
            }`}
          >
            {tabs.map((tab) => {
              const Xi = tab.Ic;
              const on = active === tab.k;
              return (
                <button
                  key={tab.k}
                  onClick={() => setActive(tab.k)}
                  className={`inline-flex items-center gap-1.5 text-[12px] font-medium px-3 py-1.5 rounded-full transition-colors ${
                    on
                      ? isDark
                        ? "bg-white text-[#0a0a0a]"
                        : "bg-[#0a0a0a] text-white"
                      : isDark
                      ? "text-white/55 hover:text-white/80"
                      : "text-black/55 hover:text-black/80"
                  }`}
                >
                  <Xi size={12} /> {tab.name}
                </button>
              );
            })}
          </div>
          <p className={`text-[13px] leading-relaxed ${isDark ? "text-white/45" : "text-black/50"}`}>{t.copy}</p>
        </FadeUp>

        <FadeUp key={active} delay={60}>
          <div
            className={`rounded-2xl border overflow-hidden ${
              isDark ? "bg-[#121212] border-white/10" : "bg-[#fafafa] border-black/[0.06]"
            }`}
          >
            <div
              className={`px-6 py-4 border-b flex items-center gap-3 ${
                isDark ? "border-white/5 bg-white/[0.02]" : "border-black/[0.05] bg-white"
              }`}
            >
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center"
                style={{
                  background: accentRgb(isDark ? 0.18 : 0.12),
                  color: accentSolid,
                }}
              >
                <Ti size={14} />
              </div>
              <div className="flex-1">
                <p className={`text-[13px] font-medium ${isDark ? "text-white/90" : "text-black/90"}`}>{t.name}</p>
                <p
                  className={`text-[10px] font-mono uppercase tracking-wider ${
                    isDark ? "text-white/35" : "text-black/35"
                  }`}
                >
                  From Project Lyra · Mgmt presentation · Apr 14
                </p>
              </div>
            </div>
            <div className="p-4">
              <div className="flex flex-col gap-1.5">
                {t.items.map((it, i) => (
                  <div
                    key={i}
                    className={`flex items-center justify-between gap-3 p-3 rounded-lg ${
                      isDark ? "hover:bg-white/[0.02]" : "hover:bg-black/[0.02]"
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <p
                        className={`text-[13px] font-medium truncate ${
                          isDark ? "text-white/85" : "text-black/85"
                        }`}
                      >
                        {it.l}
                      </p>
                      <p
                        className={`text-[11px] font-mono mt-0.5 truncate ${
                          isDark ? "text-white/40" : "text-black/45"
                        }`}
                      >
                        {it.src}
                      </p>
                    </div>
                    <span
                      className="text-[13px] font-medium tabular-nums shrink-0"
                      style={{ color: accentSolid }}
                    >
                      {it.v}
                    </span>
                  </div>
                ))}
              </div>
            </div>
            <div
              className={`px-4 py-3 border-t flex items-center justify-between ${
                isDark ? "border-white/5 bg-white/[0.02]" : "border-black/[0.05] bg-white"
              }`}
            >
              <span
                className={`text-[10px] font-mono tracking-wider uppercase ${
                  isDark ? "text-white/35" : "text-black/35"
                }`}
              >
                Confidence · 0.94 avg
              </span>
              <span className={`text-[11px] font-mono ${isDark ? "text-white/50" : "text-black/50"}`}>
                ↓ Export · CSV
              </span>
            </div>
          </div>
        </FadeUp>
      </div>
    </section>
  );
}

type Meeting = {
  deal: string;
  kind: string;
  dur: string;
  date: string;
  people: number;
  tag: string;
  topics: string[];
};

const MEETINGS: Meeting[] = [
  {
    deal: "Project Lyra",
    kind: "Mgmt presentation",
    dur: "01:12:40",
    date: "Apr 14",
    people: 6,
    tag: "bg-amber-500",
    topics: ["EBITDA", "Customer concentration", "Churn", "Growth plan"],
  },
  {
    deal: "Project Meridian",
    kind: "Legal diligence",
    dur: "00:48:12",
    date: "Apr 12",
    people: 4,
    tag: "bg-emerald-500",
    topics: ["Reps & warranties", "Change of control", "IP ownership"],
  },
  {
    deal: "Project Aster",
    kind: "Buyer intro call",
    dur: "00:32:05",
    date: "Apr 11",
    people: 5,
    tag: "bg-sky-500",
    topics: ["Fit", "Process timeline", "Exclusivity"],
  },
  {
    deal: "Project Onyx",
    kind: "Negotiation",
    dur: "01:05:22",
    date: "Apr 09",
    people: 3,
    tag: "bg-violet-500",
    topics: ["Purchase price", "Earn-out", "Escrow"],
  },
  {
    deal: "Accenture · Q1",
    kind: "Client review",
    dur: "00:56:10",
    date: "Apr 08",
    people: 7,
    tag: "bg-rose-500",
    topics: ["Delivery", "Scope change", "Staffing"],
  },
  {
    deal: "Project Vesta",
    kind: "Partner roundtable",
    dur: "00:38:00",
    date: "Apr 05",
    people: 4,
    tag: "bg-lime-500",
    topics: ["Valuation", "Comps", "Timing"],
  },
];

export function ScribeLibrary() {
  const { isDark, aiDemosPlaying } = useScribeTheme();
  const kinds = [
    "All",
    "Mgmt presentation",
    "Legal diligence",
    "Buyer intro call",
    "Negotiation",
    "Client review",
    "Partner roundtable",
  ];
  const [filter, setFilter] = useState("All");
  const [q, setQ] = useState("");
  const filtered = MEETINGS.filter((m) => {
    if (filter !== "All" && m.kind !== filter) return false;
    if (q && !(m.deal + " " + m.topics.join(" ")).toLowerCase().includes(q.toLowerCase())) return false;
    return true;
  });

  return (
    <section
      id="library"
      className={`${isDark ? "bg-[#0a0a0a] text-white" : "bg-[#fafafa] text-black"} py-28 px-6`}
    >
      <div className="max-w-6xl mx-auto">
        <FadeUp className="mb-10 flex flex-col md:flex-row md:items-end md:justify-between gap-6">
          <div>
            <Eyebrow className="mb-3">Meeting library</Eyebrow>
            <h3 className="text-[36px] sm:text-[44px] leading-[1.05] tracking-[-0.02em] font-medium">
              Every call, searchable.
              <br />
              <span
                className="font-display italic font-normal"
                style={{ color: isDark ? "rgba(255,255,255,0.4)" : "rgba(0,0,0,0.35)" }}
              >
                By topic, speaker, metric.
              </span>
            </h3>
          </div>
          <div
            className={`flex items-center gap-2 rounded-full border px-4 py-2 w-full md:w-80 ${
              isDark ? "bg-white/[0.03] border-white/10" : "bg-white border-black/[0.06]"
            }`}
          >
            <I.Search size={13} className={isDark ? "text-white/40" : "text-black/40"} />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search meetings, topics, speakers..."
              className={`bg-transparent outline-none text-[13px] flex-1 ${
                isDark ? "text-white placeholder-white/30" : "text-black placeholder-black/30"
              }`}
            />
          </div>
        </FadeUp>

        <FadeUp delay={60} className="mb-6 -mx-6 px-6 overflow-x-auto no-scrollbar">
          <div
            className={`inline-flex gap-1.5 rounded-full p-1 border whitespace-nowrap ${
              isDark ? "bg-white/[0.03] border-white/10" : "bg-white border-black/[0.06]"
            }`}
          >
            {kinds.map((k) => (
              <button
                key={k}
                onClick={() => setFilter(k)}
                className={`text-[11px] font-medium px-3 py-1.5 rounded-full transition-colors ${
                  filter === k
                    ? isDark
                      ? "bg-white text-[#0a0a0a]"
                      : "bg-[#0a0a0a] text-white"
                    : isDark
                    ? "text-white/55 hover:text-white/80"
                    : "text-black/55 hover:text-black/80"
                }`}
              >
                {k}
              </button>
            ))}
          </div>
        </FadeUp>

        <div className="grid md:grid-cols-2 gap-4">
          {filtered.map((m, i) => (
            <FadeUp key={m.deal + i} delay={i * 60}>
              <div
                className={`group rounded-2xl border p-5 transition-all hover:-translate-y-0.5 cursor-pointer ${
                  isDark
                    ? "border-white/10 bg-[#121212] hover:border-white/20"
                    : "border-black/[0.06] bg-white hover:border-black/15"
                } shadow-sm hover:shadow-lg`}
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-2.5">
                    <div className={`w-1.5 h-12 rounded-full ${m.tag}`}></div>
                    <div>
                      <p
                        className={`text-[11px] font-mono uppercase tracking-wider ${
                          isDark ? "text-white/40" : "text-black/40"
                        }`}
                      >
                        {m.kind}
                      </p>
                      <p
                        className={`text-[16px] font-medium mt-0.5 ${
                          isDark ? "text-white/90" : "text-black/90"
                        }`}
                      >
                        {m.deal}
                      </p>
                    </div>
                  </div>
                  <div
                    className={`text-right text-[11px] font-mono ${
                      isDark ? "text-white/40" : "text-black/40"
                    }`}
                  >
                    <p>{m.dur}</p>
                    <p className="mt-0.5">{m.date}</p>
                  </div>
                </div>

                <div className="flex items-end gap-[2px] h-9 mb-4">
                  {Array.from({ length: 48 }).map((_, j) => {
                    const seed = (Math.sin(i * 7 + j * 1.3) + 1) / 2;
                    const h = 20 + seed * 80;
                    return (
                      <div
                        key={j}
                        className={`flex-1 rounded-sm ${
                          isDark ? "bg-white/20 group-hover:bg-white/35" : "bg-black/20 group-hover:bg-black/40"
                        } transition-colors`}
                        style={{
                          height: `${h}%`,
                          animation: aiDemosPlaying
                            ? `cs-equalize ${1.2 + (j % 5) * 0.2}s ease-in-out ${j * 40}ms infinite alternate`
                            : "none",
                          transformOrigin: "center bottom",
                        }}
                      ></div>
                    );
                  })}
                </div>

                <div className="flex items-center justify-between">
                  <div className="flex flex-wrap gap-1.5">
                    {m.topics.slice(0, 3).map((t) => (
                      <span
                        key={t}
                        className={`text-[10px] px-2 py-0.5 rounded-md font-mono ${
                          isDark ? "bg-white/5 text-white/55" : "bg-black/[0.04] text-black/55"
                        }`}
                      >
                        {t}
                      </span>
                    ))}
                    {m.topics.length > 3 && (
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded-md font-mono ${
                          isDark ? "text-white/35" : "text-black/35"
                        }`}
                      >
                        +{m.topics.length - 3}
                      </span>
                    )}
                  </div>
                  <div
                    className={`flex items-center gap-1.5 text-[11px] ${
                      isDark ? "text-white/50" : "text-black/50"
                    }`}
                  >
                    <I.Users size={11} />
                    {m.people}
                  </div>
                </div>
              </div>
            </FadeUp>
          ))}
          {filtered.length === 0 && (
            <div
              className={`md:col-span-2 text-center py-16 rounded-2xl border ${
                isDark ? "border-white/10 text-white/40" : "border-black/[0.06] text-black/40"
              }`}
            >
              <p className="text-[13px] font-mono">No meetings match that query.</p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

export function ScribeIntegrations() {
  const { isDark } = useScribeTheme();
  const tools = [
    { n: "Zoom", c: "#2D8CFF" },
    { n: "Google Meet", c: "#00832D" },
    { n: "MS Teams", c: "#5059C9" },
    { n: "Webex", c: "#064E40" },
    { n: "Dialpad", c: "#7B40C4" },
    { n: "Google Cal", c: "#4285F4" },
    { n: "Outlook", c: "#0078D4" },
    { n: "Salesforce", c: "#00A1E0" },
    { n: "HubSpot", c: "#FF7A59" },
    { n: "Slack", c: "#4A154B" },
  ];
  return (
    <section className={`${isDark ? "bg-[#0a0a0a] text-white" : "bg-[#fafafa] text-black"} py-24 px-6`}>
      <div className="max-w-6xl mx-auto">
        <FadeUp className="mb-10 max-w-2xl">
          <Eyebrow className="mb-4">Integrations</Eyebrow>
          <h3 className="text-[28px] sm:text-[36px] leading-[1.08] tracking-[-0.02em] font-medium">
            Lives where your team already lives.
          </h3>
        </FadeUp>
        <FadeUp delay={80}>
          <div className="flex flex-wrap gap-2">
            {tools.map((t) => (
              <div
                key={t.n}
                className={`inline-flex items-center gap-2.5 rounded-full border px-4 py-2 ${
                  isDark ? "bg-[#121212] border-white/10" : "bg-white border-black/[0.06]"
                }`}
              >
                <span className="w-2 h-2 rounded-full" style={{ background: t.c }}></span>
                <span className={`text-[12px] font-medium ${isDark ? "text-white/75" : "text-black/75"}`}>{t.n}</span>
              </div>
            ))}
            <div
              className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 font-mono text-[11px] tracking-wider uppercase ${
                isDark ? "bg-white/[0.02] border-white/10 text-white/45" : "bg-white border-black/[0.06] text-black/45"
              }`}
            >
              +28 more
            </div>
          </div>
        </FadeUp>
      </div>
    </section>
  );
}

export function ScribeCrossProduct() {
  const { isDark } = useScribeTheme();
  const tone = isDark ? "dark" : "light";
  const vault = PRODUCTS.vdr;
  return (
    <section className={`${isDark ? "bg-[#0e0e0e] text-white" : "bg-white text-black"} py-24 px-6`}>
      <div className="max-w-6xl mx-auto">
        <FadeUp>
          <div
            className={`rounded-3xl border overflow-hidden ${
              isDark
                ? "border-white/10 bg-gradient-to-br from-[#121212] to-[#0e0e0e]"
                : "border-black/[0.06] bg-gradient-to-br from-[#fafafa] to-white"
            }`}
          >
            <div className="grid md:grid-cols-2 gap-10 p-10 md:p-14 items-center">
              <div>
                <div
                  className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-[11px] mb-5 font-mono tracking-wider uppercase ${vault.bg[tone]} ${vault.text[tone]}`}
                >
                  <I.Shield size={11} /> Pairs with CogniVault
                </div>
                <h3 className="text-[28px] sm:text-[36px] leading-[1.08] tracking-[-0.02em] font-medium mb-4">
                  Where conversations
                  <br />
                  <span
                    className="font-display italic font-normal"
                    style={{ color: isDark ? "rgba(255,255,255,0.4)" : "rgba(0,0,0,0.35)" }}
                  >
                    meet contracts.
                  </span>
                </h3>
                <p className={`text-[14px] leading-relaxed mb-6 ${isDark ? "text-white/55" : "text-black/60"}`}>
                  Every CogniScribe transcript becomes a first-class citizen inside CogniVault — so an analyst asking
                  the workspace about revenue gets an answer that cites both the Excel model and the CFO&apos;s quote
                  on the mgmt call.
                </p>
                <Link
                  href={vault.href}
                  className={`inline-flex items-center gap-1.5 text-[13px] font-medium ${
                    isDark ? "text-emerald-300 hover:text-emerald-200" : "text-emerald-700 hover:text-emerald-800"
                  }`}
                >
                  Tour CogniVault <I.Arrow size={13} />
                </Link>
              </div>
              <div
                className={`rounded-xl border p-5 ${
                  isDark ? "bg-black/30 border-white/5" : "bg-white border-black/[0.05]"
                }`}
              >
                <div className="flex items-center gap-2 mb-3">
                  <I.Sparkles size={12} className="text-emerald-500" />
                  <span
                    className={`text-[10px] font-mono tracking-wider uppercase ${
                      isDark ? "text-white/45" : "text-black/45"
                    }`}
                  >
                    Blended answer
                  </span>
                </div>
                <p className={`text-[13px] mb-4 ${isDark ? "text-white/85" : "text-black/85"}`}>
                  &ldquo;Reconcile the revenue number the CEO quoted with the P&amp;L in the data room.&rdquo;
                </p>
                <div
                  className={`rounded-lg border-l-2 p-3 mb-2 ${
                    isDark ? "border-l-amber-400 bg-white/[0.03]" : "border-l-amber-500 bg-amber-50/40"
                  }`}
                >
                  <p
                    className={`text-[10px] font-mono uppercase tracking-wider mb-1 ${
                      isDark ? "text-amber-300/80" : "text-amber-700"
                    }`}
                  >
                    Call · Apr 14 · 00:14:02 · CEO
                  </p>
                  <p className={`text-[12px] ${isDark ? "text-white/75" : "text-black/75"}`}>
                    &ldquo;We ended at $64.1M top line for the LTM.&rdquo;
                  </p>
                </div>
                <div
                  className={`rounded-lg border-l-2 p-3 ${
                    isDark ? "border-l-emerald-400 bg-white/[0.03]" : "border-l-emerald-500 bg-emerald-50/40"
                  }`}
                >
                  <p
                    className={`text-[10px] font-mono uppercase tracking-wider mb-1 ${
                      isDark ? "text-emerald-300/80" : "text-emerald-700"
                    }`}
                  >
                    Doc · LTM_PnL_FY24.xlsx · Row 12
                  </p>
                  <p className={`text-[12px] ${isDark ? "text-white/75" : "text-black/75"}`}>
                    Revenue (LTM, audited) = $64,107,428. ✓ Match.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </FadeUp>
      </div>
    </section>
  );
}

export function ScribeCTA() {
  const { isDark } = useScribeTheme();
  return (
    <section
      id="get-started"
      className={`${
        isDark ? "bg-[#0a0a0a] text-white" : "bg-[#fafafa] text-black"
      } py-32 px-6 relative overflow-hidden`}
    >
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: `radial-gradient(ellipse 60% 80% at 50% 100%, ${accentRgb(isDark ? 0.18 : 0.12)}, transparent 60%)`,
        }}
      ></div>
      <FadeUp className="relative max-w-3xl mx-auto text-center">
        <h2 className="text-[44px] sm:text-[60px] leading-[0.98] tracking-[-0.03em] font-medium mb-6">
          Stop taking notes.
          <br />
          <span
            className="font-display italic font-normal"
            style={{ color: isDark ? "rgba(255,255,255,0.4)" : "rgba(0,0,0,0.35)" }}
          >
            Start asking questions.
          </span>
        </h2>
        <p
          className={`text-[16px] leading-relaxed mb-10 max-w-lg mx-auto ${
            isDark ? "text-white/55" : "text-black/55"
          }`}
        >
          Connect your calendar and watch every call turn into a first-class asset. 14-day trial, no credit card.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link
            href="/login?mode=signup"
            className="inline-flex items-center gap-2 h-12 px-7 rounded-full text-[14px] font-medium whitespace-nowrap"
            style={{ background: accentSolid, color: "#3a1e00" }}
          >
            Start free <I.Arrow size={14} />
          </Link>
          <a
            href="#talk"
            className={`inline-flex items-center gap-2 h-12 px-7 rounded-full text-[14px] font-medium whitespace-nowrap border ${
              isDark
                ? "border-white/15 text-white/80 hover:bg-white/5"
                : "border-black/15 text-black/75 hover:bg-black/[0.04]"
            }`}
          >
            Book a demo
          </a>
        </div>
      </FadeUp>
    </section>
  );
}
