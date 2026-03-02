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
      <nav className="mb-6 border-b">
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
      {children}
    </div>
  );
}
