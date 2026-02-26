"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useDeal, useUpdateDeal, useDeleteDeal } from "@/hooks/use-deals";
import { LoadingState } from "@/components/shared/loading-state";
import { DealStatus } from "@/types";
import { DEAL_STATUS_LABELS } from "@/lib/constants";

export default function DealSettingsPage() {
  const params = useParams<{ dealId: string }>();
  const router = useRouter();
  const { data: deal, isLoading } = useDeal(params.dealId);
  const updateDeal = useUpdateDeal();
  const deleteDeal = useDeleteDeal();
  const [confirmDelete, setConfirmDelete] = useState(false);

  if (isLoading || !deal) {
    return <LoadingState message="Loading settings..." />;
  }

  const handleStatusChange = async (status: DealStatus) => {
    await updateDeal.mutateAsync({
      dealId: params.dealId,
      payload: { status },
    });
  };

  const handleDelete = async () => {
    await deleteDeal.mutateAsync(params.dealId);
    router.push("/deals");
  };

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <div>
        <h2 className="text-lg font-semibold">Deal Settings</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Manage deal status and configuration.
        </p>
      </div>

      {/* Status */}
      <div className="rounded-lg border bg-white p-6">
        <h3 className="font-medium">Deal Status</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Update the current status of this deal.
        </p>
        <select
          value={deal.status}
          onChange={(e) => handleStatusChange(e.target.value as DealStatus)}
          className="mt-3 w-full max-w-xs rounded-md border px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
        >
          {Object.entries(DEAL_STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>

      {/* Danger zone */}
      <div className="rounded-lg border border-red-200 bg-white p-6">
        <h3 className="font-medium text-red-600">Danger Zone</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Permanently delete this deal and all associated data.
        </p>
        {confirmDelete ? (
          <div className="mt-4 flex items-center gap-3">
            <button
              onClick={handleDelete}
              disabled={deleteDeal.isPending}
              className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
            >
              {deleteDeal.isPending ? "Deleting..." : "Confirm Delete"}
            </button>
            <button
              onClick={() => setConfirmDelete(false)}
              className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-muted"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            onClick={() => setConfirmDelete(true)}
            className="mt-4 rounded-md border border-red-300 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50"
          >
            Delete Deal
          </button>
        )}
      </div>
    </div>
  );
}
