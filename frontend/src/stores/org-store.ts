import { create } from "zustand";
import type { Organization } from "@/types";

interface OrgState {
  currentOrg: Organization | null;
  orgs: Organization[];
  setCurrentOrg: (org: Organization) => void;
  setOrgs: (orgs: Organization[]) => void;
}

export const useOrgStore = create<OrgState>((set) => ({
  currentOrg: null,
  orgs: [],

  setCurrentOrg: (org: Organization) => {
    set({ currentOrg: org });
  },

  setOrgs: (orgs: Organization[]) => {
    set({ orgs });
  },
}));
