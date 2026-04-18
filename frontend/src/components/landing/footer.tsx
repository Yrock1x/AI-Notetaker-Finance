"use client";

import Link from "next/link";

export const Footer = () => (
  <footer className="bg-[#1A1A1A] pt-24 pb-12 px-8 md:px-16 rounded-t-[4rem] text-[#F2F0E9] font-subheading relative z-40">
    <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-4 gap-16 mb-24">
      <div className="md:col-span-2">
        <div className="font-heading text-3xl font-bold mb-6 tracking-tight text-white">Deal Companion</div>
        <p className="text-white/50 max-w-md mb-10 text-lg leading-relaxed">
          The ultimate digital instrument for investment banking, private equity, and venture capital.
        </p>
        <div className="flex items-center gap-3 bg-white/5 inline-flex px-5 py-2.5 rounded-full border border-white/10 shadow-inner">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-[pulse_2s_infinite]"></div>
          <span className="font-data text-xs uppercase tracking-[0.2em] text-white/70 font-medium">System Operational</span>
        </div>
      </div>
      <div>
        <div className="font-data text-xs uppercase tracking-widest mb-8 opacity-40">Platform</div>
        <ul className="space-y-4 text-sm text-white/70 font-medium">
          <li><a href="#features" className="hover:text-white transition-colors">Features</a></li>
          <li><a href="#protocol" className="hover:text-white transition-colors">How It Works</a></li>
          <li><Link href="/login" className="hover:text-white transition-colors">Get Started</Link></li>
        </ul>
      </div>
      <div>
        <div className="font-data text-xs uppercase tracking-widest mb-8 opacity-40">Company</div>
        <ul className="space-y-4 text-sm text-white/70 font-medium">
          <li><a href="#philosophy" className="hover:text-white transition-colors">Philosophy</a></li>
          <li><a href="mailto:support@dealcompanion.ai" className="hover:text-white transition-colors">Contact</a></li>
        </ul>
      </div>
    </div>
    <div className="max-w-7xl mx-auto border-t border-white/10 pt-8 flex flex-col md:flex-row justify-between items-center text-xs text-white/30 font-data tracking-wider gap-4">
      <div>&copy; 2026 DEAL COMPANION.</div>
      <div>GENERATION 01.</div>
    </div>
  </footer>
);
