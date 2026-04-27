"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Sparkles, ArrowRight } from "lucide-react";
import { useScribeTheme } from "@/components/cogniscribe/theme-provider";

const PROMPTS = [
  "What action items came up this week?",
  "Summarize my last management presentation",
  "Which deals haven't had a touch in 14 days?",
];

export function HeroSearch() {
  const router = useRouter();
  const { isDark } = useScribeTheme();
  const [value, setValue] = useState("");

  function submit(e: FormEvent) {
    e.preventDefault();
    const q = value.trim();
    if (!q) return;
    router.push(`/chat?q=${encodeURIComponent(q)}`);
  }

  function fillPrompt(p: string) {
    setValue(p);
    router.push(`/chat?q=${encodeURIComponent(p)}`);
  }

  return (
    <section className="relative">
      {/* Gradient glow halo behind the card */}
      <div
        aria-hidden
        className={`pointer-events-none absolute -inset-px rounded-[20px] opacity-60 blur-xl ${
          isDark
            ? "bg-gradient-to-r from-indigo-500/20 via-violet-500/15 to-emerald-500/20"
            : "bg-gradient-to-r from-indigo-300/40 via-violet-200/30 to-emerald-300/40"
        }`}
      />
      <div
        className={`relative rounded-2xl border p-6 sm:p-8 overflow-hidden ${
          isDark
            ? "bg-gradient-to-br from-[#161425] via-[#121212] to-[#10181a] border-white/10"
            : "bg-gradient-to-br from-indigo-50/60 via-white to-emerald-50/60 border-black/[0.06]"
        }`}
      >
        {/* Subtle radial accent */}
        <div
          aria-hidden
          className={`pointer-events-none absolute -top-20 -right-20 h-56 w-56 rounded-full blur-3xl ${
            isDark ? "bg-indigo-500/10" : "bg-indigo-300/30"
          }`}
        />
        <div
          aria-hidden
          className={`pointer-events-none absolute -bottom-24 -left-16 h-48 w-48 rounded-full blur-3xl ${
            isDark ? "bg-emerald-500/10" : "bg-emerald-300/25"
          }`}
        />

        <form onSubmit={submit} className="relative flex flex-col gap-4">
          <div className="flex items-center gap-2">
            <span
              className={`inline-flex h-6 w-6 items-center justify-center rounded-md ${
                isDark
                  ? "bg-indigo-500/20 text-indigo-300"
                  : "bg-indigo-100 text-indigo-600"
              }`}
            >
              <Sparkles className="h-3.5 w-3.5" />
            </span>
            <span
              className={`text-[11px] font-medium tracking-[0.18em] uppercase ${
                isDark ? "text-white/55" : "text-black/55"
              }`}
            >
              Ask across all your deals
            </span>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="Ask anything — action items, summaries, comparisons across calls…"
              className={`flex-1 bg-transparent text-base sm:text-lg outline-none placeholder:font-light ${
                isDark
                  ? "text-white placeholder:text-white/30"
                  : "text-black placeholder:text-black/30"
              }`}
            />
            <button
              type="submit"
              disabled={!value.trim()}
              className={`inline-flex items-center gap-1.5 h-10 px-5 rounded-full text-[13px] font-medium shadow-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed ${
                isDark
                  ? "bg-gradient-to-r from-indigo-500 to-violet-500 text-white hover:from-indigo-400 hover:to-violet-400 hover:shadow-indigo-500/30 hover:shadow-lg"
                  : "bg-gradient-to-r from-indigo-600 to-violet-600 text-white hover:from-indigo-500 hover:to-violet-500 hover:shadow-indigo-500/40 hover:shadow-lg"
              }`}
            >
              Ask
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
          <div className="flex flex-wrap gap-2 pt-1">
            {PROMPTS.map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => fillPrompt(p)}
                className={`text-[11.5px] px-3 py-1.5 rounded-full border transition-colors ${
                  isDark
                    ? "border-white/10 bg-white/[0.02] text-white/65 hover:text-white hover:border-indigo-400/40 hover:bg-indigo-500/10"
                    : "border-black/10 bg-white/60 text-black/65 hover:text-indigo-700 hover:border-indigo-300 hover:bg-indigo-50"
                }`}
              >
                {p}
              </button>
            ))}
          </div>
        </form>
      </div>
    </section>
  );
}
