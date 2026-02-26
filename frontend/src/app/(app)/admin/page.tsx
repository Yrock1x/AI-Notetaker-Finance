"use client";

import Link from "next/link";
import { Users, Shield, FileText } from "lucide-react";

export default function AdminPage() {
  const adminSections = [
    {
      title: "Users",
      description: "Manage organization members and permissions",
      href: "/admin/users",
      icon: Users,
    },
    {
      title: "Audit Logs",
      description: "View activity history and security events",
      href: "/admin/audit",
      icon: FileText,
    },
    {
      title: "Settings",
      description: "Configure organization-wide settings",
      href: "/admin/settings",
      icon: Shield,
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Administration</h1>
        <p className="mt-1 text-muted-foreground">
          Manage your organization settings and users.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {adminSections.map((section) => (
          <Link
            key={section.href}
            href={section.href}
            className="group rounded-lg border bg-white p-6 transition-shadow hover:shadow-md"
          >
            <section.icon className="h-8 w-8 text-primary" />
            <h3 className="mt-3 font-semibold group-hover:text-primary">
              {section.title}
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {section.description}
            </p>
          </Link>
        ))}
      </div>
    </div>
  );
}
