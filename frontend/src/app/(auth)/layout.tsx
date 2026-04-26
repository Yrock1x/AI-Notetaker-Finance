"use client";

import Link from "next/link";
import { useScribeTheme } from "@/components/cogniscribe/theme-provider";
import { ThemeToggle } from "@/components/cogniscribe/theme-toggle";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  const { isDark } = useScribeTheme();
  return (
    <div
      className={`relative flex min-h-screen items-center justify-center overflow-hidden px-6 ${
        isDark ? "bg-[#0a0a0a] text-white" : "bg-[#fafafa] text-[#0a0a0a]"
      }`}
    >
      <div
        className="absolute inset-0 pointer-events-none drift"
        style={{
          background: `radial-gradient(ellipse 70% 50% at 50% 0%, rgba(16,185,129,${
            isDark ? 0.12 : 0.08
          }), transparent 60%)`,
        }}
      ></div>
      <div className={`absolute inset-0 noise ${isDark ? "opacity-[0.04]" : "opacity-[0.03]"} pointer-events-none`}></div>

      <div className="absolute top-6 left-6 right-6 flex items-center justify-between z-20">
        <Link href="/" className="flex items-center gap-2">
          <div
            className={`w-6 h-6 rounded-md flex items-center justify-center ${
              isDark ? "bg-white text-black" : "bg-black text-white"
            }`}
          >
            <span className="font-display italic text-sm leading-none translate-y-px">C</span>
          </div>
          <span className="text-[14px] font-medium tracking-tight">
            CogniSuite<span className={isDark ? "text-white/40" : "text-black/40"}>.ai</span>
          </span>
        </Link>
        <ThemeToggle />
      </div>

      <div
        className={`relative z-10 w-full max-w-md rounded-2xl border p-8 md:p-10 shadow-2xl ${
          isDark ? "bg-[#121212] border-white/10" : "bg-white border-black/[0.06]"
        }`}
      >
        {children}
      </div>
    </div>
  );
}
