import { useAuthStore } from "@/stores/auth-store";

export function useAuth() {
  const user = useAuthStore((state) => state.user);
  const tokens = useAuthStore((state) => state.tokens);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const isLoading = useAuthStore((state) => state.isLoading);
  const login = useAuthStore((state) => state.login);
  const logout = useAuthStore((state) => state.logout);
  const setUser = useAuthStore((state) => state.setUser);

  return {
    user,
    tokens,
    isAuthenticated,
    isLoading,
    login,
    logout,
    setUser,
  };
}
