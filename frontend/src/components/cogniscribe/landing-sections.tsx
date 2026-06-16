"use client";

import Link from "next/link";
import { useState } from "react";
import { Eyebrow, FadeUp } from "./primitives";
import { useScribeTheme } from "./theme-provider";
import { I } from "./icons";
import { PlatformArtifact } from "./platform-artifact";
import { PRODUCTS } from "./products";

const EMERALD = "16 185 129";

export function LandingHero() {
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
          background: `radial-gradient(ellipse 80% 50% at 20% 0%, rgba(${EMERALD}, ${
            isDark ? 0.12 : 0.08
          }), transparent 60%)`,
        }}
      ></div>
      <div className={`absolute inset-0 noise ${isDark ? "opacity-[0.04]" : "opacity-[0.03]"} pointer-events-none`}></div>

      <div className="relative max-w-7xl mx-auto px-6 pt-36 pb-24 grid lg:grid-cols-12 gap-12 items-center">
        <div className="lg:col-span-6">
          <div
            className="fade-up inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[11px] mb-8 backdrop-blur-sm"
            style={{
              borderColor: `rgba(${EMERALD}, 0.3)`,
              background: `rgba(${EMERALD}, ${isDark ? 0.08 : 0.06})`,
              color: isDark ? "rgba(255,255,255,0.85)" : "rgba(0,0,0,0.75)",
            }}
          >
            <span className="w-1.5 h-1.5 rounded-full breathe" style={{ background: "#10b981" }}></span>
            <span className="font-mono tracking-wider uppercase">Now in private beta</span>
          </div>

          <h1 className="fade-up d-100 text-[52px] sm:text-[68px] lg:text-[80px] leading-[0.95] tracking-[-0.035em] font-medium mb-8">
            The AI workspace
            <br />
            <span
              className="font-display italic font-normal"
              style={{ color: isDark ? "rgba(255,255,255,0.55)" : "rgba(0,0,0,0.45)" }}
            >
              for complex&nbsp;
            </span>
            <span className="font-display italic font-normal">engagements.</span>
          </h1>

          <p
            className={`fade-up d-200 text-[17px] leading-relaxed max-w-lg mb-10 ${
              isDark ? "text-white/55" : "text-black/55"
            }`}
          >
            Purpose-built for finance, legal, and advisory teams. A secure data room and a meeting intelligence engine —
            sharing one context, one audit trail, one source of truth.
          </p>

          <div className="fade-up d-300 flex flex-col sm:flex-row items-start gap-3 mb-10">
            <a
              href="#get-started"
              className={`inline-flex items-center justify-center gap-2 h-11 px-6 rounded-full text-[13px] font-medium ${
                isDark ? "bg-white text-[#0a0a0a] hover:bg-white/90" : "bg-[#0a0a0a] text-white hover:bg-black/90"
              }`}
            >
              Start a 14-day trial <I.Arrow size={14} />
            </a>
            <a
              href="#products"
              className={`inline-flex items-center justify-center gap-2 h-11 px-6 rounded-full text-[13px] font-medium border ${
                isDark
                  ? "border-white/15 text-white/80 hover:bg-white/5"
                  : "border-black/15 text-black/75 hover:bg-black/[0.04]"
              }`}
            >
              Explore the products
            </a>
          </div>

          <div className="fade-up d-400 flex items-center gap-5">
            <div className="flex -space-x-2">
              {["M", "R", "S", "K"].map((l, i) => (
                <div
                  key={l}
                  className={`w-7 h-7 rounded-full border-2 flex items-center justify-center text-[10px] font-semibold ${
                    isDark ? "border-[#0a0a0a] bg-white/10 text-white/70" : "border-[#fafafa] bg-black/[0.06] text-black/60"
                  }`}
                  style={{ zIndex: 10 - i }}
                >
                  {l}
                </div>
              ))}
            </div>
            <div>
              <p
                className={`text-[11px] font-mono tracking-wider uppercase ${
                  isDark ? "text-white/35" : "text-black/35"
                }`}
              >
                Backed by
              </p>
              <p className={`text-[12px] ${isDark ? "text-white/60" : "text-black/60"}`}>
                Operators from Goldman, Blackstone &amp; Anthropic
              </p>
            </div>
          </div>
        </div>

        <div className="fade-up d-200 lg:col-span-6">
          <PlatformArtifact />
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

export function LogoMarquee() {
  const { isDark, aiDemosPlaying } = useScribeTheme();
  const logos = [
    "BLACKSTONE",
    "KKR",
    "LAZARD",
    "EVERCORE",
    "MOELIS",
    "LATHAM",
    "SKADDEN",
    "DAVIS POLK",
    "PJT PARTNERS",
    "WACHTELL",
  ];
  return (
    <section
      className={`py-14 border-y ${
        isDark ? "bg-[#0a0a0a] text-white border-white/5" : "bg-[#fafafa] text-black border-black/[0.06]"
      } overflow-hidden`}
    >
      <div className="max-w-7xl mx-auto px-6 mb-8">
        <Eyebrow className="text-center">Used by finance, legal &amp; advisory teams at</Eyebrow>
      </div>
      <div className={`relative ${aiDemosPlaying ? "" : "paused"}`}>
        <div className="flex marquee-track" style={{ width: "max-content" }}>
          {[...logos, ...logos].map((name, i) => (
            <div
              key={i}
              className={`px-10 py-2 whitespace-nowrap font-mono text-[12px] tracking-[0.22em] ${
                isDark ? "text-white/30" : "text-black/30"
              }`}
            >
              {name}
            </div>
          ))}
        </div>
        <div
          className={`absolute top-0 bottom-0 left-0 w-24 pointer-events-none bg-gradient-to-r ${
            isDark ? "from-[#0a0a0a]" : "from-[#fafafa]"
          } to-transparent`}
        ></div>
        <div
          className={`absolute top-0 bottom-0 right-0 w-24 pointer-events-none bg-gradient-to-l ${
            isDark ? "from-[#0a0a0a]" : "from-[#fafafa]"
          } to-transparent`}
        ></div>
      </div>
    </section>
  );
}

type IndustryKey = "finance" | "legal" | "advisory";

const INDUSTRIES: Record<
  IndustryKey,
  {
    name: string;
    Icon: typeof I.TrendUp;
    tag: string;
    headline: string;
    copy: string;
    metrics: { k: string; v: string }[];
    examples: string[];
  }
> = {
  finance: {
    name: "Finance",
    Icon: I.TrendUp,
    tag: "M&A · PE · Investment banking",
    headline: "Close more deals, with fewer all-nighters.",
    copy: "Run diligence on a fortified data room while every management meeting is captured, indexed, and cited. Request lists auto-fill themselves. Cap tables, financials, and transcripts are one chat away.",
    metrics: [
      { k: "72%", v: "faster diligence" },
      { k: "$3.2B", v: "transacted on platform" },
      { k: "11×", v: "quicker request fill" },
    ],
    examples: [
      "Sell-side VDR with buyer-side engagement analytics",
      "LBO model sanity check from financial statements",
      "Auto-summarized mgmt presentations with extracted metrics",
      "Cross-deal comparable retrieval",
    ],
  },
  legal: {
    name: "Legal",
    Icon: I.Scale,
    tag: "Corporate · Litigation · Regulatory",
    headline: "Every document reviewed. Every clause tracked.",
    copy: "Redline across thousands of pages. Extract reps, warranties, and covenants with citations. Keep privilege intact with party-to-party isolation and immutable audit logs — essential for litigation holds and regulatory inquiries.",
    metrics: [
      { k: "89%", v: "of clauses auto-tagged" },
      { k: "24/7", v: "audit log availability" },
      { k: "SOC 2", v: "Type II certified" },
    ],
    examples: [
      "Privileged doc isolation with clean-room workflows",
      "Clause extraction across LOIs, SPAs, and NDAs",
      "Deposition transcripts with timestamped citations",
      "Chronological fact patterns built from source material",
    ],
  },
  advisory: {
    name: "Advisory",
    Icon: I.Briefcase,
    tag: "Consulting · Accounting · Restructuring",
    headline: "Every engagement, one memory.",
    copy: "Partners' context is no longer trapped in inboxes. Client meetings, working papers, and deliverables share one searchable layer — so a junior consultant can ask the workspace what a senior heard on last week's board call.",
    metrics: [
      { k: "100%", v: "of meetings captured" },
      { k: "∞", v: "context retention" },
      { k: "48h", v: "average onboarding" },
    ],
    examples: [
      "Engagement-scoped chat grounded in working papers",
      "Client interview transcripts with extracted quotes",
      "Deliverable version history with change rationale",
      "Cross-engagement comparable playbook retrieval",
    ],
  },
};

export function IndustriesSection() {
  const { isDark } = useScribeTheme();
  const [active, setActive] = useState<IndustryKey>("finance");
  const curr = INDUSTRIES[active];
  const IIcon = curr.Icon;

  return (
    <section
      id="industries"
      className={`${isDark ? "bg-[#0a0a0a] text-white" : "bg-[#fafafa] text-black"} py-28 px-6`}
    >
      <div className="max-w-6xl mx-auto">
        <FadeUp className="mb-12 max-w-2xl">
          <Eyebrow className="mb-4">Built for professional services</Eyebrow>
          <h2 className="text-[38px] sm:text-[54px] leading-[1.02] tracking-[-0.02em] font-medium">
            Not another generic
            <br />
            <span
              className="font-display italic font-normal"
              style={{ color: isDark ? "rgba(255,255,255,0.45)" : "rgba(0,0,0,0.35)" }}
            >
              AI chatbot.
            </span>
          </h2>
          <p
            className={`text-[15px] leading-relaxed mt-5 max-w-lg ${
              isDark ? "text-white/55" : "text-black/55"
            }`}
          >
            Shaped around the workflows of the people who ship deals, opinions, and engagement letters for a living.
            One workspace — three practices.
          </p>
        </FadeUp>

        <FadeUp delay={100}>
          <div
            className={`inline-flex gap-1 rounded-full p-1 border mb-10 ${
              isDark ? "bg-white/[0.03] border-white/10" : "bg-white border-black/[0.06]"
            }`}
          >
            {(Object.entries(INDUSTRIES) as [IndustryKey, (typeof INDUSTRIES)[IndustryKey]][]).map(([k, v]) => {
              const Vi = v.Icon;
              const isActive = active === k;
              return (
                <button
                  key={k}
                  onClick={() => setActive(k)}
                  className={`inline-flex items-center gap-2 text-[13px] font-medium px-4 py-2 rounded-full transition-colors ${
                    isActive
                      ? isDark
                        ? "bg-white text-[#0a0a0a]"
                        : "bg-[#0a0a0a] text-white"
                      : isDark
                      ? "text-white/55 hover:text-white/80"
                      : "text-black/55 hover:text-black/80"
                  }`}
                >
                  <Vi size={13} />
                  {v.name}
                </button>
              );
            })}
          </div>
        </FadeUp>

        <FadeUp key={active} delay={60}>
          <div className="grid md:grid-cols-5 gap-10 md:gap-16 items-start">
            <div className="md:col-span-3">
              <div
                className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-[11px] mb-5 font-mono tracking-wider uppercase border ${
                  isDark
                    ? "text-white/55 border-white/10 bg-white/[0.03]"
                    : "text-black/55 border-black/[0.08] bg-white"
                }`}
              >
                <IIcon size={11} /> {curr.tag}
              </div>
              <h3 className="text-[32px] sm:text-[40px] leading-[1.05] tracking-[-0.02em] font-medium mb-5">
                {curr.headline}
              </h3>
              <p
                className={`text-[15px] leading-relaxed mb-8 max-w-lg ${
                  isDark ? "text-white/55" : "text-black/60"
                }`}
              >
                {curr.copy}
              </p>
              <ul className="flex flex-col gap-3">
                {curr.examples.map((e) => (
                  <li key={e} className="flex items-start gap-3">
                    <I.Check
                      size={14}
                      className={isDark ? "text-white/45 shrink-0 mt-0.5" : "text-black/45 shrink-0 mt-0.5"}
                    />
                    <span className={`text-[14px] ${isDark ? "text-white/70" : "text-black/70"}`}>{e}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="md:col-span-2 flex flex-col gap-3">
              {curr.metrics.map((m) => (
                <div
                  key={m.v}
                  className={`rounded-2xl border p-5 ${
                    isDark ? "bg-[#121212] border-white/10" : "bg-white border-black/[0.06]"
                  }`}
                >
                  <p className="font-display text-4xl sm:text-5xl tracking-tight tabular-nums">{m.k}</p>
                  <p
                    className={`text-[12px] font-mono tracking-wider uppercase mt-1 ${
                      isDark ? "text-white/40" : "text-black/40"
                    }`}
                  >
                    {m.v}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </FadeUp>
      </div>
    </section>
  );
}

export function ProductsSection() {
  const { isDark } = useScribeTheme();
  const items = [
    {
      p: PRODUCTS.vdr,
      tagline: "AI-native data room",
      headline: "Every document, indexed the moment it arrives.",
      copy: "Upload contracts, financials, transcripts — CogniVault builds a citation-backed knowledge layer that auto-fills request lists, answers questions, and watches buyer-side engagement in real time.",
      features: [
        "Auto-matched diligence responses",
        "Grounded chat with page citations",
        "Granular permissions & watermarks",
        "Real-time engagement analytics",
      ],
      accentRgb: "16 185 129",
      cta: "Tour CogniVault",
    },
    {
      p: PRODUCTS.mic,
      tagline: "Meeting intelligence",
      headline: "A conversational memory that never forgets.",
      copy: "CogniScribe joins every call, diarizes speakers, extracts metrics and risks, and stitches the transcript back into your workspace so every word said is searchable — forever.",
      features: [
        "Auto-joins Zoom, Meet, and Teams",
        "Speaker diarization + timestamps",
        "Metrics, risks, and actions extracted",
        "Org-wide RAG across transcripts",
      ],
      accentRgb: "245 158 11",
      cta: "Tour CogniScribe",
    },
  ];

  return (
    <section id="products" className={`${isDark ? "bg-[#0e0e0e] text-white" : "bg-white text-black"} py-28 px-6`}>
      <div className="max-w-6xl mx-auto">
        <FadeUp className="mb-14 max-w-3xl">
          <Eyebrow className="mb-4">The suite</Eyebrow>
          <h2 className="text-[38px] sm:text-[54px] leading-[1.02] tracking-[-0.02em] font-medium">
            Two products.
            <br />
            <span
              className="font-display italic font-normal"
              style={{ color: isDark ? "rgba(255,255,255,0.45)" : "rgba(0,0,0,0.35)" }}
            >
              One shared memory.
            </span>
          </h2>
          <p className={`text-[15px] leading-relaxed mt-5 max-w-lg ${isDark ? "text-white/55" : "text-black/55"}`}>
            Built to work together, priced to work independently. Start with one — or both — and the platform grows
            with the engagement.
          </p>
        </FadeUp>

        <div className="grid md:grid-cols-2 gap-5">
          {items.map((it, idx) => {
            const Pi = it.p.icon;
            const tone = isDark ? "dark" : "light";
            return (
              <FadeUp key={it.p.key} delay={idx * 80}>
                <Link href={it.p.href} className="group block">
                  <div
                    className={`relative rounded-2xl border overflow-hidden h-full transition-all hover:-translate-y-0.5 ${
                      isDark
                        ? "bg-[#121212] border-white/10 hover:border-white/15"
                        : "bg-[#fafafa] border-black/[0.06] hover:border-black/15"
                    } shadow-sm hover:shadow-2xl`}
                  >
                    <div
                      className="absolute -top-24 -right-24 w-64 h-64 rounded-full blur-3xl pointer-events-none opacity-40 transition-opacity group-hover:opacity-70"
                      style={{
                        background: `radial-gradient(circle, rgba(${it.accentRgb}, 0.35), transparent 70%)`,
                      }}
                    ></div>

                    <div className="relative p-7 sm:p-9">
                      <div className="flex items-start justify-between mb-6">
                        <div
                          className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-[11px] font-medium ${it.p.bg[tone]} ${it.p.text[tone]} border ${it.p.border[tone]}`}
                        >
                          <Pi size={11} />
                          <span className="font-mono tracking-wider uppercase">{it.p.name}</span>
                        </div>
                        <span
                          className={`text-[11px] font-mono uppercase tracking-wider ${
                            isDark ? "text-white/35" : "text-black/35"
                          }`}
                        >
                          {it.tagline}
                        </span>
                      </div>

                      <h3 className="text-[28px] sm:text-[34px] leading-[1.08] tracking-[-0.02em] font-medium mb-4">
                        {it.headline}
                      </h3>
                      <p
                        className={`text-[14px] leading-relaxed mb-6 ${
                          isDark ? "text-white/55" : "text-black/60"
                        }`}
                      >
                        {it.copy}
                      </p>

                      <ul className="flex flex-col gap-2.5 mb-8">
                        {it.features.map((f) => (
                          <li key={f} className="flex items-start gap-2.5">
                            <I.Check size={13} className="shrink-0 mt-0.5" />
                            <span className={`text-[13px] ${isDark ? "text-white/65" : "text-black/65"}`}>{f}</span>
                          </li>
                        ))}
                      </ul>

                      <span
                        className={`inline-flex items-center gap-1.5 text-[13px] font-medium ${
                          isDark ? "text-white/90" : "text-black/85"
                        }`}
                      >
                        {it.cta}
                        <I.Arrow size={13} className="transition-transform group-hover:translate-x-1" />
                      </span>
                    </div>
                  </div>
                </Link>
              </FadeUp>
            );
          })}
        </div>
      </div>
    </section>
  );
}

export function SecuritySection() {
  const { isDark } = useScribeTheme();
  const layers = [
    { l: "Platform", d: "SSO, SCIM, IP allow-lists, encryption in transit & at rest" },
    { l: "Engagement", d: "Role-based permissions per deal, matter, or engagement" },
    { l: "Object", d: "Document, clause & recording-level visibility controls" },
  ];
  return (
    <section
      id="security"
      className={`${isDark ? "bg-[#0a0a0a] text-white" : "bg-[#fafafa] text-black"} py-28 px-6`}
    >
      <div className="max-w-6xl mx-auto grid md:grid-cols-2 gap-16 items-center">
        <FadeUp>
          <Eyebrow className="mb-4">Security architecture</Eyebrow>
          <h2 className="text-[38px] sm:text-[54px] leading-[1.02] tracking-[-0.02em] font-medium mb-6">
            Built for people
            <br />
            <span
              className="font-display italic font-normal"
              style={{ color: isDark ? "rgba(255,255,255,0.4)" : "rgba(0,0,0,0.35)" }}
            >
              who can&apos;t afford leaks.
            </span>
          </h2>
          <p className={`text-[15px] leading-relaxed mb-8 ${isDark ? "text-white/55" : "text-black/60"}`}>
            Every AI action requires human approval. Visibility is enforced at the data layer — never UI-only. Complete
            party-to-party and matter-to-matter isolation, with immutable audit logs suitable for regulators.
          </p>
          <ul className="flex flex-col gap-3">
            {[
              "AI never auto-shares — every action requires approval",
              "Data-layer visibility enforcement, never UI-only",
              "Complete party-to-party and matter-to-matter isolation",
              "Immutable, append-only audit logs",
              "Customer-managed encryption keys available on Enterprise",
              "SOC 2 Type II, ISO 27001, GDPR, CCPA",
            ].map((x) => (
              <li key={x} className="flex items-start gap-3">
                <I.Check
                  size={14}
                  className={isDark ? "text-white/50 shrink-0 mt-0.5" : "text-black/40 shrink-0 mt-0.5"}
                />
                <span className={`text-[14px] ${isDark ? "text-white/65" : "text-black/65"}`}>{x}</span>
              </li>
            ))}
          </ul>
        </FadeUp>

        <FadeUp delay={100} className="flex flex-col gap-3">
          {layers.map((layer, i) => (
            <div
              key={layer.l}
              className={`rounded-xl border p-5 ${
                isDark ? "bg-[#121212] border-white/10" : "bg-white border-black/[0.06]"
              } ${i === 0 ? "" : i === 1 ? "md:ml-6" : "md:ml-12"}`}
            >
              <p
                className={`text-[10px] font-mono tracking-wider uppercase mb-1 ${
                  isDark ? "text-white/30" : "text-black/30"
                }`}
              >
                Layer {i + 1}
              </p>
              <p className={`text-[16px] font-medium ${isDark ? "text-white/90" : "text-black/90"}`}>{layer.l}</p>
              <p className={`text-[13px] mt-1 ${isDark ? "text-white/45" : "text-black/50"}`}>{layer.d}</p>
            </div>
          ))}
          <div
            className={`rounded-xl border p-5 flex items-center gap-4 md:ml-12 ${
              isDark ? "bg-white/[0.02] border-white/10" : "bg-white border-black/[0.06]"
            }`}
          >
            <div
              className={`h-10 w-10 rounded-lg flex items-center justify-center ${
                isDark ? "bg-white/5" : "bg-black/[0.05]"
              }`}
            >
              <I.Lock size={16} className={isDark ? "text-white/60" : "text-black/60"} />
            </div>
            <div>
              <p
                className={`text-[12px] font-mono tracking-wider uppercase ${
                  isDark ? "text-white/50" : "text-black/50"
                }`}
              >
                SOC 2 · ISO 27001 · GDPR
              </p>
              <p className={`text-[11px] mt-0.5 ${isDark ? "text-white/35" : "text-black/40"}`}>
                Audited &amp; certified — reports available on request.
              </p>
            </div>
          </div>
        </FadeUp>
      </div>
    </section>
  );
}

export function LandingCTA() {
  const { isDark } = useScribeTheme();
  return (
    <section
      id="get-started"
      className={`${
        isDark ? "bg-[#0e0e0e] text-white" : "bg-white text-black"
      } py-32 px-6 relative overflow-hidden`}
    >
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: `radial-gradient(ellipse 60% 80% at 50% 100%, rgba(${EMERALD}, ${
            isDark ? 0.15 : 0.1
          }), transparent 60%)`,
        }}
      ></div>
      <FadeUp className="relative max-w-3xl mx-auto text-center">
        <h2 className="text-[44px] sm:text-[64px] leading-[0.98] tracking-[-0.03em] font-medium mb-6">
          Ready to ship
          <br />
          <span
            className="font-display italic font-normal"
            style={{ color: isDark ? "rgba(255,255,255,0.4)" : "rgba(0,0,0,0.35)" }}
          >
            the next engagement?
          </span>
        </h2>
        <p
          className={`text-[16px] leading-relaxed mb-10 max-w-lg mx-auto ${
            isDark ? "text-white/55" : "text-black/55"
          }`}
        >
          Start a 14-day trial. No credit card. Spin up a live deal, matter, or engagement — bring your team and see
          the difference on the first request list.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link
            href="/login?mode=signup"
            className={`inline-flex items-center gap-2 h-12 px-7 rounded-full text-[14px] font-medium whitespace-nowrap ${
              isDark ? "bg-white text-[#0a0a0a] hover:bg-white/90" : "bg-[#0a0a0a] text-white hover:bg-black/90"
            }`}
          >
            Get started free <I.Arrow size={14} />
          </Link>
          <a
            href="#talk"
            className={`inline-flex items-center gap-2 h-12 px-7 rounded-full text-[14px] font-medium whitespace-nowrap border ${
              isDark
                ? "border-white/15 text-white/80 hover:bg-white/5"
                : "border-black/15 text-black/75 hover:bg-black/[0.04]"
            }`}
          >
            Talk to a specialist
          </a>
        </div>
      </FadeUp>
    </section>
  );
}
