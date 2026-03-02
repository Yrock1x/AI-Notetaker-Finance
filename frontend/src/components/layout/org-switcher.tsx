"use client";

import { useOrg } from "@/hooks/use-org";
import { ChevronDown } from "lucide-react";

export function OrgSwitcher() {
  const { currentOrg } = useOrg();

  return (
    <button
      type="button"
      className="flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-muted"
    >
      <span>{currentOrg?.name ?? "Select Organization"}</span>
      <ChevronDown className="h-3 w-3" />
    </button>
  );
}
