import { describe, it, expect, beforeEach, vi } from "vitest";
import { useOrgSelection } from "@/stores/org-store";
import { useUIStore } from "@/stores/ui-store";

// Auth session lives in @supabase/ssr cookies — tested via middleware +
// browser flow, not in isolation here. Org selection (just an id) and the UI
// store are the only client-side stores worth unit testing.

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

// ---------------------------------------------------------------------------
// Org Selection Store
// ---------------------------------------------------------------------------
describe("useOrgSelection", () => {
  beforeEach(() => {
    localStorageMock._reset();
    useOrgSelection.setState({ currentOrgId: null });
  });

  it("starts with null currentOrgId", () => {
    expect(useOrgSelection.getState().currentOrgId).toBeNull();
  });

  it("persists org_id to localStorage when set", () => {
    useOrgSelection.getState().setCurrentOrgId("org-42");
    expect(localStorageMock.setItem).toHaveBeenCalledWith("org_id", "org-42");
    expect(useOrgSelection.getState().currentOrgId).toBe("org-42");
  });

  it("removes org_id from localStorage when cleared", () => {
    useOrgSelection.getState().setCurrentOrgId("org-1");
    localStorageMock.removeItem.mockClear();
    useOrgSelection.getState().setCurrentOrgId(null);
    expect(localStorageMock.removeItem).toHaveBeenCalledWith("org_id");
    expect(useOrgSelection.getState().currentOrgId).toBeNull();
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
