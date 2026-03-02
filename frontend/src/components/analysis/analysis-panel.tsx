"use client";

import type { Analysis } from "@/types";
import { CALL_TYPE_LABELS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { BarChart3, CheckCircle, Clock, AlertCircle } from "lucide-react";
import { useState } from "react";

interface AnalysisPanelProps {
  analysis: Analysis;
}

const STATUS_CONFIG: Record<string, { icon: typeof CheckCircle; color: string; label: string }> = {
  completed: { icon: CheckCircle, color: "text-green-600", label: "Completed" },
  running: { icon: Clock, color: "text-yellow-600", label: "Running" },
  failed: { icon: AlertCircle, color: "text-red-600", label: "Failed" },
};

export function AnalysisPanel({ analysis }: AnalysisPanelProps) {
  const [expanded, setExpanded] = useState(true);
  const config = STATUS_CONFIG[analysis.status] ?? STATUS_CONFIG.completed;
  const StatusIcon = config.icon;

  return (
    <div className="rounded-lg border bg-white">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between p-4 text-left"
      >
        <div className="flex items-center gap-3">
          <BarChart3 className="h-5 w-5 text-primary" />
          <div>
            <h3 className="font-semibold">
              {CALL_TYPE_LABELS[analysis.call_type] ?? analysis.call_type}
            </h3>
            <p className="text-xs text-muted-foreground">
              {new Date(analysis.created_at).toLocaleString()} · {analysis.model_version}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <StatusIcon className={cn("h-4 w-4", config.color)} />
          <span className={cn("text-sm", config.color)}>{config.label}</span>
        </div>
      </button>

      {expanded && analysis.result && (
        <div className="border-t px-4 py-4">
          <AnalysisResult data={analysis.result} />
        </div>
      )}
    </div>
  );
}

function AnalysisResult({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="space-y-4">
      {Object.entries(data).map(([key, value]) => (
        <div key={key}>
          <h4 className="mb-1 text-sm font-semibold capitalize">
            {key.replace(/_/g, " ")}
          </h4>
          {typeof value === "string" ? (
            <p className="text-sm text-muted-foreground whitespace-pre-wrap">{value}</p>
          ) : Array.isArray(value) ? (
            <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
              {value.map((item, i) => (
                <li key={i}>{typeof item === "string" ? item : JSON.stringify(item)}</li>
              ))}
            </ul>
          ) : (
            <pre className="rounded bg-muted p-2 text-xs overflow-auto">
              {JSON.stringify(value, null, 2)}
            </pre>
          )}
        </div>
      ))}
    </div>
  );
}
