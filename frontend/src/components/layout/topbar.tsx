"use client";

import { OrgSwitcher } from "./org-switcher";
import { Breadcrumbs } from "./breadcrumbs";

export function Topbar() {
  return (
    <header className="flex h-24 items-center justify-between border-b border-[#1A1A1A]/5 px-10 bg-[#F2F0E9]/80 backdrop-blur-xl relative z-20 antialiased">
      <div className="flex items-center gap-6">
        <Breadcrumbs />
      </div>
      <div className="flex items-center gap-6">
        <div className="hidden md:flex items-center gap-2 px-4 py-2 bg-white/50 rounded-full border border-[#1A1A1A]/5 shadow-sm">
          <OrgSwitcher />
        </div>
        <div className="magnetic-btn group flex h-12 w-12 items-center justify-center rounded-full bg-primary text-white text-sm font-heading font-extrabold shadow-lg overflow-hidden relative cursor-pointer">
          <span className="relative z-10 transition-transform group-hover:scale-110">U</span>
          <div className="absolute inset-0 bg-accent translate-y-full group-hover:translate-y-0 transition-transform duration-300"></div>
        </div>
      </div>
    </header>
  );
}
