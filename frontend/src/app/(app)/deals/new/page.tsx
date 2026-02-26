"use client";

import { useRouter } from "next/navigation";
import { DealForm } from "@/components/deals/deal-form";
import { useCreateDeal } from "@/hooks/use-deals";
import type { DealCreate } from "@/types";

export default function CreateDealPage() {
  const router = useRouter();
  const createDeal = useCreateDeal();

  const handleSubmit = async (data: DealCreate) => {
    const deal = await createDeal.mutateAsync(data);
    router.push(`/deals/${deal.id}`);
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Create Deal</h1>
        <p className="mt-1 text-muted-foreground">
          Set up a new deal workspace for your team.
        </p>
      </div>

      <DealForm
        onSubmit={handleSubmit}
        isSubmitting={createDeal.isPending}
        error={createDeal.error?.message}
      />
    </div>
  );
}
