"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";
import apiClient from "@/lib/api-client";
import Link from "next/link";

function CallbackHandler() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const login = useAuthStore((state) => state.login);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = searchParams.get("code");
    const state = searchParams.get("state");

    if (!code || !state) {
      setError("Missing authentication parameters. Please try signing in again.");
      return;
    }

    const handleCallback = async () => {
      try {
        const response = await apiClient.post("/auth/callback", { code, state });
        const { access_token, refresh_token, expires_in, token_type, user } =
          response.data;

        const tokens = { access_token, refresh_token, expires_in, token_type };

        login(user, tokens);
        router.push("/dashboard");
      } catch (err: unknown) {
        let message = "Authentication failed. Please try again.";

        if (
          err !== null &&
          typeof err === "object" &&
          "response" in err &&
          err.response !== null &&
          typeof err.response === "object" &&
          "data" in err.response &&
          err.response.data !== null &&
          typeof err.response.data === "object" &&
          "detail" in err.response.data &&
          typeof err.response.data.detail === "string"
        ) {
          message = err.response.data.detail;
        }

        setError(message);
      }
    };

    handleCallback();
  }, [searchParams, login, router]);

  if (error) {
    return (
      <div className="text-center space-y-4">
        <div className="rounded-md bg-red-50 p-4 text-sm text-red-800">
          {error}
        </div>
        <Link
          href="/login"
          className="inline-block text-sm font-medium text-primary hover:underline"
        >
          Return to login
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center space-y-4 text-center">
      <Loader2 className="h-8 w-8 animate-spin text-primary" />
      <div>
        <h1 className="text-xl font-semibold">Processing authentication...</h1>
        <p className="mt-2 text-muted-foreground">
          Please wait while we complete your sign-in.
        </p>
      </div>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex flex-col items-center space-y-4 text-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-muted-foreground">Loading...</p>
        </div>
      }
    >
      <CallbackHandler />
    </Suspense>
  );
}
