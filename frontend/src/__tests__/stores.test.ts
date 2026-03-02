import { describe, it, expect, beforeEach, vi } from "vitest";
import { useAuthStore, setQueryClientRef } from "@/stores/auth-store";
import { useOrgStore } from "@/stores/org-store";
import { useUIStore } from "@/stores/ui-store";
import type { User, AuthTokens, Organization } from "@/types";

// ---------------------------------------------------------------------------
// Helpers: mock localStorage
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
    _store: store,
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

// Ensure `window` is defined so store guards like `typeof window !== 'undefined'` pass
if (typeof globalThis.window === "undefined") {
  Object.defineProperty(globalThis, "window", {
    value: globalThis,
    writable: true,
  });
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------
function makeUser(overrides?: Partial<User>): User {
  return {
    id: "user-1",
    email: "john@example.com",
    full_name: "John Doe",
    org_id: "org-1",
    role: "admin",
    is_active: true,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

function makeTokens(overrides?: Partial<AuthTokens>): AuthTokens {
  return {
    access_token: "test-access-token",
    refresh_token: "test-refresh-token",
    ...overrides,
  } as AuthTokens;
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

// Create a non-expired JWT payload for testing initialize()
function makeJwt(exp?: number): string {
  const payload = {
    sub: "user-1",
    exp: exp ?? Math.floor(Date.now() / 1000) + 3600, // 1 hour from now
  };
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.signature`;
}

// ---------------------------------------------------------------------------
// Auth Store
// ---------------------------------------------------------------------------
describe("useAuthStore", () => {
  beforeEach(() => {
    localStorageMock._reset();
    // Reset store to initial state
    useAuthStore.setState({
      user: null,
      tokens: null,
      isAuthenticated: false,
      isLoading: true,
    });
  });

  describe("initial state", () => {
    it("should start with null user and tokens", () => {
      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.tokens).toBeNull();
    });

    it("should start unauthenticated", () => {
      expect(useAuthStore.getState().isAuthenticated).toBe(false);
    });

    it("should start in loading state", () => {
      expect(useAuthStore.getState().isLoading).toBe(true);
    });
  });

  describe("login", () => {
    it("should set user and tokens", () => {
      const user = makeUser();
      const tokens = makeTokens();
      useAuthStore.getState().login(user, tokens);

      const state = useAuthStore.getState();
      expect(state.user).toEqual(user);
      expect(state.tokens).toEqual(tokens);
    });

    it("should set isAuthenticated to true", () => {
      useAuthStore.getState().login(makeUser(), makeTokens());
      expect(useAuthStore.getState().isAuthenticated).toBe(true);
    });

    it("should set isLoading to false", () => {
      useAuthStore.getState().login(makeUser(), makeTokens());
      expect(useAuthStore.getState().isLoading).toBe(false);
    });

    it("should persist access_token to localStorage", () => {
      const tokens = makeTokens({ access_token: "my-at" });
      useAuthStore.getState().login(makeUser(), tokens);
      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        "access_token",
        "my-at"
      );
    });

    it("should persist refresh_token to localStorage", () => {
      const tokens = makeTokens({ refresh_token: "my-rt" });
      useAuthStore.getState().login(makeUser(), tokens);
      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        "refresh_token",
        "my-rt"
      );
    });

    it("should persist org_id to localStorage when user has org_id", () => {
      const user = makeUser({ org_id: "org-42" });
      useAuthStore.getState().login(user, makeTokens());
      expect(localStorageMock.setItem).toHaveBeenCalledWith("org_id", "org-42");
    });
  });

  describe("logout", () => {
    it("should clear user and tokens", () => {
      useAuthStore.getState().login(makeUser(), makeTokens());
      useAuthStore.getState().logout();

      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.tokens).toBeNull();
    });

    it("should set isAuthenticated to false", () => {
      useAuthStore.getState().login(makeUser(), makeTokens());
      useAuthStore.getState().logout();
      expect(useAuthStore.getState().isAuthenticated).toBe(false);
    });

    it("should set isLoading to false", () => {
      useAuthStore.getState().login(makeUser(), makeTokens());
      useAuthStore.getState().logout();
      expect(useAuthStore.getState().isLoading).toBe(false);
    });

    it("should remove tokens and org_id from localStorage", () => {
      useAuthStore.getState().login(makeUser(), makeTokens());
      localStorageMock.removeItem.mockClear();
      useAuthStore.getState().logout();

      expect(localStorageMock.removeItem).toHaveBeenCalledWith("access_token");
      expect(localStorageMock.removeItem).toHaveBeenCalledWith("refresh_token");
      expect(localStorageMock.removeItem).toHaveBeenCalledWith("org_id");
    });

    it("should clear queryClient cache if ref is set", () => {
      const mockClear = vi.fn();
      setQueryClientRef({ clear: mockClear } as any);

      useAuthStore.getState().login(makeUser(), makeTokens());
      useAuthStore.getState().logout();

      expect(mockClear).toHaveBeenCalled();
      // Reset the ref
      setQueryClientRef(null as any);
    });
  });

  describe("setUser", () => {
    it("should update user and set isAuthenticated to true", () => {
      const user = makeUser({ full_name: "Jane Doe" });
      useAuthStore.getState().setUser(user);

      const state = useAuthStore.getState();
      expect(state.user).toEqual(user);
      expect(state.isAuthenticated).toBe(true);
    });
  });

  describe("setLoading", () => {
    it("should update isLoading state", () => {
      useAuthStore.getState().setLoading(false);
      expect(useAuthStore.getState().isLoading).toBe(false);

      useAuthStore.getState().setLoading(true);
      expect(useAuthStore.getState().isLoading).toBe(true);
    });
  });

  describe("initialize", () => {
    it("should authenticate when a valid non-expired JWT exists in localStorage", () => {
      const jwt = makeJwt();
      localStorageMock.setItem("access_token", jwt);
      localStorageMock.setItem("refresh_token", "rt-123");

      // Reset spy call counts after setup
      localStorageMock.getItem.mockClear();

      useAuthStore.getState().initialize();

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(true);
      expect(state.isLoading).toBe(false);
      expect(state.tokens?.access_token).toBe(jwt);
    });

    it("should clear auth state when token is expired", () => {
      const expiredJwt = makeJwt(Math.floor(Date.now() / 1000) - 3600); // 1 hour ago
      localStorageMock.setItem("access_token", expiredJwt);

      useAuthStore.getState().initialize();

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(false);
      expect(state.isLoading).toBe(false);
      expect(state.tokens).toBeNull();
    });

    it("should clear auth state when no token exists", () => {
      useAuthStore.getState().initialize();

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(false);
      expect(state.isLoading).toBe(false);
    });

    it("should clear auth state when token is malformed", () => {
      localStorageMock.setItem("access_token", "not-a-valid-jwt");

      useAuthStore.getState().initialize();

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(false);
      expect(state.tokens).toBeNull();
      expect(localStorageMock.removeItem).toHaveBeenCalledWith("access_token");
    });
  });
});

// ---------------------------------------------------------------------------
// Org Store
// ---------------------------------------------------------------------------
describe("useOrgStore", () => {
  beforeEach(() => {
    localStorageMock._reset();
    useOrgStore.setState({
      currentOrg: null,
      orgs: [],
    });
  });

  describe("initial state", () => {
    it("should start with null currentOrg", () => {
      expect(useOrgStore.getState().currentOrg).toBeNull();
    });

    it("should start with empty orgs array", () => {
      expect(useOrgStore.getState().orgs).toEqual([]);
    });
  });

  describe("setCurrentOrg", () => {
    it("should update currentOrg", () => {
      const org = makeOrg();
      useOrgStore.getState().setCurrentOrg(org);
      expect(useOrgStore.getState().currentOrg).toEqual(org);
    });

    it("should persist org_id to localStorage when org is set", () => {
      const org = makeOrg({ id: "org-42" });
      useOrgStore.getState().setCurrentOrg(org);
      expect(localStorageMock.setItem).toHaveBeenCalledWith("org_id", "org-42");
    });

    it("should remove org_id from localStorage when org is set to null", () => {
      useOrgStore.getState().setCurrentOrg(makeOrg());
      localStorageMock.removeItem.mockClear();
      useOrgStore.getState().setCurrentOrg(null);
      expect(localStorageMock.removeItem).toHaveBeenCalledWith("org_id");
    });

    it("should allow switching orgs", () => {
      const org1 = makeOrg({ id: "org-1", name: "Alpha" });
      const org2 = makeOrg({ id: "org-2", name: "Beta" });

      useOrgStore.getState().setCurrentOrg(org1);
      expect(useOrgStore.getState().currentOrg?.name).toBe("Alpha");

      useOrgStore.getState().setCurrentOrg(org2);
      expect(useOrgStore.getState().currentOrg?.name).toBe("Beta");
    });
  });

  describe("setOrgs", () => {
    it("should set the orgs array", () => {
      const orgs = [
        makeOrg({ id: "org-1", name: "Alpha" }),
        makeOrg({ id: "org-2", name: "Beta" }),
      ];
      useOrgStore.getState().setOrgs(orgs);
      expect(useOrgStore.getState().orgs).toHaveLength(2);
      expect(useOrgStore.getState().orgs[0].name).toBe("Alpha");
    });

    it("should replace existing orgs", () => {
      useOrgStore.getState().setOrgs([makeOrg({ id: "org-1" })]);
      expect(useOrgStore.getState().orgs).toHaveLength(1);

      useOrgStore.getState().setOrgs([
        makeOrg({ id: "org-2" }),
        makeOrg({ id: "org-3" }),
      ]);
      expect(useOrgStore.getState().orgs).toHaveLength(2);
    });

    it("should allow setting empty array", () => {
      useOrgStore.getState().setOrgs([makeOrg()]);
      useOrgStore.getState().setOrgs([]);
      expect(useOrgStore.getState().orgs).toEqual([]);
    });
  });
});

// ---------------------------------------------------------------------------
// UI Store
// ---------------------------------------------------------------------------
describe("useUIStore", () => {
  beforeEach(() => {
    useUIStore.setState({
      sidebarOpen: true,
      theme: "system",
    });
  });

  describe("initial state", () => {
    it("should start with sidebar open", () => {
      expect(useUIStore.getState().sidebarOpen).toBe(true);
    });

    it("should start with system theme", () => {
      expect(useUIStore.getState().theme).toBe("system");
    });
  });

  describe("toggleSidebar", () => {
    it("should toggle sidebar from open to closed", () => {
      useUIStore.getState().toggleSidebar();
      expect(useUIStore.getState().sidebarOpen).toBe(false);
    });

    it("should toggle sidebar from closed to open", () => {
      useUIStore.getState().setSidebarOpen(false);
      useUIStore.getState().toggleSidebar();
      expect(useUIStore.getState().sidebarOpen).toBe(true);
    });

    it("should toggle back and forth correctly", () => {
      expect(useUIStore.getState().sidebarOpen).toBe(true);
      useUIStore.getState().toggleSidebar();
      expect(useUIStore.getState().sidebarOpen).toBe(false);
      useUIStore.getState().toggleSidebar();
      expect(useUIStore.getState().sidebarOpen).toBe(true);
    });
  });

  describe("setSidebarOpen", () => {
    it("should set sidebar to open", () => {
      useUIStore.getState().setSidebarOpen(false);
      useUIStore.getState().setSidebarOpen(true);
      expect(useUIStore.getState().sidebarOpen).toBe(true);
    });

    it("should set sidebar to closed", () => {
      useUIStore.getState().setSidebarOpen(false);
      expect(useUIStore.getState().sidebarOpen).toBe(false);
    });
  });

  describe("setTheme", () => {
    it("should set theme to light", () => {
      useUIStore.getState().setTheme("light");
      expect(useUIStore.getState().theme).toBe("light");
    });

    it("should set theme to dark", () => {
      useUIStore.getState().setTheme("dark");
      expect(useUIStore.getState().theme).toBe("dark");
    });

    it("should set theme to system", () => {
      useUIStore.getState().setTheme("dark");
      useUIStore.getState().setTheme("system");
      expect(useUIStore.getState().theme).toBe("system");
    });

    it("should allow cycling through themes", () => {
      useUIStore.getState().setTheme("light");
      expect(useUIStore.getState().theme).toBe("light");

      useUIStore.getState().setTheme("dark");
      expect(useUIStore.getState().theme).toBe("dark");

      useUIStore.getState().setTheme("system");
      expect(useUIStore.getState().theme).toBe("system");
    });
  });
});
