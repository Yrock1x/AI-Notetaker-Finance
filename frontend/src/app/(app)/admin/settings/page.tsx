"use client";

import { useState, useEffect } from "react";
import apiClient from "@/lib/api-client";
import { LoadingState } from "@/components/shared/loading-state";

export default function AdminSettingsPage() {
  const [settings, setSettings] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    async function fetchSettings() {
      try {
        const { data } = await apiClient.get("/admin/settings");
        setSettings(data);
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    }
    fetchSettings();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const { data } = await apiClient.patch("/admin/settings", settings);
      setSettings(data);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <LoadingState message="Loading settings..." />;
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Organization Settings</h1>
        <p className="mt-1 text-muted-foreground">
          Configure organization-wide preferences.
        </p>
      </div>

      <div className="rounded-lg border bg-white p-6">
        <h3 className="font-medium">Settings</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Organization settings are stored as key-value pairs.
        </p>
        <pre className="mt-4 rounded bg-muted p-4 text-sm overflow-auto">
          {JSON.stringify(settings, null, 2)}
        </pre>
      </div>

      <div className="flex justify-end">
        <button
          onClick={handleSave}
          disabled={saving}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {saving ? "Saving..." : "Save Settings"}
        </button>
      </div>
    </div>
  );
}
