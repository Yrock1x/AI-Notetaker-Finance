"use client";

import Link from "next/link";
import { usePathname, useParams } from "next/navigation";
import { cn } from "@/lib/utils";

const tabs = [
  { label: "Overview", href: "" },
  { label: "Meetings", href: "/meetings" },
  { label: "Documents", href: "/documents" },
  { label: "Deliverables", href: "/deliverables" },
  { label: "Q&A", href: "/qa" },
  { label: "Team", href: "/team" },
  { label: "Settings", href: "/settings" },
];

export default function DealLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const params = useParams<{ dealId: string }>();
  const basePath = `/deals/${params.dealId}`;

  return (
    <div>
      {/*
        Sticky tab bar so the deal header can scroll away and leave the
        whole viewport for tab content. The nearest scroll ancestor is
        the app-shell <main className="overflow-auto p-10 md:p-14"> so
        top:0 anchors to the inside of that container. We bleed the nav
        horizontally into <main>'s padding (negative margins + matching
        padding) so the underline + background reach edge-to-edge and
        don't look like a floating pill.
      */}
      <nav className="sticky top-0 z-10 -mx-10 border-b bg-background px-10 md:-mx-14 md:px-14">
        <div className="flex space-x-4">
          {tabs.map((tab) => {
            const tabPath = `${basePath}${tab.href}`;
            const isActive =
              tab.href === ""
                ? pathname === basePath
                : pathname.startsWith(tabPath);

            return (
              <Link
                key={tab.label}
                href={tabPath}
                className={cn(
                  "border-b-2 px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                )}
              >
                {tab.label}
              </Link>
            );
          })}
        </div>
      </nav>
      <div className="pt-6">{children}</div>
    </div>
  );
}
