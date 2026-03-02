import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/**/*.{ts,tsx}",
  ],
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
        border: "var(--border)",
        ring: "var(--ring)",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 8px)",
        sm: "calc(var(--radius) - 16px)",
      },
      fontFamily: {
        heading: ['Plus Jakarta Sans', 'sans-serif'],
        subheading: ['Outfit', 'sans-serif'],
        drama: ['Cormorant Garamond', 'serif'],
        data: ['IBM Plex Mono', 'monospace'],
      },
    },
  },
  plugins: [],
};

export default config;
