"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useSession,
  userDisplayName,
} from "@/hooks/use-session";
import { OrgSwitcher } from "./org-switcher";
import { Breadcrumbs } from "./breadcrumbs";
import { Settings, LogOut } from "lucide-react";
import { useScribeTheme } from "@/components/cogniscribe/theme-provider";
import { ThemeToggle } from "@/components/cogniscribe/theme-toggle";
import { cn } from "@/lib/utils";

export function Topbar() {
  const { isDark } = useScribeTheme();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const { user, signOut } = useSession();
  const router = useRouter();

  const displayName = userDisplayName(user);
  const initial = displayName.charAt(0)?.toUpperCase() || "U";

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    if (menuOpen) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [menuOpen]);

  const handleLogout = async () => {
    setMenuOpen(false);
    await signOut();
    router.push("/login");
  };

  return (
    <header
      className={cn(
        "flex h-16 items-center justify-between border-b px-8 backdrop-blur-xl relative z-20",
        isDark
          ? "bg-[#0a0a0a]/85 text-white border-white/5"
          : "bg-[#fafafa]/85 text-black border-black/[0.06]"
      )}
    >
      <div className="flex items-center gap-4">
        <Breadcrumbs />
      </div>
      <div className="flex items-center gap-2">
        <div
          className={cn(
            "hidden md:flex items-center px-3 py-1.5 rounded-full border",
            isDark ? "bg-white/[0.03] border-white/10" : "bg-white border-black/[0.06]"
          )}
        >
          <OrgSwitcher />
        </div>
        <ThemeToggle />
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Open user menu"
            className={cn(
              "group flex h-9 w-9 items-center justify-center rounded-full text-[12px] font-semibold transition-colors",
              isDark
                ? "bg-white text-[#0a0a0a] hover:bg-white/90"
                : "bg-[#0a0a0a] text-white hover:bg-black/90"
            )}
          >
            {initial}
          </button>
          {menuOpen && (
            <div
              className={cn(
                "absolute right-0 top-full mt-2 w-56 rounded-xl border py-1 shadow-2xl z-50",
                isDark
                  ? "bg-[#0a0a0a] border-white/10"
                  : "bg-white border-black/[0.08]"
              )}
            >
              {user && (
                <div
                  className={cn("px-3 py-2 border-b", isDark ? "border-white/5" : "border-black/[0.06]")}
                >
                  <p className={cn("text-[13px] font-medium truncate", isDark ? "text-white/90" : "text-black/85")}>
                    {displayName}
                  </p>
                  <p className={cn("text-[11px] truncate font-mono", isDark ? "text-white/40" : "text-black/40")}>
                    {user.email}
                  </p>
                </div>
              )}
              <Link
                href="/settings"
                onClick={() => setMenuOpen(false)}
                className={cn(
                  "flex items-center gap-2.5 px-3 py-2 text-[13px] transition-colors",
                  isDark
                    ? "text-white/70 hover:bg-white/[0.05] hover:text-white"
                    : "text-black/70 hover:bg-black/[0.04] hover:text-black"
                )}
              >
                <Settings className="h-4 w-4" />
                Settings
              </Link>
              <button
                onClick={handleLogout}
                className={cn(
                  "flex w-full items-center gap-2.5 px-3 py-2 text-[13px] transition-colors",
                  isDark
                    ? "text-rose-300 hover:bg-rose-500/10"
                    : "text-rose-600 hover:bg-rose-50"
                )}
              >
                <LogOut className="h-4 w-4" />
                Log out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
