import { describe, it, expect, beforeEach, vi } from "vitest";
import { useOrgStore } from "@/stores/org-store";
import { useUIStore } from "@/stores/ui-store";
import type { Organization } from "@/types";

// The auth store is a Supabase-backed shim — its behaviour is driven by
// @supabase/ssr cookies, not by local state. Testing it in isolation would
// require mocking the whole Supabase client; the effective contract is
// verified by middleware + the browser flow. Only the org + UI stores are
// covered here.

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
    get length() {
      return Object.keys(store).length;
    },
    key: vi.fn((i: number) => Object.keys(store)[i] ?? null),
    _reset: () => {
      store = {};
      localStorageMock.getItem.mockClear();
      localStorageMock.setItem.mockClear();
      localStorageMock.removeItem.mockClear();
    },
  };
})();

Object.defineProperty(globalThis, "localStorage", {
  value: localStorageMock,
  writable: true,
});
if (typeof globalThis.window === "undefined") {
  Object.defineProperty(globalThis, "window", {
    value: globalThis,
    writable: true,
  });
}

function makeOrg(overrides?: Partial<Organization>): Organization {
  return {
    id: "org-1",
    name: "Acme Capital",
    slug: "acme-capital",
    settings: {},
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Org Store
// ---------------------------------------------------------------------------
describe("useOrgStore", () => {
  beforeEach(() => {
    localStorageMock._reset();
    useOrgStore.setState({ currentOrg: null, orgs: [] });
  });

  it("starts with null currentOrg", () => {
    expect(useOrgStore.getState().currentOrg).toBeNull();
  });

  it("starts with empty orgs array", () => {
    expect(useOrgStore.getState().orgs).toEqual([]);
  });

  it("persists org_id to localStorage when org is set", () => {
    const org = makeOrg({ id: "org-42" });
    useOrgStore.getState().setCurrentOrg(org);
    expect(localStorageMock.setItem).toHaveBeenCalledWith("org_id", "org-42");
  });

  it("removes org_id when org is cleared", () => {
    useOrgStore.getState().setCurrentOrg(makeOrg());
    localStorageMock.removeItem.mockClear();
    useOrgStore.getState().setCurrentOrg(null);
    expect(localStorageMock.removeItem).toHaveBeenCalledWith("org_id");
  });

  it("replaces the orgs array on setOrgs", () => {
    useOrgStore.getState().setOrgs([makeOrg({ id: "org-1" })]);
    useOrgStore.getState().setOrgs([
      makeOrg({ id: "org-2" }),
      makeOrg({ id: "org-3" }),
    ]);
    expect(useOrgStore.getState().orgs).toHaveLength(2);
  });
});

// ---------------------------------------------------------------------------
// UI Store
// ---------------------------------------------------------------------------
describe("useUIStore", () => {
  beforeEach(() => {
    useUIStore.setState({ sidebarOpen: true, theme: "system" });
  });

  it("toggles the sidebar", () => {
    useUIStore.getState().toggleSidebar();
    expect(useUIStore.getState().sidebarOpen).toBe(false);
    useUIStore.getState().toggleSidebar();
    expect(useUIStore.getState().sidebarOpen).toBe(true);
  });

  it("sets the theme", () => {
    useUIStore.getState().setTheme("dark");
    expect(useUIStore.getState().theme).toBe("dark");
    useUIStore.getState().setTheme("system");
    expect(useUIStore.getState().theme).toBe("system");
  });
});
