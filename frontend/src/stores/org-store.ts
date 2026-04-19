"use client";

import { create } from "zustand";

// Stores only the user's selection (which org they picked in the switcher).
// The actual org list + objects live in React Query (see useOrgs).

const STORAGE_KEY = "org_id";

function readInitial(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(STORAGE_KEY);
}

interface OrgSelectionState {
  currentOrgId: string | null;
  setCurrentOrgId: (id: string | null) => void;
}

export const useOrgSelection = create<OrgSelectionState>((set) => ({
  currentOrgId: readInitial(),
  setCurrentOrgId: (id) => {
    if (typeof window !== "undefined") {
      if (id) localStorage.setItem(STORAGE_KEY, id);
      else localStorage.removeItem(STORAGE_KEY);
    }
    set({ currentOrgId: id });
  },
}));
