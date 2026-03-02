"use client";

import { useState } from "react";
import type { DealCreate } from "@/types";
import { DealType } from "@/types";

const DEAL_TYPE_OPTIONS = [
  { value: DealType.BUYOUT, label: "Buyout" },
  { value: DealType.GROWTH_EQUITY, label: "Growth Equity" },
  { value: DealType.VENTURE, label: "Venture" },
  { value: DealType.RECAPITALIZATION, label: "Recapitalization" },
  { value: DealType.ADD_ON, label: "Add-on" },
  { value: DealType.OTHER, label: "Other" },
];

interface DealFormProps {
  onSubmit: (data: DealCreate) => void;
  initialData?: Partial<DealCreate>;
  isSubmitting?: boolean;
  error?: string;
}

export function DealForm({ onSubmit, initialData, isSubmitting, error }: DealFormProps) {
  const [name, setName] = useState(initialData?.name ?? "");
  const [targetCompany, setTargetCompany] = useState(initialData?.target_company ?? "");
  const [dealType, setDealType] = useState<DealType>(
    initialData?.deal_type ?? DealType.BUYOUT
  );
  const [description, setDescription] = useState(initialData?.description ?? "");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      name,
      target_company: targetCompany || undefined,
      deal_type: dealType,
      description: description || undefined,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-red-800">
          {error}
        </div>
      )}

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium" htmlFor="name">
            Deal Name *
          </label>
          <input
            id="name"
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., Project Alpha"
            className="mt-1 w-full rounded-md border px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>

        <div>
          <label className="block text-sm font-medium" htmlFor="company">
            Target Company
          </label>
          <input
            id="company"
            type="text"
            value={targetCompany}
            onChange={(e) => setTargetCompany(e.target.value)}
            placeholder="e.g., Acme Corp"
            className="mt-1 w-full rounded-md border px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>

        <div>
          <label className="block text-sm font-medium" htmlFor="dealType">
            Deal Type *
          </label>
          <select
            id="dealType"
            value={dealType}
            onChange={(e) => setDealType(e.target.value as DealType)}
            className="mt-1 w-full rounded-md border px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          >
            {DEAL_TYPE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium" htmlFor="description">
            Description
          </label>
          <textarea
            id="description"
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Brief description of the deal..."
            className="mt-1 w-full rounded-md border px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
      </div>

      <div className="flex justify-end gap-3">
        <button
          type="button"
          onClick={() => window.history.back()}
          className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-muted"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={isSubmitting || !name}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {isSubmitting ? "Creating..." : "Create Deal"}
        </button>
      </div>
    </form>
  );
}
