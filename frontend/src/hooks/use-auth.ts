import { useAuthStore } from "@/stores/auth-store";
import { useShallow } from "zustand/react/shallow";

export function useAuth() {
  return useAuthStore(
    useShallow((state) => ({
      user: state.user,
      tokens: state.tokens,
      isAuthenticated: state.isAuthenticated,
      isLoading: state.isLoading,
      login: state.login,
      logout: state.logout,
      initialize: state.initialize,
    }))
  );
}
