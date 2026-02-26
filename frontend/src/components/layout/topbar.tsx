"use client";

import { OrgSwitcher } from "./org-switcher";
import { Breadcrumbs } from "./breadcrumbs";

export function Topbar() {
  return (
    <header className="flex h-14 items-center justify-between border-b px-6">
      <Breadcrumbs />
      <div className="flex items-center gap-4">
        <OrgSwitcher />
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-medium text-primary-foreground">
          U
        </div>
      </div>
    </header>
  );
}
