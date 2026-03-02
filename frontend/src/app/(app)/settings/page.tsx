"use client";

import { useEffect } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useUIStore } from "@/stores/ui-store";

export default function SettingsPage() {
  const user = useAuthStore((state) => state.user);
  const { theme, setTheme } = useUIStore();

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") {
      root.classList.add("dark");
    } else if (theme === "light") {
      root.classList.remove("dark");
    } else {
      // System preference
      const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      root.classList.toggle("dark", prefersDark);
    }
  }, [theme]);

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="mt-1 text-muted-foreground">Manage your preferences.</p>
      </div>

      {/* Profile */}
      <div className="rounded-lg border bg-white p-6">
        <h3 className="font-medium">Profile</h3>
        <div className="mt-4 space-y-3">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary text-lg text-primary-foreground">
              {user?.full_name?.charAt(0)?.toUpperCase() ?? "?"}
            </div>
            <div>
              <p className="font-medium">{user?.full_name ?? "Unknown"}</p>
              <p className="text-sm text-muted-foreground">{user?.email ?? ""}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Appearance */}
      <div className="rounded-lg border bg-white p-6">
        <h3 className="font-medium">Appearance</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Choose your preferred color theme.
        </p>
        <div className="mt-4 flex gap-3">
          {(["light", "dark", "system"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTheme(t)}
              className={`rounded-md border px-4 py-2 text-sm font-medium capitalize ${
                theme === t
                  ? "border-primary bg-primary/10 text-primary"
                  : "hover:bg-muted"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
