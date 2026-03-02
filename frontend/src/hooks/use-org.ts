import { useOrgStore } from "@/stores/org-store";

export function useOrg() {
  const currentOrg = useOrgStore((state) => state.currentOrg);
  const orgs = useOrgStore((state) => state.orgs);
  const setCurrentOrg = useOrgStore((state) => state.setCurrentOrg);
  const setOrgs = useOrgStore((state) => state.setOrgs);

  return {
    currentOrg,
    orgs,
    setCurrentOrg,
    setOrgs,
  };
}
