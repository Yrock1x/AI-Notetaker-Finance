import { create } from "zustand";
import type { Organization } from "@/types";

interface OrgState {
  currentOrg: Organization | null;
  orgs: Organization[];
  setCurrentOrg: (org: Organization | null) => void;
  setOrgs: (orgs: Organization[]) => void;
}

export const useOrgStore = create<OrgState>((set) => ({
  currentOrg: null,
  orgs: [],

  setCurrentOrg: (org: Organization | null) => {
    set({ currentOrg: org });
    if (org) {
      localStorage.setItem("org_id", org.id);
    } else {
      localStorage.removeItem("org_id");
    }
  },

  setOrgs: (orgs: Organization[]) => {
    set({ orgs });
  },
}));
