"use client";

import { useState, useEffect } from "react";
import apiClient from "@/lib/api-client";
import { LoadingState } from "@/components/shared/loading-state";
import { EmptyState } from "@/components/shared/empty-state";
import type { AuditLog } from "@/types";

export default function AuditLogsPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState("");

  useEffect(() => {
    async function fetchLogs() {
      setLoading(true);
      try {
        const { data } = await apiClient.get("/admin/audit-logs", {
          params: { action: actionFilter || undefined },
        });
        setLogs(data.items ?? []);
      } catch {
        setLogs([]);
      } finally {
        setLoading(false);
      }
    }
    fetchLogs();
  }, [actionFilter]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Audit Logs</h1>
        <p className="mt-1 text-muted-foreground">
          View organization activity history.
        </p>
      </div>

      <div>
        <select
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          className="rounded-md border bg-white px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
        >
          <option value="">All Actions</option>
          <option value="create">Create</option>
          <option value="update">Update</option>
          <option value="delete">Delete</option>
        </select>
      </div>

      {loading ? (
        <LoadingState message="Loading audit logs..." />
      ) : logs.length === 0 ? (
        <EmptyState title="No audit logs" description="No activity to display." />
      ) : (
        <div className="rounded-lg border bg-white">
          <table className="w-full">
            <thead>
              <tr className="border-b text-left text-sm text-muted-foreground">
                <th className="px-4 py-3 font-medium">Action</th>
                <th className="px-4 py-3 font-medium">Resource</th>
                <th className="px-4 py-3 font-medium">User</th>
                <th className="px-4 py-3 font-medium">IP Address</th>
                <th className="px-4 py-3 font-medium">Time</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr
                  key={log.id}
                  className="border-b last:border-0 hover:bg-muted/50"
                >
                  <td className="px-4 py-3">
                    <span className="rounded bg-muted px-2 py-0.5 text-xs font-mono">
                      {log.action}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm">
                    {log.resource_type}
                    {log.resource_id && (
                      <span className="ml-1 text-xs text-muted-foreground">
                        ({log.resource_id.slice(0, 8)}...)
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">
                    {log.user_id.slice(0, 8)}...
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">
                    {log.ip_address ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">
                    {new Date(log.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
