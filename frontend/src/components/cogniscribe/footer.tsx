"use client";

import Link from "next/link";
import { Eyebrow } from "./primitives";
import { useScribeTheme } from "./theme-provider";

const cols = [
  {
    t: "Products",
    items: [
      { n: "CogniVault", h: "/cognivault" },
      { n: "CogniScribe", h: "/cogniscribe" },
      { n: "Platform", h: "/" },
      { n: "Integrations", h: "#" },
    ],
  },
  {
    t: "For",
    items: [
      { n: "Finance", h: "/#features" },
      { n: "Legal", h: "/#features" },
      { n: "Advisory", h: "/#features" },
      { n: "Professional services", h: "/#features" },
    ],
  },
  {
    t: "Resources",
    items: [
      { n: "Changelog", h: "#" },
      { n: "Security", h: "/#protocol" },
      { n: "Status", h: "#" },
      { n: "Docs", h: "#" },
    ],
  },
  {
    t: "Legal",
    items: [
      { n: "Privacy", h: "#" },
      { n: "Terms", h: "#" },
      { n: "DPA", h: "#" },
      { n: "SOC 2", h: "#" },
    ],
  },
];

export function ScribeFooter() {
  const { isDark } = useScribeTheme();
  return (
    <footer
      className={`${
        isDark ? "bg-[#0a0a0a] text-white border-white/5" : "bg-white text-black border-black/[0.06]"
      } border-t`}
    >
      <div className="max-w-6xl mx-auto px-6 py-20">
        <div className="grid md:grid-cols-6 gap-12">
          <div className="md:col-span-2">
            <div className="flex items-center gap-2 mb-5">
              <div
                className={`w-7 h-7 rounded-md ${
                  isDark ? "bg-white text-black" : "bg-black text-white"
                } flex items-center justify-center`}
              >
                <span className="font-display italic text-base leading-none translate-y-px">C</span>
              </div>
              <span className="text-[16px] font-medium tracking-tight">CogniSuite.ai</span>
            </div>
            <p
              className={`text-[13px] leading-relaxed max-w-xs ${
                isDark ? "text-white/40" : "text-black/45"
              }`}
            >
              AI-native workspace for professional services. Data room plus meeting intelligence — built for finance,
              legal, and advisory teams.
            </p>
          </div>
          {cols.map((c) => (
            <div key={c.t}>
              <Eyebrow className="mb-4">{c.t}</Eyebrow>
              <ul className="flex flex-col gap-2.5">
                {c.items.map((i) => (
                  <li key={i.n}>
                    <Link
                      href={i.h}
                      className={`text-[13px] ${
                        isDark ? "text-white/50 hover:text-white/80" : "text-black/55 hover:text-black/85"
                      }`}
                    >
                      {i.n}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div
          className={`mt-16 pt-8 border-t flex flex-col sm:flex-row items-center justify-between gap-4 ${
            isDark ? "border-white/5" : "border-black/[0.06]"
          }`}
        >
          <p className={`text-[11px] font-mono ${isDark ? "text-white/25" : "text-black/30"}`}>
            © 2026 CogniSuite, Inc. All rights reserved.
          </p>
          <p className={`text-[11px] font-mono ${isDark ? "text-white/25" : "text-black/30"}`}>
            <span className="inline-flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 breathe"></span>
              All systems operational
            </span>
          </p>
        </div>
      </div>
    </footer>
  );
}
