"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useScrolled } from "./primitives";
import { useScribeTheme } from "./theme-provider";
import { I } from "./icons";
import { PRODUCTS, type ProductKey } from "./products";

export function ScribeNav({ currentProduct }: { currentProduct?: ProductKey }) {
  const { isDark, theme, setTheme } = useScribeTheme();
  const scrolled = useScrolled(30);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [productsOpen, setProductsOpen] = useState(false);
  const ddRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (ddRef.current && !ddRef.current.contains(e.target as Node)) setProductsOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const navBg = scrolled
    ? isDark
      ? "bg-[#0a0a0a]/85 backdrop-blur-xl border-b border-white/5"
      : "bg-[#fafafa]/80 backdrop-blur-xl border-b border-black/[0.06]"
    : "bg-transparent border-b border-transparent";

  const linkCls = isDark ? "text-white/50 hover:text-white" : "text-black/55 hover:text-black";

  return (
    <header className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${navBg}`}>
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link href="/" className={`flex items-center gap-2 ${isDark ? "text-white" : "text-black"}`}>
          <div
            className={`w-6 h-6 rounded-md ${
              isDark ? "bg-white text-black" : "bg-black text-white"
            } flex items-center justify-center`}
          >
            <span className="font-display italic text-sm leading-none translate-y-px">C</span>
          </div>
          <span className="text-[15px] font-medium tracking-tight">
            CogniSuite<span className={isDark ? "text-white/40" : "text-black/40"}>.ai</span>
          </span>
        </Link>

        <nav className="hidden md:flex items-center gap-8">
          <div ref={ddRef} className="relative">
            <button
              onClick={() => setProductsOpen((v) => !v)}
              className={`flex items-center gap-1 text-[13px] ${linkCls} transition-colors ${
                currentProduct ? (isDark ? "!text-white" : "!text-black") : ""
              }`}
            >
              Products{" "}
              <I.ChevDown size={12} className={`transition-transform ${productsOpen ? "rotate-180" : ""}`} />
            </button>
            {productsOpen && (
              <div
                className={`absolute top-full left-1/2 -translate-x-1/2 mt-3 w-80 rounded-xl border p-2 shadow-2xl ${
                  isDark
                    ? "border-white/10 bg-[#0a0a0a]/95 backdrop-blur-xl"
                    : "border-black/[0.08] bg-white/95 backdrop-blur-xl"
                }`}
              >
                {Object.values(PRODUCTS).map((p) => {
                  const Pi = p.icon;
                  const isActive = currentProduct === p.key;
                  return (
                    <Link
                      key={p.key}
                      href={p.href}
                      onClick={() => setProductsOpen(false)}
                      className={`flex items-start gap-3 rounded-lg p-3 transition-colors ${
                        isActive
                          ? isDark
                            ? "bg-white/[0.04]"
                            : "bg-black/[0.04]"
                          : isDark
                          ? "hover:bg-white/5"
                          : "hover:bg-black/[0.04]"
                      }`}
                    >
                      <div
                        className={`flex h-9 w-9 items-center justify-center rounded-lg shrink-0 mt-0.5 ${
                          p.bg[isDark ? "dark" : "light"]
                        }`}
                      >
                        <Pi size={14} className={p.text[isDark ? "dark" : "light"]} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className={`text-[13px] font-medium ${isDark ? "text-white/90" : "text-black/85"}`}>
                            {p.name}
                          </p>
                          {isActive && (
                            <span
                              className={`text-[9px] font-mono tracking-wider uppercase ${
                                isDark ? "text-white/40" : "text-black/40"
                              }`}
                            >
                              Current
                            </span>
                          )}
                        </div>
                        <p className={`text-[11px] mt-0.5 ${isDark ? "text-white/40" : "text-black/45"}`}>
                          {p.tagline}
                        </p>
                      </div>
                      <I.Arrow size={12} className={`mt-2 ${isDark ? "text-white/25" : "text-black/25"}`} />
                    </Link>
                  );
                })}
                <div className={`mx-2 my-2 border-t ${isDark ? "border-white/5" : "border-black/[0.06]"}`}></div>
                <Link
                  href="/"
                  className={`block px-3 py-2 text-[11px] font-mono tracking-wider uppercase ${
                    isDark ? "text-white/35 hover:text-white/70" : "text-black/35 hover:text-black/70"
                  }`}
                >
                  ← Back to overview
                </Link>
              </div>
            )}
          </div>
          <Link href="/#industries" className={`text-[13px] ${linkCls}`}>
            For
          </Link>
          <Link href="/#security" className={`text-[13px] ${linkCls}`}>
            Security
          </Link>
          <Link href="/#get-started" className={`text-[13px] ${linkCls}`}>
            Pricing
          </Link>
        </nav>

        <div className="hidden md:flex items-center gap-2">
          <button
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            className={`h-9 w-9 rounded-full flex items-center justify-center ${
              isDark ? "text-white/60 hover:bg-white/5" : "text-black/60 hover:bg-black/[0.04]"
            }`}
            aria-label="Toggle theme"
          >
            {isDark ? <I.Sun size={14} /> : <I.Moon size={14} />}
          </button>
          <Link href="/login" className={`text-[13px] px-3 py-1.5 ${linkCls}`}>
            Sign in
          </Link>
          <a
            href="#get-started"
            className={`inline-flex items-center gap-1.5 text-[13px] h-9 px-4 rounded-full font-medium ${
              isDark ? "bg-white text-[#0a0a0a] hover:bg-white/90" : "bg-[#0a0a0a] text-white hover:bg-black/90"
            }`}
          >
            Get started <I.Arrow size={13} />
          </a>
        </div>

        <button
          onClick={() => setMobileOpen((v) => !v)}
          className={`md:hidden ${isDark ? "text-white/70" : "text-black/70"}`}
          aria-label="Toggle menu"
        >
          {mobileOpen ? <I.X size={20} /> : <I.Menu size={20} />}
        </button>
      </div>

      {mobileOpen && (
        <div
          className={`md:hidden border-t px-6 py-5 flex flex-col gap-2 ${
            isDark
              ? "bg-[#0a0a0a]/95 backdrop-blur-xl border-white/5"
              : "bg-white/95 backdrop-blur-xl border-black/[0.06]"
          }`}
        >
          {Object.values(PRODUCTS).map((p) => {
            const Pi = p.icon;
            return (
              <Link
                key={p.key}
                href={p.href}
                onClick={() => setMobileOpen(false)}
                className={`flex items-center gap-3 rounded-lg p-2.5 ${
                  isDark ? "hover:bg-white/5" : "hover:bg-black/[0.04]"
                }`}
              >
                <Pi size={14} className={isDark ? "text-white/45" : "text-black/45"} />
                <span className={`text-[13px] ${isDark ? "text-white/75" : "text-black/75"}`}>{p.name}</span>
              </Link>
            );
          })}
          <div className={`pt-3 mt-3 border-t ${isDark ? "border-white/5" : "border-black/5"} flex flex-col gap-2`}>
            <Link href="/" className={`text-[13px] px-3 py-2 ${linkCls}`}>
              Home
            </Link>
            <Link href="/login" className={`text-[13px] px-3 py-2 ${linkCls}`}>
              Sign in
            </Link>
            <a
              href="#get-started"
              className={`text-[13px] px-4 py-2.5 rounded-full text-center font-medium ${
                isDark ? "bg-white text-[#0a0a0a]" : "bg-[#0a0a0a] text-white"
              }`}
            >
              Get started
            </a>
          </div>
        </div>
      )}
    </header>
  );
}
