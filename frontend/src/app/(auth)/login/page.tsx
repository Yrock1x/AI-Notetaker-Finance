"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { signInWithOAuth } from "@/lib/auth";

export default function LoginPage() {
  return (
    <Suspense fallback={<div />}>
      <LoginContent />
    </Suspense>
  );
}

function LoginContent() {
  const search = useSearchParams();
  const nextPath = search.get("next") || "/dashboard";
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<"google" | "azure" | null>(null);

  const handleOAuth = async (provider: "google" | "azure") => {
    setError(null);
    setLoading(provider);
    try {
      await signInWithOAuth(provider, nextPath);
    } catch (e: unknown) {
      setLoading(null);
      setError(
        e instanceof Error
          ? e.message
          : "Sign in failed. Please try again."
      );
    }
  };

  return (
    <div className="space-y-10 antialiased">
      <div className="text-center space-y-2">
        <h1 className="text-4xl font-heading font-extrabold tracking-tight text-primary uppercase">
          Deal Companion
        </h1>
        <p className="font-subheading text-[#1A1A1A]/60 text-sm font-medium">
          Sign in with your work account.
        </p>
      </div>

      {error && (
        <div className="rounded-[1.5rem] bg-accent/10 p-4 text-sm text-accent font-medium border border-accent/20">
          {error}
        </div>
      )}

      <div className="space-y-3">
        <button
          type="button"
          onClick={() => handleOAuth("google")}
          disabled={loading !== null}
          className="group w-full flex items-center justify-between gap-3 rounded-[2rem] border border-[#1A1A1A]/10 bg-white py-4 px-6 text-left text-sm hover:border-accent hover:bg-white transition-all shadow-sm disabled:opacity-60"
        >
          <div className="flex items-center gap-3">
            <GoogleIcon />
            <span className="font-heading font-bold text-primary group-hover:text-accent">
              {loading === "google" ? "Redirecting…" : "Continue with Google"}
            </span>
          </div>
          <div className="w-8 h-8 rounded-full bg-[#F2F0E9] flex items-center justify-center group-hover:bg-accent group-hover:text-white transition-all">
            <ArrowRight className="w-4 h-4" />
          </div>
        </button>

        <button
          type="button"
          onClick={() => handleOAuth("azure")}
          disabled={loading !== null}
          className="group w-full flex items-center justify-between gap-3 rounded-[2rem] border border-[#1A1A1A]/10 bg-white py-4 px-6 text-left text-sm hover:border-accent hover:bg-white transition-all shadow-sm disabled:opacity-60"
        >
          <div className="flex items-center gap-3">
            <MicrosoftIcon />
            <span className="font-heading font-bold text-primary group-hover:text-accent">
              {loading === "azure" ? "Redirecting…" : "Continue with Microsoft"}
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
