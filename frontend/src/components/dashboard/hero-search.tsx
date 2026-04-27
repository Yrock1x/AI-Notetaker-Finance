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
    <section
      className={`rounded-2xl border p-6 sm:p-8 ${
        isDark
          ? "bg-[#121212] border-white/10"
          : "bg-white border-black/[0.06]"
      }`}
    >
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="flex items-center gap-2">
          <Sparkles className={`h-4 w-4 ${isDark ? "text-white/60" : "text-black/60"}`} />
          <span className={`text-[11px] font-medium tracking-[0.18em] uppercase ${isDark ? "text-white/45" : "text-black/45"}`}>
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
            className={`inline-flex items-center gap-1.5 h-10 px-4 rounded-full text-[13px] font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
              isDark
                ? "bg-white text-[#0a0a0a] hover:bg-white/90"
                : "bg-[#0a0a0a] text-white hover:bg-black/90"
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
                  ? "border-white/10 text-white/55 hover:text-white hover:border-white/25"
                  : "border-black/10 text-black/55 hover:text-black hover:border-black/25"
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </form>
    </section>
  );
}
