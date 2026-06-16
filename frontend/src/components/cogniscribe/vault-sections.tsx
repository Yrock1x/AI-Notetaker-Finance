"use client";

import Link from "next/link";
import { useState } from "react";
import { Eyebrow, FadeUp } from "./primitives";
import { useScribeTheme } from "./theme-provider";
import { I } from "./icons";
import { RequestListDemo } from "./request-list-demo";
import { ChatDemo } from "./chat-demo";
import { PRODUCTS } from "./products";

const VAULT_ACCENT = "16 185 129";
const accentRgb = (alpha: number) => `rgba(${VAULT_ACCENT}, ${alpha})`;
const accentSolid = `rgb(${VAULT_ACCENT})`;

export function VaultHero() {
  const { isDark } = useScribeTheme();
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
          background: `radial-gradient(ellipse 70% 50% at 15% 0%, ${accentRgb(isDark ? 0.18 : 0.1)}, transparent 60%)`,
        }}
      ></div>
      <div className={`absolute inset-0 noise ${isDark ? "opacity-[0.04]" : "opacity-[0.03]"} pointer-events-none`}></div>

      <div className="relative max-w-7xl mx-auto px-6 pt-36 pb-24 grid lg:grid-cols-12 gap-12 items-center">
        <div className="lg:col-span-6">
          <div
            className="fade-up inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[11px] mb-8 backdrop-blur-sm"
            style={{
              borderColor: accentRgb(0.3),
              background: accentRgb(isDark ? 0.1 : 0.08),
              color: isDark ? "rgba(255,255,255,0.85)" : "rgba(0,0,0,0.75)",
            }}
          >
            <I.Shield size={11} />
            <span className="font-mono tracking-wider uppercase">CogniVault · AI-native data room</span>
          </div>

          <h1 className="fade-up d-100 text-[52px] sm:text-[64px] lg:text-[76px] leading-[0.95] tracking-[-0.035em] font-medium mb-8">
            Every document,
            <br />
            <span
              className="font-display italic font-normal"
              style={{ color: isDark ? "rgba(255,255,255,0.55)" : "rgba(0,0,0,0.45)" }}
            >
              instantly understood.
            </span>
          </h1>

          <p
            className={`fade-up d-200 text-[17px] leading-relaxed max-w-lg mb-10 ${
              isDark ? "text-white/55" : "text-black/55"
            }`}
          >
            Upload contracts, financials, memos, transcripts. CogniVault indexes them the moment they arrive,
            auto-matches to your request list, answers questions with page citations, and enforces every permission at
            the data layer.
          </p>

          <div className="fade-up d-300 flex flex-col sm:flex-row items-start gap-3 mb-10">
            <Link
              href="/#get-started"
              className="inline-flex items-center justify-center gap-2 h-11 px-6 rounded-full text-[13px] font-medium whitespace-nowrap"
              style={{ background: accentSolid, color: "#052e1e" }}
            >
              Start a trial <I.Arrow size={14} />
            </Link>
            <a
              href="#how"
              className={`inline-flex items-center justify-center gap-2 h-11 px-6 rounded-full text-[13px] font-medium border ${
                isDark
                  ? "border-white/15 text-white/80 hover:bg-white/5"
                  : "border-black/15 text-black/75 hover:bg-black/[0.04]"
              }`}
            >
              How it works
            </a>
          </div>

          <div className="fade-up d-400 grid grid-cols-3 gap-4 max-w-md">
            {[
              { k: "72%", v: "faster diligence" },
              { k: "11×", v: "request-list fill" },
              { k: "100%", v: "answers cited" },
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

        <div className="fade-up d-200 lg:col-span-6">
          <div
            className={`rounded-2xl border p-6 md:p-7 shadow-2xl ${
              isDark ? "border-white/10 bg-[#121212]" : "border-black/[0.06] bg-white"
            }`}
            style={{
              boxShadow: isDark
                ? `0 40px 80px -30px ${accentRgb(0.25)}`
                : `0 40px 80px -40px ${accentRgb(0.4)}`,
            }}
          >
            <RequestListDemo />
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

export function HowItWorks() {
  const { isDark } = useScribeTheme();
  const steps = [
    {
      n: "01",
      t: "Upload",
      d: "Drag in a folder — contracts, Excel models, transcripts, memos, emails. CogniVault indexes every page as it arrives and builds embeddings in the background.",
      Ic: I.Folder,
      chip: "Native parsers for 140+ file types",
    },
    {
      n: "02",
      t: "Index",
      d: "AI auto-classifies into a structured request list (DD folders, legal matters, working-paper tabs) and extracts the facts, tables, and clauses that matter.",
      Ic: I.Brain,
      chip: "Entity, clause & metric extraction",
    },
    {
      n: "03",
      t: "Ask",
      d: "Chat with the whole workspace. Every answer links back to the exact page it came from. Share a link to an answer — or export a watermarked memo.",
      Ic: I.Sparkles,
      chip: "Citation-grade Q&A",
    },
  ];
  return (
    <section id="how" className={`${isDark ? "bg-[#0e0e0e] text-white" : "bg-white text-black"} py-28 px-6`}>
      <div className="max-w-6xl mx-auto">
        <FadeUp className="mb-14 max-w-2xl">
          <Eyebrow className="mb-4">How CogniVault works</Eyebrow>
          <h2 className="text-[38px] sm:text-[54px] leading-[1.02] tracking-[-0.02em] font-medium">
            Three steps from a folder
            <br />
            <span
              className="font-display italic font-normal"
              style={{ color: isDark ? "rgba(255,255,255,0.45)" : "rgba(0,0,0,0.35)" }}
            >
              to a grounded answer.
            </span>
          </h2>
        </FadeUp>

        <div className="grid md:grid-cols-3 gap-4">
          {steps.map((s, i) => {
            const Ic = s.Ic;
            return (
              <FadeUp key={s.n} delay={i * 100}>
                <div
                  className={`relative rounded-2xl border p-7 h-full ${
                    isDark ? "bg-[#121212] border-white/10" : "bg-[#fafafa] border-black/[0.06]"
                  }`}
                >
                  <div className="flex items-center justify-between mb-8">
                    <span className="font-display text-5xl tabular-nums" style={{ color: accentSolid }}>
                      {s.n}
                    </span>
                    <div
                      className={`w-9 h-9 rounded-lg flex items-center justify-center ${
                        isDark ? "bg-white/5" : "bg-black/[0.04]"
                      }`}
                    >
                      <Ic size={16} className={isDark ? "text-white/75" : "text-black/75"} />
                    </div>
                  </div>
                  <h3 className={`text-[22px] font-medium mb-3 ${isDark ? "text-white/90" : "text-black/90"}`}>
                    {s.t}
                  </h3>
                  <p className={`text-[13px] leading-relaxed mb-5 ${isDark ? "text-white/55" : "text-black/60"}`}>
                    {s.d}
                  </p>
                  <div
                    className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-mono tracking-wider uppercase ${
                      isDark ? "bg-white/5 text-white/50" : "bg-black/[0.04] text-black/50"
                    }`}
                  >
                    <span className="w-1 h-1 rounded-full" style={{ background: accentSolid }}></span>
                    {s.chip}
                  </div>
                </div>
              </FadeUp>
            );
          })}
        </div>
      </div>
    </section>
  );
}

export function VaultChat() {
  const { isDark } = useScribeTheme();
  return (
    <section className={`${isDark ? "bg-[#0a0a0a] text-white" : "bg-[#fafafa] text-black"} py-28 px-6`}>
      <div className="max-w-6xl mx-auto grid md:grid-cols-2 gap-16 items-center">
        <FadeUp delay={100}>
          <div
            className={`rounded-2xl border p-6 md:p-7 shadow-xl ${
              isDark ? "border-white/10 bg-[#121212]" : "border-black/[0.06] bg-white"
            }`}
          >
            <ChatDemo />
          </div>
        </FadeUp>

        <FadeUp>
          <Eyebrow className="mb-4">Chat with the room</Eyebrow>
          <h3 className="text-[38px] sm:text-[48px] leading-[1.02] tracking-[-0.02em] font-medium mb-6">
            Every answer, cited.
            <br />
            <span
              className="font-display italic font-normal"
              style={{ color: isDark ? "rgba(255,255,255,0.4)" : "rgba(0,0,0,0.35)" }}
            >
              Every claim, traceable.
            </span>
          </h3>
          <p className={`text-[15px] leading-relaxed mb-8 ${isDark ? "text-white/55" : "text-black/60"}`}>
            Ask a question in plain language. CogniVault retrieves the relevant pages, synthesizes an answer, and shows
            you exactly which sources were used — with the page numbers, section refs, and direct links. No
            hallucinations. No black box.
          </p>
          <div className="grid sm:grid-cols-2 gap-3">
            {[
              { t: "Per-sentence citations", d: "Every claim hyperlinked to the source page" },
              { t: "Refusal on uncertainty", d: "No evidence → no answer, every time" },
              { t: "Scoped retrieval", d: "Permissions enforced inside the AI call" },
              { t: "Share as artifact", d: "Turn an answer into a watermarked memo" },
            ].map((x) => (
              <div
                key={x.t}
                className={`rounded-xl border p-4 ${
                  isDark ? "bg-white/[0.02] border-white/10" : "bg-white border-black/[0.06]"
                }`}
              >
                <p className={`text-[13px] font-medium mb-1 ${isDark ? "text-white/85" : "text-black/85"}`}>
                  {x.t}
                </p>
                <p className={`text-[12px] ${isDark ? "text-white/45" : "text-black/50"}`}>{x.d}</p>
              </div>
            ))}
          </div>
        </FadeUp>
      </div>
    </section>
  );
}

export function VaultFeatures() {
  const { isDark } = useScribeTheme();
  const features = [
    {
      Ic: I.Eye,
      t: "Engagement analytics",
      d: "See which buyer viewed which doc, for how long, and flag exhaust you didn't expect.",
    },
    {
      Ic: I.Lock,
      t: "Granular permissions",
      d: "Party-, folder-, and clause-level visibility. No UI-only ACLs — enforced at the database.",
    },
    {
      Ic: I.Paper,
      t: "Watermarked exports",
      d: "Every downloaded PDF is stamped per-recipient, with a revocable access link.",
    },
    {
      Ic: I.Git,
      t: "Versioned everything",
      d: "Every document, clause, and redline is versioned with diff and change rationale.",
    },
    {
      Ic: I.Filter,
      t: "Q&A workflow",
      d: "Buyer questions are routed, answered, and disclosed to the room with full audit.",
    },
    {
      Ic: I.Zap,
      t: "Integrations",
      d: "Native connectors for Google Drive, SharePoint, Dropbox, Box, and iManage.",
    },
  ];
  return (
    <section className={`${isDark ? "bg-[#0e0e0e] text-white" : "bg-white text-black"} py-28 px-6`}>
      <div className="max-w-6xl mx-auto">
        <FadeUp className="mb-12 max-w-2xl">
          <Eyebrow className="mb-4">What&apos;s inside</Eyebrow>
          <h3 className="text-[32px] sm:text-[44px] leading-[1.05] tracking-[-0.02em] font-medium">
            Everything a modern data room{" "}
            <span
              className="font-display italic font-normal"
              style={{ color: isDark ? "rgba(255,255,255,0.4)" : "rgba(0,0,0,0.35)" }}
            >
              should already have.
            </span>
          </h3>
        </FadeUp>
        <div className="grid md:grid-cols-3 gap-4">
          {features.map((f, i) => {
            const Fi = f.Ic;
            return (
              <FadeUp key={f.t} delay={i * 60}>
                <div
                  className={`rounded-xl border p-5 h-full ${
                    isDark ? "bg-[#121212] border-white/10" : "bg-[#fafafa] border-black/[0.06]"
                  }`}
                >
                  <div
                    className="w-9 h-9 rounded-lg flex items-center justify-center mb-4"
                    style={{
                      background: accentRgb(isDark ? 0.15 : 0.1),
                      color: accentSolid,
                    }}
                  >
                    <Fi size={16} />
                  </div>
                  <p className={`text-[15px] font-medium mb-1.5 ${isDark ? "text-white/90" : "text-black/90"}`}>
                    {f.t}
                  </p>
                  <p className={`text-[13px] leading-relaxed ${isDark ? "text-white/50" : "text-black/55"}`}>
                    {f.d}
                  </p>
                </div>
              </FadeUp>
            );
          })}
        </div>
      </div>
    </section>
  );
}

type CaseKey = "finance" | "legal" | "advisory";
type CaseDef = {
  k: CaseKey;
  name: string;
  Ic: typeof I.TrendUp;
  title: string;
  scenario: string;
  timeline: { day: string; ev: string }[];
};

export function VaultUseCases() {
  const { isDark } = useScribeTheme();
  const cases: CaseDef[] = [
    {
      k: "finance",
      name: "Finance",
      Ic: I.TrendUp,
      title: "Sell-side M&A",
      scenario: "Project Lyra · 140 buyers · 18k pages",
      timeline: [
        { day: "Mon", ev: "Teaser goes live. 40 NDAs signed by EOD." },
        { day: "Tue", ev: "Request list auto-fills 68% of the 312 items overnight." },
        {
          day: "Wed",
          ev: "Buyer A asks about customer concentration — AI flags the Top-25 file already in the room.",
        },
        {
          day: "Thu",
          ev: "Management presentation recorded in CogniScribe — transcript cited back into the VDR.",
        },
        { day: "Fri", ev: "Weekly engagement report surfaces Buyer C as the most active on commercial docs." },
      ],
    },
    {
      k: "legal",
      name: "Legal",
      Ic: I.Scale,
      title: "Corporate · M&A counsel",
      scenario: "Project Meridian · 3 parties · 42k pages",
      timeline: [
        {
          day: "Mon",
          ev: "Clean-room opened for seller-side counsel only. AI auto-redacts commercially sensitive material.",
        },
        { day: "Tue", ev: "3,200 clauses auto-extracted across 214 contracts — grouped by type." },
        {
          day: "Wed",
          ev: "Buyer counsel asks \"show me every change-of-control provision.\" Answer cites 47 clauses.",
        },
        { day: "Thu", ev: "Redline memo drafted in-app, with every edit tied to a specific source clause." },
        { day: "Fri", ev: "SPA-ready disclosure schedules generated from the extracted dataset." },
      ],
    },
    {
      k: "advisory",
      name: "Advisory",
      Ic: I.Briefcase,
      title: "Consulting engagement",
      scenario: "Fortune-100 restructuring · 6 workstreams",
      timeline: [
        { day: "Mon", ev: "Engagement kickoff. All prior working papers uploaded and indexed." },
        { day: "Tue", ev: "Client interview series begins — CogniScribe captures, CogniVault stores." },
        {
          day: "Wed",
          ev: 'Junior asks "what did the CFO say about working capital?" — cited back across 4 calls.',
        },
        { day: "Thu", ev: "Draft board deck pulls charts with provenance linked to source workpapers." },
        { day: "Fri", ev: "Partner reviews with a single audit trail across every deliverable." },
      ],
    },
  ];
  const [active, setActive] = useState<CaseKey>("finance");
  const c = cases.find((x) => x.k === active)!;
  const Ic = c.Ic;

  return (
    <section className={`${isDark ? "bg-[#0a0a0a] text-white" : "bg-[#fafafa] text-black"} py-28 px-6`}>
      <div className="max-w-6xl mx-auto">
        <FadeUp className="mb-10 max-w-2xl">
          <Eyebrow className="mb-4">In practice</Eyebrow>
          <h3 className="text-[32px] sm:text-[44px] leading-[1.05] tracking-[-0.02em] font-medium">
            A week in a CogniVault.
            <br />
            <span
              className="font-display italic font-normal"
              style={{ color: isDark ? "rgba(255,255,255,0.4)" : "rgba(0,0,0,0.35)" }}
            >
              One workspace, three practices.
            </span>
          </h3>
        </FadeUp>

        <FadeUp delay={60}>
          <div
            className={`inline-flex gap-1 rounded-full p-1 border mb-8 ${
              isDark ? "bg-white/[0.03] border-white/10" : "bg-white border-black/[0.06]"
            }`}
          >
            {cases.map((cs) => {
              const Si = cs.Ic;
              const on = active === cs.k;
              return (
                <button
                  key={cs.k}
                  onClick={() => setActive(cs.k)}
                  className={`inline-flex items-center gap-2 text-[13px] font-medium px-4 py-2 rounded-full transition-colors ${
                    on
                      ? isDark
                        ? "bg-white text-[#0a0a0a]"
                        : "bg-[#0a0a0a] text-white"
                      : isDark
                      ? "text-white/55 hover:text-white/80"
                      : "text-black/55 hover:text-black/80"
                  }`}
                >
                  <Si size={13} />
                  {cs.name}
                </button>
              );
            })}
          </div>
        </FadeUp>

        <FadeUp key={active} delay={50}>
          <div
            className={`rounded-2xl border overflow-hidden ${
              isDark ? "bg-[#121212] border-white/10" : "bg-white border-black/[0.06]"
            }`}
          >
            <div
              className={`px-7 py-5 border-b flex items-center gap-3 ${
                isDark ? "border-white/5 bg-white/[0.02]" : "border-black/[0.05] bg-[#fafafa]"
              }`}
            >
              <div
                className="w-9 h-9 rounded-lg flex items-center justify-center"
                style={{
                  background: accentRgb(isDark ? 0.15 : 0.1),
                  color: accentSolid,
                }}
              >
                <Ic size={16} />
              </div>
              <div className="flex-1">
                <p className={`text-[15px] font-medium ${isDark ? "text-white/90" : "text-black/90"}`}>
                  {c.title}
                </p>
                <p
                  className={`text-[11px] font-mono tracking-wider uppercase mt-0.5 ${
                    isDark ? "text-white/40" : "text-black/40"
                  }`}
                >
                  {c.scenario}
                </p>
              </div>
            </div>
            <div className="p-7">
              <div className="relative">
                <div
                  className={`absolute left-[30px] top-3 bottom-3 w-px ${
                    isDark ? "bg-white/10" : "bg-black/[0.08]"
                  }`}
                ></div>
                <ul className="flex flex-col gap-4">
                  {c.timeline.map((t, i) => (
                    <li key={i} className="flex items-start gap-5">
                      <div className="relative z-10 w-16 shrink-0 text-right">
                        <span
                          className={`text-[11px] font-mono tracking-wider uppercase ${
                            isDark ? "text-white/35" : "text-black/35"
                          }`}
                        >
                          {t.day}
                        </span>
                      </div>
                      <div
                        className="relative z-10 w-3 h-3 rounded-full mt-1 shrink-0 border-2"
                        style={{
                          borderColor: accentSolid,
                          background: isDark ? "#121212" : "#fff",
                        }}
                      ></div>
                      <p className={`text-[14px] leading-relaxed ${isDark ? "text-white/75" : "text-black/75"}`}>
                        {t.ev}
                      </p>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </FadeUp>
      </div>
    </section>
  );
}

export function VaultCrossProduct() {
  const { isDark } = useScribeTheme();
  const tone = isDark ? "dark" : "light";
  const mic = PRODUCTS.mic;
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
                  className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-[11px] mb-5 font-mono tracking-wider uppercase ${mic.bg[tone]} ${mic.text[tone]}`}
                >
                  <I.Mic size={11} /> Pairs with CogniScribe
                </div>
                <h3 className="text-[28px] sm:text-[36px] leading-[1.08] tracking-[-0.02em] font-medium mb-4">
                  Meetings in. Documents out.
                  <br />
                  <span
                    className="font-display italic font-normal"
                    style={{ color: isDark ? "rgba(255,255,255,0.4)" : "rgba(0,0,0,0.35)" }}
                  >
                    Same shared memory.
                  </span>
                </h3>
                <p className={`text-[14px] leading-relaxed mb-6 ${isDark ? "text-white/55" : "text-black/60"}`}>
                  CogniScribe captures every management meeting, buyer call, and working session — then pipes the
                  transcript into CogniVault so a question asked about documents can be answered with what was said.
                </p>
                <Link
                  href={mic.href}
                  className={`inline-flex items-center gap-1.5 text-[13px] font-medium ${
                    isDark ? "text-amber-300 hover:text-amber-200" : "text-amber-700 hover:text-amber-800"
                  }`}
                >
                  Tour CogniScribe <I.Arrow size={13} />
                </Link>
              </div>
              <div
                className={`rounded-xl border p-5 ${
                  isDark ? "bg-black/30 border-white/5" : "bg-white border-black/[0.05]"
                }`}
              >
                <div className="flex items-center gap-2 mb-3">
                  <I.Sparkles size={12} className="text-amber-500" />
                  <span
                    className={`text-[10px] font-mono tracking-wider uppercase ${
                      isDark ? "text-white/45" : "text-black/45"
                    }`}
                  >
                    Cross-product query
                  </span>
                </div>
                <p className={`text-[13px] mb-4 ${isDark ? "text-white/85" : "text-black/85"}`}>
                  &ldquo;What did the CFO say about working capital, and which VDR document does it relate to?&rdquo;
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
                    CogniScribe · Apr 14 · 00:42:18
                  </p>
                  <p className={`text-[12px] ${isDark ? "text-white/75" : "text-black/75"}`}>
                    &ldquo;Working capital was a drag of $2.1M this quarter, driven by a shift in AR timing.&rdquo;
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
                    CogniVault · WC_Bridge_FY24.xlsx · Row 47
                  </p>
                  <p className={`text-[12px] ${isDark ? "text-white/75" : "text-black/75"}`}>
                    AR days outstanding 44 → 52, Δ working capital −$2.1M.
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

export function VaultCTA() {
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
          Turn a folder
          <br />
          <span
            className="font-display italic font-normal"
            style={{ color: isDark ? "rgba(255,255,255,0.4)" : "rgba(0,0,0,0.35)" }}
          >
            into a live deal.
          </span>
        </h2>
        <p
          className={`text-[16px] leading-relaxed mb-10 max-w-lg mx-auto ${
            isDark ? "text-white/55" : "text-black/55"
          }`}
        >
          Bring your next engagement to CogniVault — a 14-day trial, full feature set, no credit card.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link
            href="/login?mode=signup"
            className="inline-flex items-center gap-2 h-12 px-7 rounded-full text-[14px] font-medium whitespace-nowrap"
            style={{ background: accentSolid, color: "#052e1e" }}
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
