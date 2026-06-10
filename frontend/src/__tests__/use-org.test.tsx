// @vitest-environment jsdom
//
// Regression tests for the org switcher, especially the F3 fix: switching org
// must drop EVERY org-scoped React Query cache entry (denylist of global
// roots), so the UI can never show the previous org's rows. A leak here is
// cross-tenant data exposure in the switcher UI.

import { describe, it, expect, beforeEach, vi } from "vitest";
import type { ReactNode } from "react";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useOrg } from "@/hooks/use-org";
import { useOrgSelection } from "@/stores/org-store";

vi.mock("@/lib/worker-api", () => ({
  apiGet: vi.fn(),
}));

import { apiGet } from "@/lib/worker-api";

const apiGetMock = vi.mocked(apiGet);

const ORG_A = { id: "org-a", name: "Alpha Capital", slug: "alpha", role: "admin" };
const ORG_B = { id: "org-b", name: "Beta Partners", slug: "beta", role: "member" };

function setup() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { client, ...renderHook(() => useOrg(), { wrapper }) };
}

beforeEach(() => {
  localStorage.clear();
  useOrgSelection.setState({ currentOrgId: null });
  apiGetMock.mockReset();
  apiGetMock.mockResolvedValue([ORG_A, ORG_B]);
});

describe("useOrg — selection", () => {
  it("auto-selects the first org when nothing is stored", async () => {
    const { result } = setup();
    await waitFor(() => expect(result.current.currentOrg?.id).toBe("org-a"));
    expect(localStorage.getItem("org_id")).toBe("org-a");
  });

  it("keeps a stored selection that is still a membership", async () => {
    useOrgSelection.setState({ currentOrgId: "org-b" });
    const { result } = setup();
    await waitFor(() => expect(result.current.currentOrg?.id).toBe("org-b"));
  });

  it("falls back to the first org when the stored selection is stale", async () => {
    useOrgSelection.setState({ currentOrgId: "org-gone" });
    const { result } = setup();
    await waitFor(() => expect(result.current.currentOrg?.id).toBe("org-a"));
  });
});

describe("useOrg — switchOrg query clearing", () => {
  it("drops every org-scoped query and keeps only the global roots", async () => {
    const { client, result } = setup();
    await waitFor(() => expect(result.current.currentOrg?.id).toBe("org-a"));

    // Caches an org switch must not leak — including one with a non-string
    // root (the predicate must treat unknown shapes as org-scoped).
    client.setQueryData(["deals", "org-a"], [{ id: "d1" }]);
    client.setQueryData(["dashboard", "org-a"], { meetings: 3 });
    client.setQueryData(["deal-extractions", "org-a", "d1"], []);
    client.setQueryData([{ odd: "key" }], "value");
    // Genuinely-global caches that must survive.
    client.setQueryData(["auth", "session"], { id: "user-1" });

    act(() => result.current.switchOrg("org-b"));

    expect(result.current.currentOrg?.id).toBe("org-b");
    expect(client.getQueryData(["deals", "org-a"])).toBeUndefined();
    expect(client.getQueryData(["dashboard", "org-a"])).toBeUndefined();
    expect(client.getQueryData(["deal-extractions", "org-a", "d1"])).toBeUndefined();
    expect(client.getQueryData([{ odd: "key" }])).toBeUndefined();
    expect(client.getQueryData(["auth", "session"])).toEqual({ id: "user-1" });
    expect(client.getQueryData(["orgs"])).toBeDefined();
  });

  it("ignores a switch to an org outside the membership", async () => {
    const { client, result } = setup();
    await waitFor(() => expect(result.current.currentOrg?.id).toBe("org-a"));
    client.setQueryData(["deals", "org-a"], [{ id: "d1" }]);

    act(() => result.current.switchOrg("org-intruder"));

    expect(result.current.currentOrg?.id).toBe("org-a");
    expect(client.getQueryData(["deals", "org-a"])).toBeDefined();
  });

  it("no-ops when switching to the already-current org", async () => {
    const { client, result } = setup();
    await waitFor(() => expect(result.current.currentOrg?.id).toBe("org-a"));
    client.setQueryData(["deals", "org-a"], [{ id: "d1" }]);

    act(() => result.current.switchOrg("org-a"));

    expect(client.getQueryData(["deals", "org-a"])).toBeDefined();
  });
});
