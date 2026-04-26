"use client";

import { useScribeTheme } from "./theme-provider";
import { I } from "./icons";

export function ThemeToggle({ className = "" }: { className?: string }) {
  const { theme, setTheme, isDark } = useScribeTheme();
  return (
    <button
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      aria-label="Toggle theme"
      className={`h-9 w-9 rounded-full flex items-center justify-center transition-colors ${
        isDark ? "text-white/60 hover:bg-white/5 hover:text-white" : "text-black/60 hover:bg-black/[0.04] hover:text-black"
      } ${className}`}
    >
      {isDark ? <I.Sun size={14} /> : <I.Moon size={14} />}
    </button>
  );
}
