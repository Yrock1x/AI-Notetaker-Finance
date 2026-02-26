"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useAnalyses, useRunAnalysis } from "@/hooks/use-analysis";
import { AnalysisPanel } from "@/components/analysis/analysis-panel";
import { CallTypeSelector } from "@/components/analysis/call-type-selector";
import { LoadingState } from "@/components/shared/loading-state";
import { EmptyState } from "@/components/shared/empty-state";
import { ArrowLeft, Play } from "lucide-react";
import { useState } from "react";
import { CallType } from "@/types";

export default function AnalysisPage() {
  const params = useParams<{ dealId: string; meetingId: string }>();
  const { data: analyses, isLoading } = useAnalyses(params.meetingId);
  const runAnalysis = useRunAnalysis();
  const [selectedCallType, setSelectedCallType] = useState<CallType>(
    CallType.MANAGEMENT_PRESENTATION
  );

  const handleRunAnalysis = async () => {
    await runAnalysis.mutateAsync({
      meetingId: params.meetingId,
      payload: { call_type: selectedCallType },
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <Link
          href={`/deals/${params.dealId}/meetings/${params.meetingId}`}
          className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-3 w-3" />
          Back to meeting
        </Link>
        <h1 className="text-2xl font-bold">Meeting Analysis</h1>
      </div>

      <div className="flex items-center gap-3 rounded-lg border bg-white p-4">
        <CallTypeSelector
          value={selectedCallType}
          onChange={setSelectedCallType}
        />
        <button
          onClick={handleRunAnalysis}
          disabled={runAnalysis.isPending}
          className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          <Play className="h-4 w-4" />
          {runAnalysis.isPending ? "Running..." : "Run Analysis"}
        </button>
      </div>

      {isLoading ? (
        <LoadingState message="Loading analyses..." />
      ) : !analyses || analyses.length === 0 ? (
        <EmptyState
          title="No analyses yet"
          description="Select a call type and run an analysis to get AI-generated insights from this meeting."
        />
      ) : (
        <div className="space-y-4">
          {analyses.map((analysis) => (
            <AnalysisPanel key={analysis.id} analysis={analysis} />
          ))}
        </div>
      )}
    </div>
  );
}
