"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { signInWithOAuth } from "@/lib/auth";
import { getBrowserSupabase } from "@/lib/supabase/browser";
import { useScribeTheme } from "@/components/cogniscribe/theme-provider";
import { Eyebrow } from "@/components/cogniscribe/primitives";

type AuthMode = "signin" | "signup";

export default function LoginPage() {
  return (
    <Suspense fallback={<div />}>
      <LoginContent />
    </Suspense>
  );
}

function LoginContent() {
  const { isDark } = useScribeTheme();
  const router = useRouter();
  const search = useSearchParams();
  const nextPath = search.get("next") || "/dashboard";

  const [mode, setMode] = useState<AuthMode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [oauthLoading, setOauthLoading] = useState<"google" | "azure" | null>(null);
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
      setError(e instanceof Error ? e.message : "Sign in failed. Please try again.");
    }
  };

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    resetMessages();
    setEmailLoading(true);
    const supabase = getBrowserSupabase();

    try {
      if (mode === "signin") {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
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
            emailRedirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent(nextPath)}`,
          },
        });
        if (error) {
          setError(error.message);
        } else if (data.session) {
          router.push(nextPath);
          router.refresh();
        } else {
          setNotice(`Check ${email} for a confirmation link.`);
        }
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Something went wrong. Try again.");
    } finally {
      setEmailLoading(false);
    }
  };

  const busy = emailLoading || oauthLoading !== null;

  const inputCls = `w-full rounded-xl border px-4 py-3 text-[14px] outline-none transition-colors ${
    isDark
      ? "bg-white/[0.03] border-white/10 text-white placeholder-white/30 focus:border-emerald-500/40"
      : "bg-[#fafafa] border-black/[0.08] text-black placeholder-black/30 focus:border-emerald-500/40"
  }`;

  return (
    <div className="flex flex-col gap-7">
      <div className="text-center flex flex-col gap-2">
        <h1 className="text-[40px] leading-[1.05] tracking-[-0.02em] font-medium">
          Welcome
          <br />
          <span
            className="font-display italic font-normal"
            style={{ color: isDark ? "rgba(255,255,255,0.55)" : "rgba(0,0,0,0.45)" }}
          >
            {mode === "signin" ? "back." : "aboard."}
          </span>
        </h1>
        <p className={`text-[13px] ${isDark ? "text-white/55" : "text-black/55"}`}>
          {mode === "signin" ? "Sign in to your CogniSuite workspace." : "Create your CogniSuite workspace."}
        </p>
      </div>

      <div
        className={`flex rounded-full p-1 border ${
          isDark ? "bg-white/[0.03] border-white/10" : "bg-[#fafafa] border-black/[0.06]"
        }`}
      >
        {(["signin", "signup"] as AuthMode[]).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => {
              setMode(m);
              resetMessages();
            }}
            className={`flex-1 py-2 text-[12px] font-medium rounded-full transition-colors ${
              mode === m
                ? isDark
                  ? "bg-white text-[#0a0a0a]"
                  : "bg-[#0a0a0a] text-white"
                : isDark
                ? "text-white/55 hover:text-white/80"
                : "text-black/55 hover:text-black/80"
            }`}
          >
            {m === "signin" ? "Sign in" : "Sign up"}
          </button>
        ))}
      </div>

      {error && (
        <div
          className={`rounded-xl px-4 py-3 text-[12px] border ${
            isDark
              ? "bg-rose-500/10 text-rose-300 border-rose-500/25"
              : "bg-rose-50 text-rose-700 border-rose-200/70"
          }`}
        >
          {error}
        </div>
      )}
      {notice && (
        <div
          className={`rounded-xl px-4 py-3 text-[12px] border ${
            isDark
              ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/25"
              : "bg-emerald-50 text-emerald-700 border-emerald-200/70"
          }`}
        >
          {notice}
        </div>
      )}

      <form onSubmit={handleEmailSubmit} className="flex flex-col gap-3.5">
        {mode === "signup" && (
          <div className="flex flex-col gap-1.5">
            <Eyebrow>Full name</Eyebrow>
            <input
              id="full-name"
              type="text"
              autoComplete="name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Jane Smith"
              className={inputCls}
            />
          </div>
        )}

        <div className="flex flex-col gap-1.5">
          <Eyebrow>Email</Eyebrow>
          <input
            id="email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@yourfirm.com"
            className={inputCls}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <Eyebrow>Password</Eyebrow>
          <input
            id="password"
            type="password"
            required
            minLength={6}
            autoComplete={mode === "signin" ? "current-password" : "new-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            className={inputCls}
          />
        </div>

        <button
          type="submit"
          disabled={busy || !email || !password}
          className={`mt-2 inline-flex items-center justify-center gap-2 h-11 rounded-full text-[13px] font-medium transition-colors disabled:opacity-50 ${
            isDark ? "bg-white text-[#0a0a0a] hover:bg-white/90" : "bg-[#0a0a0a] text-white hover:bg-black/90"
          }`}
        >
          {emailLoading
            ? mode === "signin"
              ? "Signing in…"
              : "Creating account…"
            : mode === "signin"
            ? "Sign in"
            : "Create account"}
          <ArrowRight className="w-4 h-4" />
        </button>
      </form>

      <div
        className={`flex items-center gap-3 text-[10px] font-mono uppercase tracking-[0.22em] ${
          isDark ? "text-white/30" : "text-black/30"
        }`}
      >
        <div className={`h-px flex-1 ${isDark ? "bg-white/10" : "bg-black/10"}`} />
        <span>or continue with</span>
        <div className={`h-px flex-1 ${isDark ? "bg-white/10" : "bg-black/10"}`} />
      </div>

      <div className="flex flex-col gap-2.5">
        <button
          type="button"
          onClick={() => handleOAuth("google")}
          disabled={busy}
          className={`group w-full flex items-center justify-between gap-3 rounded-xl border py-3 px-4 text-[13px] transition-colors disabled:opacity-50 ${
            isDark
              ? "bg-white/[0.03] border-white/10 hover:border-white/25 hover:bg-white/[0.06]"
              : "bg-white border-black/[0.08] hover:border-black/20"
          }`}
        >
          <div className="flex items-center gap-3">
            <GoogleIcon />
            <span className={`font-medium ${isDark ? "text-white/85" : "text-black/85"}`}>
              {oauthLoading === "google" ? "Redirecting…" : "Continue with Google"}
            </span>
          </div>
          <ArrowRight
            className={`w-4 h-4 transition-transform group-hover:translate-x-0.5 ${
              isDark ? "text-white/30" : "text-black/30"
            }`}
          />
        </button>

        <button
          type="button"
          onClick={() => handleOAuth("azure")}
          disabled={busy}
          className={`group w-full flex items-center justify-between gap-3 rounded-xl border py-3 px-4 text-[13px] transition-colors disabled:opacity-50 ${
            isDark
              ? "bg-white/[0.03] border-white/10 hover:border-white/25 hover:bg-white/[0.06]"
              : "bg-white border-black/[0.08] hover:border-black/20"
          }`}
        >
          <div className="flex items-center gap-3">
            <MicrosoftIcon />
            <span className={`font-medium ${isDark ? "text-white/85" : "text-black/85"}`}>
              {oauthLoading === "azure" ? "Redirecting…" : "Continue with Microsoft"}
            </span>
          </div>
          <ArrowRight
            className={`w-4 h-4 transition-transform group-hover:translate-x-0.5 ${
              isDark ? "text-white/30" : "text-black/30"
            }`}
          />
        </button>
      </div>

      <p
        className={`text-center text-[10px] font-mono tracking-[0.22em] uppercase ${
          isDark ? "text-white/30" : "text-black/30"
        }`}
      >
        Authentication by Supabase
      </p>
    </div>
  );
}

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
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
    <svg width="18" height="18" viewBox="0 0 23 23" xmlns="http://www.w3.org/2000/svg">
      <path fill="#F25022" d="M1 1h10v10H1z" />
      <path fill="#00A4EF" d="M1 12h10v10H1z" />
      <path fill="#7FBA00" d="M12 1h10v10H12z" />
      <path fill="#FFB900" d="M12 12h10v10H12z" />
    </svg>
  );
}
