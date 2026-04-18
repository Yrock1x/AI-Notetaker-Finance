"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { signInWithOAuth } from "@/lib/auth";
import { getBrowserSupabase } from "@/lib/supabase/browser";

type AuthMode = "signin" | "signup";

export default function LoginPage() {
  return (
    <Suspense fallback={<div />}>
      <LoginContent />
    </Suspense>
  );
}

function LoginContent() {
  const router = useRouter();
  const search = useSearchParams();
  const nextPath = search.get("next") || "/dashboard";

  const [mode, setMode] = useState<AuthMode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [oauthLoading, setOauthLoading] = useState<"google" | "azure" | null>(
    null
  );
  const [emailLoading, setEmailLoading] = useState(false);

  const resetMessages = () => {
    setError(null);
    setNotice(null);
  };

  const handleOAuth = async (provider: "google" | "azure") => {
    resetMessages();
    setOauthLoading(provider);
    try {
      await signInWithOAuth(provider, nextPath);
    } catch (e: unknown) {
      setOauthLoading(null);
      setError(
        e instanceof Error ? e.message : "Sign in failed. Please try again."
      );
    }
  };

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    resetMessages();
    setEmailLoading(true);
    const supabase = getBrowserSupabase();

    try {
      if (mode === "signin") {
        const { error } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (error) {
          setError(error.message);
        } else {
          router.push(nextPath);
          router.refresh();
        }
      } else {
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
          options: {
            data: { full_name: fullName || email.split("@")[0] },
            // emailRedirectTo is only used when Supabase's email confirmations
            // are on; harmless if they're off.
            emailRedirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent(nextPath)}`,
          },
        });
        if (error) {
          setError(error.message);
        } else if (data.session) {
          // Confirmations disabled — signed in immediately.
          router.push(nextPath);
          router.refresh();
        } else {
          // Confirmations enabled — user must click the email link.
          setNotice(
            `Check ${email} for a confirmation link. You can close this tab and click through from your inbox.`
          );
        }
      }
    } catch (e: unknown) {
      setError(
        e instanceof Error ? e.message : "Something went wrong. Try again."
      );
    } finally {
      setEmailLoading(false);
    }
  };

  const busy = emailLoading || oauthLoading !== null;

  return (
    <div className="space-y-8 antialiased">
      <div className="text-center space-y-2">
        <h1 className="text-4xl font-heading font-extrabold tracking-tight text-primary uppercase">
          Deal Companion
        </h1>
        <p className="font-subheading text-[#1A1A1A]/60 text-sm font-medium">
          {mode === "signin"
            ? "Sign in to your account."
            : "Create an account."}
        </p>
      </div>

      {/* Mode toggle */}
      <div className="flex rounded-[2rem] border border-[#1A1A1A]/10 overflow-hidden">
        {(["signin", "signup"] as AuthMode[]).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => {
              setMode(m);
              resetMessages();
            }}
            className={`flex-1 py-3 text-xs font-heading font-bold uppercase tracking-wider transition-all ${
              mode === m
                ? "bg-accent text-white"
                : "bg-transparent text-[#1A1A1A]/40 hover:text-[#1A1A1A]/60"
            }`}
          >
            {m === "signin" ? "Sign In" : "Sign Up"}
          </button>
        ))}
      </div>

      {error && (
        <div className="rounded-[1.5rem] bg-accent/10 p-4 text-sm text-accent font-medium border border-accent/20">
          {error}
        </div>
      )}
      {notice && (
        <div className="rounded-[1.5rem] bg-emerald-50 p-4 text-sm text-emerald-700 font-medium border border-emerald-200">
          {notice}
        </div>
      )}

      {/* Email / password form */}
      <form onSubmit={handleEmailSubmit} className="space-y-4">
        {mode === "signup" && (
          <div className="space-y-1.5">
            <label
              htmlFor="full-name"
              className="block text-xs font-data uppercase tracking-widest text-[#1A1A1A]/40 font-bold ml-1"
            >
              Full Name
            </label>
            <input
              id="full-name"
              type="text"
              autoComplete="name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="John Smith"
              className="w-full rounded-[1.5rem] border border-[#1A1A1A]/10 px-6 py-4 text-sm font-subheading focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent bg-[#F2F0E9]/50 transition-all"
            />
          </div>
        )}

        <div className="space-y-1.5">
          <label
            htmlFor="email"
            className="block text-xs font-data uppercase tracking-widest text-[#1A1A1A]/40 font-bold ml-1"
          >
            Email
          </label>
          <input
            id="email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@yourfirm.com"
            className="w-full rounded-[1.5rem] border border-[#1A1A1A]/10 px-6 py-4 text-sm font-subheading focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent bg-[#F2F0E9]/50 transition-all"
          />
        </div>

        <div className="space-y-1.5">
          <label
            htmlFor="password"
            className="block text-xs font-data uppercase tracking-widest text-[#1A1A1A]/40 font-bold ml-1"
          >
            Password
          </label>
          <input
            id="password"
            type="password"
            required
            minLength={6}
            autoComplete={mode === "signin" ? "current-password" : "new-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            className="w-full rounded-[1.5rem] border border-[#1A1A1A]/10 px-6 py-4 text-sm font-subheading focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent bg-[#F2F0E9]/50 transition-all"
          />
        </div>

        <button
          type="submit"
          disabled={busy || !email || !password}
          className="w-full rounded-[2rem] bg-accent py-4 text-sm font-heading font-bold text-white shadow-xl hover:shadow-[#CC5833]/20 disabled:opacity-50 transition-all"
        >
          {emailLoading
            ? mode === "signin"
              ? "Signing in…"
              : "Creating account…"
            : mode === "signin"
              ? "Sign In"
              : "Create Account"}
        </button>
      </form>

      {/* Divider */}
      <div className="flex items-center gap-3 text-[10px] font-data uppercase tracking-[0.2em] text-[#1A1A1A]/30">
        <div className="h-px flex-1 bg-[#1A1A1A]/10" />
        <span>or continue with</span>
        <div className="h-px flex-1 bg-[#1A1A1A]/10" />
      </div>

      {/* OAuth buttons */}
      <div className="space-y-3">
        <button
          type="button"
          onClick={() => handleOAuth("google")}
          disabled={busy}
          className="group w-full flex items-center justify-between gap-3 rounded-[2rem] border border-[#1A1A1A]/10 bg-white py-4 px-6 text-left text-sm hover:border-accent hover:bg-white transition-all shadow-sm disabled:opacity-60"
        >
          <div className="flex items-center gap-3">
            <GoogleIcon />
            <span className="font-heading font-bold text-primary group-hover:text-accent">
              {oauthLoading === "google"
                ? "Redirecting…"
                : "Continue with Google"}
            </span>
          </div>
          <div className="w-8 h-8 rounded-full bg-[#F2F0E9] flex items-center justify-center group-hover:bg-accent group-hover:text-white transition-all">
            <ArrowRight className="w-4 h-4" />
          </div>
        </button>

        <button
          type="button"
          onClick={() => handleOAuth("azure")}
          disabled={busy}
          className="group w-full flex items-center justify-between gap-3 rounded-[2rem] border border-[#1A1A1A]/10 bg-white py-4 px-6 text-left text-sm hover:border-accent hover:bg-white transition-all shadow-sm disabled:opacity-60"
        >
          <div className="flex items-center gap-3">
            <MicrosoftIcon />
            <span className="font-heading font-bold text-primary group-hover:text-accent">
              {oauthLoading === "azure"
                ? "Redirecting…"
                : "Continue with Microsoft"}
            </span>
          </div>
          <div className="w-8 h-8 rounded-full bg-[#F2F0E9] flex items-center justify-center group-hover:bg-accent group-hover:text-white transition-all">
            <ArrowRight className="w-4 h-4" />
          </div>
        </button>
      </div>

      <p className="text-center text-[10px] font-data uppercase tracking-[0.2em] text-[#1A1A1A]/40 font-bold">
        Authentication by Supabase
      </p>
    </div>
  );
}

function GoogleIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path
        fill="#4285F4"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
      />
      <path
        fill="#FBBC05"
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
      />
      <path
        fill="#EA4335"
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
      />
    </svg>
  );
}

function MicrosoftIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 23 23" xmlns="http://www.w3.org/2000/svg">
      <path fill="#F25022" d="M1 1h10v10H1z" />
      <path fill="#00A4EF" d="M1 12h10v10H1z" />
      <path fill="#7FBA00" d="M12 1h10v10H12z" />
      <path fill="#FFB900" d="M12 12h10v10H12z" />
    </svg>
  );
}
