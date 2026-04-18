"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { OrgSwitcher } from "./org-switcher";
import { Breadcrumbs } from "./breadcrumbs";
import { Settings, LogOut } from "lucide-react";

export function Topbar() {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const router = useRouter();

  const initial = user?.full_name?.charAt(0)?.toUpperCase() ?? "U";

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    if (menuOpen) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [menuOpen]);

  const handleLogout = () => {
    setMenuOpen(false);
    logout();
    router.push("/login");
  };

  return (
    <header className="flex h-24 items-center justify-between border-b border-[#1A1A1A]/5 px-10 bg-[#F2F0E9]/80 backdrop-blur-xl relative z-20 antialiased">
      <div className="flex items-center gap-6">
        <Breadcrumbs />
      </div>
      <div className="flex items-center gap-6">
        <div className="hidden md:flex items-center gap-2 px-4 py-2 bg-white/50 rounded-full border border-[#1A1A1A]/5 shadow-sm">
          <OrgSwitcher />
        </div>
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="magnetic-btn group flex h-12 w-12 items-center justify-center rounded-full bg-primary text-white text-sm font-heading font-extrabold shadow-lg overflow-hidden relative cursor-pointer"
          >
            <span className="relative z-10 transition-transform group-hover:scale-110">{initial}</span>
            <div className="absolute inset-0 bg-accent translate-y-full group-hover:translate-y-0 transition-transform duration-300"></div>
          </button>
          {menuOpen && (
            <div className="absolute right-0 top-full mt-2 w-48 rounded-xl border border-[#1A1A1A]/10 bg-white py-1 shadow-xl z-50">
              {user && (
                <div className="px-4 py-2 border-b border-[#1A1A1A]/5">
                  <p className="text-sm font-bold text-primary truncate">{user.full_name}</p>
                  <p className="text-xs text-[#1A1A1A]/40 truncate">{user.email}</p>
                </div>
              )}
              <Link
                href="/settings"
                onClick={() => setMenuOpen(false)}
                className="flex items-center gap-3 px-4 py-2.5 text-sm font-medium text-[#1A1A1A]/70 hover:bg-[#F2F0E9] transition-colors"
              >
                <Settings className="h-4 w-4" />
                Settings
              </Link>
              <button
                onClick={handleLogout}
                className="flex w-full items-center gap-3 px-4 py-2.5 text-sm font-medium text-red-600 hover:bg-red-50 transition-colors"
              >
                <LogOut className="h-4 w-4" />
                Log Out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
