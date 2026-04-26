"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type ThemeMode = "dark" | "light";

type ThemeContextValue = {
  theme: ThemeMode;
  setTheme: (t: ThemeMode) => void;
  isDark: boolean;
  aiDemosPlaying: boolean;
  setAiDemosPlaying: (v: boolean | ((p: boolean) => boolean)) => void;
};

const ThemeCtx = createContext<ThemeContextValue | null>(null);
const STORAGE_KEY = "cogni-theme";

export function useScribeTheme() {
  const ctx = useContext(ThemeCtx);
  if (!ctx) throw new Error("useScribeTheme must be used inside ScribeThemeProvider");
  return ctx;
}

export function ScribeThemeProvider({
  children,
  initialTheme = "dark",
}: {
  children: ReactNode;
  initialTheme?: ThemeMode;
}) {
  const [theme, setThemeState] = useState<ThemeMode>(initialTheme);
  const [aiDemosPlaying, setAiDemosPlayingState] = useState(true);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved === "dark" || saved === "light") setThemeState(saved);
    } catch {}
    setHydrated(true);
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") root.classList.add("dark");
    else root.classList.remove("dark");
    document.body.style.backgroundColor = theme === "dark" ? "#0a0a0a" : "#fafafa";
    document.body.style.color = theme === "dark" ? "#ffffff" : "#0a0a0a";
    if (hydrated) {
      try {
        window.localStorage.setItem(STORAGE_KEY, theme);
      } catch {}
    }
  }, [theme, hydrated]);

  const setTheme = (t: ThemeMode) => setThemeState(t);
  const setAiDemosPlaying: ThemeContextValue["setAiDemosPlaying"] = (v) =>
    setAiDemosPlayingState((prev) => (typeof v === "function" ? v(prev) : v));

  return (
    <ThemeCtx.Provider
      value={{
        theme,
        setTheme,
        isDark: theme === "dark",
        aiDemosPlaying,
        setAiDemosPlaying,
      }}
    >
      {children}
    </ThemeCtx.Provider>
  );
}
