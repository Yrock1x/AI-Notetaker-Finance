"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, Check } from "lucide-react";
import { useOrg } from "@/hooks/use-org";

export function OrgSwitcher() {
  const { currentOrg, orgs, switchOrg } = useOrg();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  const hasMultiple = orgs.length > 1;

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => hasMultiple && setOpen((o) => !o)}
        className="flex items-center gap-2 text-sm font-medium text-[#1A1A1A]/70 hover:text-[#1A1A1A] transition-colors disabled:cursor-default"
        disabled={!hasMultiple}
      >
        <div className="h-2 w-2 rounded-full bg-emerald-500" />
        <span>{currentOrg?.name ?? "No Organization"}</span>
        {hasMultiple && <ChevronDown className="h-3.5 w-3.5 opacity-50" />}
      </button>

      {open && hasMultiple && (
        <div className="absolute left-0 top-full mt-2 min-w-[220px] rounded-lg border border-[#1A1A1A]/10 bg-white shadow-lg z-50 py-1">
          {orgs.map((org) => {
            const isActive = org.id === currentOrg?.id;
            return (
              <button
                key={org.id}
                type="button"
                onClick={() => {
                  switchOrg(org.id);
                  setOpen(false);
                }}
                className="w-full flex items-center justify-between gap-2 px-3 py-2 text-sm text-left hover:bg-[#F2F0E9]/50 transition-colors"
              >
                <span className={isActive ? "font-medium" : ""}>{org.name}</span>
                {isActive && <Check className="h-3.5 w-3.5 text-emerald-500" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
