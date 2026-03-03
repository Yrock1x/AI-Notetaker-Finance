"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import apiClient from "@/lib/api-client";
import { ArrowRight, UserPlus } from "lucide-react";

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
  const [mode, setMode] = useState<"login" | "register">("login");
  const [fullName, setFullName] = useState("");
  const [orgName, setOrgName] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      if (mode === "register") {
        const response = await apiClient.post("/auth/demo-register", {
          email,
          full_name: fullName,
          org_name: orgName || undefined,
        });
        const { access_token, refresh_token, expires_in, token_type, user } =
          response.data;
        login(user, { access_token, refresh_token, expires_in, token_type });
        router.push("/dashboard");
      } else {
        const response = await apiClient.post("/auth/demo-login", { email });
        const { access_token, refresh_token, expires_in, token_type, user } =
          response.data;
        login(user, { access_token, refresh_token, expires_in, token_type });
        router.push("/dashboard");
      }
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        (mode === "register"
          ? "Registration failed. Please try a different email."
          : "Login failed. Please use one of the demo accounts listed below.");
      setError(message);
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
    <div className="space-y-10 antialiased">
      <div className="text-center space-y-2">
        <h1 className="text-4xl font-heading font-extrabold tracking-tight text-primary uppercase">Deal Companion</h1>
        <p className="font-subheading text-[#1A1A1A]/60 text-sm font-medium">
          {mode === "register" ? "Create your account." : "Initialize your investment protocol."}
        </p>
      </div>

      {/* Mode toggle */}
      <div className="flex rounded-[2rem] border border-[#1A1A1A]/10 overflow-hidden">
        <button
          type="button"
          onClick={() => { setMode("login"); setError(""); }}
          className={`flex-1 py-3 text-xs font-heading font-bold uppercase tracking-wider transition-all ${
            mode === "login"
              ? "bg-accent text-white"
              : "bg-transparent text-[#1A1A1A]/40 hover:text-[#1A1A1A]/60"
          }`}
        >
          Sign In
        </button>
        <button
          type="button"
          onClick={() => { setMode("register"); setError(""); }}
          className={`flex-1 py-3 text-xs font-heading font-bold uppercase tracking-wider transition-all ${
            mode === "register"
              ? "bg-accent text-white"
              : "bg-transparent text-[#1A1A1A]/40 hover:text-[#1A1A1A]/60"
          }`}
        >
          Register
        </button>
      </div>

      {error && (
        <div className="rounded-[1.5rem] bg-accent/10 p-4 text-sm text-accent font-medium border border-accent/20">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {mode === "register" && (
          <div className="space-y-2">
            <label className="block text-xs font-data uppercase tracking-widest text-[#1A1A1A]/40 font-bold ml-1" htmlFor="fullName">
              Full Name
            </label>
            <input
              id="fullName"
              type="text"
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="John Smith"
              className="w-full rounded-[1.5rem] border border-[#1A1A1A]/10 px-6 py-4 text-sm font-subheading focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent bg-[#F2F0E9]/50 transition-all"
            />
          </div>
        )}

        <div className="space-y-2">
          <label className="block text-xs font-data uppercase tracking-widest text-[#1A1A1A]/40 font-bold ml-1" htmlFor="email">
            Email Identity
          </label>
          <input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@yourfirm.com"
            className="w-full rounded-[1.5rem] border border-[#1A1A1A]/10 px-6 py-4 text-sm font-subheading focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent bg-[#F2F0E9]/50 transition-all"
          />
        </div>

        {mode === "register" && (
          <div className="space-y-2">
            <label className="block text-xs font-data uppercase tracking-widest text-[#1A1A1A]/40 font-bold ml-1" htmlFor="orgName">
              Organization Name
              <span className="text-[#1A1A1A]/20 ml-2">(optional)</span>
            </label>
            <input
              id="orgName"
              type="text"
              value={orgName}
              onChange={(e) => setOrgName(e.target.value)}
              placeholder="Meridian Capital Partners"
              className="w-full rounded-[1.5rem] border border-[#1A1A1A]/10 px-6 py-4 text-sm font-subheading focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent bg-[#F2F0E9]/50 transition-all"
            />
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="magnetic-btn w-full rounded-[2rem] bg-accent py-4 text-sm font-heading font-bold text-white shadow-xl hover:shadow-[#CC5833]/20 disabled:opacity-50 transition-all relative overflow-hidden group"
        >
          <span className="relative z-10 flex items-center justify-center gap-2">
            {mode === "register" && <UserPlus className="w-4 h-4" />}
            {loading
              ? "Synchronizing..."
              : mode === "register"
                ? "Create Account"
                : "Initialize Session"}
          </span>
          <div className="absolute inset-0 bg-[#2E4036] translate-y-full group-hover:translate-y-0 transition-transform duration-300"></div>
        </button>
      </form>

      {mode === "login" && (
        <div className="space-y-6 pt-4 border-t border-[#1A1A1A]/5">
          <p className="text-center text-[10px] font-data uppercase tracking-[0.2em] text-[#1A1A1A]/40 font-bold">
            Demo Selection
          </p>
          <div className="grid grid-cols-1 gap-3">
            {SEED_USERS.map((user) => (
              <button
                key={user.email}
                type="button"
                onClick={() => handleQuickLogin(user.email)}
                className="group w-full rounded-[1.5rem] border border-[#1A1A1A]/10 px-6 py-4 text-left text-xs hover:border-accent hover:bg-white transition-all shadow-sm hover:shadow-md flex items-center justify-between"
              >
                <div className="space-y-0.5">
                  <div className="font-heading font-bold text-primary group-hover:text-accent transition-colors">{user.name}</div>
                  <div className="font-subheading text-[#1A1A1A]/40 font-medium tracking-tight">{user.role}</div>
                </div>
                <div className="w-8 h-8 rounded-full bg-[#F2F0E9] flex items-center justify-center group-hover:bg-accent group-hover:text-white transition-all">
                  <ArrowRight className="w-4 h-4" />
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
