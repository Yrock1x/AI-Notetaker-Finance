"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import apiClient from "@/lib/api-client";

const SEED_USERS = [
  { email: "sarah.chen@meridiancapital.com", name: "Sarah Chen", role: "Owner / Deal Lead" },
  { email: "michael.torres@meridiancapital.com", name: "Michael Torres", role: "Admin" },
  { email: "emily.park@meridiancapital.com", name: "Emily Park", role: "Analyst" },
  { email: "james.whitfield@meridiancapital.com", name: "James Whitfield", role: "Viewer" },
];

export default function LoginPage() {
  const router = useRouter();
  const login = useAuthStore((state) => state.login);
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const response = await apiClient.post("/auth/demo-login", { email });
      const { access_token, refresh_token, expires_in, token_type, user } =
        response.data;
      login(user, { access_token, refresh_token, expires_in, token_type });
      router.push("/dashboard");
    } catch {
      setError(
        "Login failed. Please use one of the demo accounts listed below."
      );
    } finally {
      setLoading(false);
    }
  };

  const handleQuickLogin = async (userEmail: string) => {
    setEmail(userEmail);
    setLoading(true);
    setError("");

    try {
      const response = await apiClient.post("/auth/demo-login", {
        email: userEmail,
      });
      const { access_token, refresh_token, expires_in, token_type, user } =
        response.data;
      login(user, { access_token, refresh_token, expires_in, token_type });
      router.push("/dashboard");
    } catch {
      setError(
        "Login failed. Please use one of the demo accounts listed below."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h1 className="text-2xl font-bold">Sign In</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Sign in to your DealWise AI account
        </p>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-red-800">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
            className="mt-1 w-full rounded-md border px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-md bg-primary py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {loading ? "Signing in..." : "Sign In"}
        </button>
      </form>

      <div className="space-y-2">
        <p className="text-center text-xs font-medium text-muted-foreground">
          Demo Accounts
        </p>
        <div className="space-y-1">
          {SEED_USERS.map((user) => (
            <button
              key={user.email}
              type="button"
              onClick={() => handleQuickLogin(user.email)}
              className="w-full rounded-md border px-3 py-2 text-left text-xs hover:bg-muted/50 transition-colors"
            >
              <span className="font-medium">{user.name}</span>
              <span className="ml-2 text-muted-foreground">({user.role})</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
