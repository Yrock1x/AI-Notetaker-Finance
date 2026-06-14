import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/**/*.{ts,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        muted: {
          DEFAULT: "var(--muted)",
          foreground: "var(--muted-foreground)",
        },
        primary: {
          DEFAULT: "var(--primary)",
          foreground: "var(--primary-foreground)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          foreground: "var(--accent-foreground)",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
        },
        // Near-black "ink" used across the authed app. Single source of truth
        // for what were ~130 scattered `[#1A1A1A]` arbitrary values; opacity
        // modifiers (text-ink/85, border-ink/5, …) work as before.
        ink: "#1A1A1A",
        border: "var(--border)",
        ring: "var(--ring)",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 8px)",
        sm: "calc(var(--radius) - 16px)",
      },
      fontFamily: {
        sans: ['"Inter Tight"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        serif: ['"Instrument Serif"', 'ui-serif', 'Georgia', 'serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
        heading: ['"Inter Tight"', 'ui-sans-serif', 'system-ui'],
        subheading: ['"Inter Tight"', 'ui-sans-serif', 'system-ui'],
        drama: ['"Instrument Serif"', 'ui-serif', 'Georgia'],
        data: ['"JetBrains Mono"', 'ui-monospace'],
        display: ['"Instrument Serif"', 'ui-serif', 'Georgia'],
      },
    },
  },
  plugins: [],
};

export default config;
