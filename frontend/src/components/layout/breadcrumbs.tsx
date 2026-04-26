"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight } from "lucide-react";
import { useDeals } from "@/hooks/use-deals";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function Breadcrumbs() {
  const pathname = usePathname();
  const segments = pathname.split("/").filter(Boolean);
  const { data: dealsData } = useDeals();
  const dealsById = new Map((dealsData?.items ?? []).map((d) => [d.id, d.name]));

  if (segments.length === 0) return null;

  return (
    <nav className="flex items-center gap-1 text-[13px]">
      {segments.map((segment, index) => {
        const href = "/" + segments.slice(0, index + 1).join("/");
        const isLast = index === segments.length - 1;
        const prev = segments[index - 1];

        let label: string;
        if (UUID_RE.test(segment) && (prev === "deals" || prev === "meetings")) {
          label = dealsById.get(segment) ?? "—";
        } else {
          label = segment.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
        }

        return (
          <span key={href} className="flex items-center gap-1">
            {index > 0 && <ChevronRight className="h-3 w-3 text-muted-foreground" />}
            {isLast ? (
              <span className="font-medium text-foreground">{label}</span>
            ) : (
              <Link href={href} className="text-muted-foreground hover:text-foreground transition-colors">
                {label}
              </Link>
            )}
          </span>
        );
      })}
    </nav>
  );
}
