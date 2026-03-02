"use client";

import { useState, useRef } from "react";
import { useParams } from "next/navigation";
import {
  useDeliverables,
  useGenerateDeliverable,
} from "@/hooks/use-deliverables";
import type { Deliverable } from "@/hooks/use-deliverables";
import { LoadingState } from "@/components/shared/loading-state";
import {
  FileText,
  FileSpreadsheet,
  Presentation,
  Download,
  Sparkles,
  Loader2,
  Upload,
  ChevronDown,
  Check,
} from "lucide-react";

const GENERATE_OPTIONS = [
  {
    type: "investment_memo",
    label: "Investment Memo",
    format: "Word (.docx)",
    icon: FileText,
  },
  {
    type: "financial_model",
    label: "Financial Model",
    format: "Excel (.xlsx)",
    icon: FileSpreadsheet,
  },
  {
    type: "ic_presentation",
    label: "IC Presentation",
    format: "PowerPoint (.pptx)",
    icon: Presentation,
  },
];

const FORMAT_ICONS: Record<string, typeof FileText> = {
  docx: FileText,
  xlsx: FileSpreadsheet,
  pptx: Presentation,
};

const FORMAT_COLORS: Record<string, string> = {
  docx: "text-blue-600 bg-blue-50",
  xlsx: "text-emerald-600 bg-emerald-50",
  pptx: "text-orange-600 bg-orange-50",
};

function DeliverableRow({ item }: { item: Deliverable }) {
  const Icon = FORMAT_ICONS[item.file_format] || FileText;
  const colorClass = FORMAT_COLORS[item.file_format] || "text-gray-600 bg-gray-50";

  return (
    <div className="flex items-center justify-between rounded-2xl border border-[#1A1A1A]/5 bg-white p-5 transition-all hover:shadow-md">
      <div className="flex items-center gap-4">
        <div className={`rounded-xl p-3 ${colorClass}`}>
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <p className="font-heading font-bold text-sm text-primary">
            {item.title}
          </p>
          <p className="text-xs text-[#1A1A1A]/40 font-medium mt-0.5">
            {item.file_format.toUpperCase()} &middot;{" "}
            {new Date(item.created_at).toLocaleDateString()}
          </p>
        </div>
      </div>
      <button className="flex items-center gap-2 rounded-full bg-[#F2F0E9] px-4 py-2 text-xs font-bold text-primary/60 transition-all hover:bg-primary hover:text-white">
        <Download className="h-3.5 w-3.5" />
        Download
      </button>
    </div>
  );
}

export default function DeliverablesPage() {
  const params = useParams<{ dealId: string }>();
  const { data, isLoading } = useDeliverables(params.dealId);
  const generateMutation = useGenerateDeliverable();
  const [showDropdown, setShowDropdown] = useState(false);
  const [generating, setGenerating] = useState<string | null>(null);
  const [exampleFile, setExampleFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const deliverables = data?.items ?? [];

  const handleGenerate = async (type: string) => {
    setShowDropdown(false);
    setGenerating(type);
    try {
      await generateMutation.mutateAsync({ dealId: params.dealId, type });
    } finally {
      setTimeout(() => setGenerating(null), 500);
    }
  };

  const handleExampleUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) setExampleFile(file);
  };

  if (isLoading) {
    return <LoadingState message="Loading deliverables..." />;
  }

  return (
    <div className="space-y-8 antialiased">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-heading font-extrabold text-primary">
            Deliverables
          </h2>
          <p className="text-sm text-[#1A1A1A]/50 font-medium mt-1">
            AI-generated documents based on meeting transcripts and uploaded
            materials.
          </p>
        </div>

        {/* Generate button */}
        <div className="relative">
          <button
            onClick={() => setShowDropdown(!showDropdown)}
            disabled={!!generating}
            className="flex items-center gap-2 rounded-full bg-accent px-5 py-2.5 text-sm font-bold text-white shadow-lg shadow-accent/20 transition-all hover:shadow-xl disabled:opacity-60"
          >
            {generating ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            {generating ? "Generating..." : "Generate"}
            {!generating && <ChevronDown className="h-3.5 w-3.5" />}
          </button>

          {showDropdown && (
            <div className="absolute right-0 top-full mt-2 w-72 rounded-2xl border border-[#1A1A1A]/10 bg-white p-2 shadow-xl z-50">
              {GENERATE_OPTIONS.map((opt) => {
                const Icon = opt.icon;
                return (
                  <button
                    key={opt.type}
                    onClick={() => handleGenerate(opt.type)}
                    className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-left transition-colors hover:bg-[#F2F0E9]"
                  >
                    <Icon className="h-5 w-5 text-[#1A1A1A]/40" />
                    <div>
                      <p className="text-sm font-bold text-primary">
                        {opt.label}
                      </p>
                      <p className="text-[11px] text-[#1A1A1A]/40">
                        {opt.format}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Example doc upload */}
      <div className="rounded-2xl border border-dashed border-[#1A1A1A]/10 bg-[#F2F0E9]/30 p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-white p-3 border border-[#1A1A1A]/5">
              <Upload className="h-5 w-5 text-[#1A1A1A]/30" />
            </div>
            <div>
              <p className="text-sm font-bold text-primary">
                Example Document (Style Reference)
              </p>
              <p className="text-xs text-[#1A1A1A]/40 mt-0.5">
                Upload a presentation, model, or memo as a formatting template
                for generated deliverables.
              </p>
            </div>
          </div>
          {exampleFile ? (
            <div className="flex items-center gap-2 rounded-full bg-emerald-50 px-4 py-2 text-xs font-bold text-emerald-700">
              <Check className="h-3.5 w-3.5" />
              {exampleFile.name}
            </div>
          ) : (
            <button
              onClick={() => fileInputRef.current?.click()}
              className="rounded-full border border-[#1A1A1A]/10 bg-white px-4 py-2 text-xs font-bold text-[#1A1A1A]/60 transition-all hover:border-accent hover:text-accent"
            >
              Upload Template
            </button>
          )}
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            accept=".pptx,.xlsx,.docx,.pdf"
            onChange={handleExampleUpload}
          />
        </div>
      </div>

      {/* Generating indicator */}
      {generating && (
        <div className="flex items-center gap-3 rounded-2xl border border-accent/20 bg-accent/5 p-5">
          <Loader2 className="h-5 w-5 animate-spin text-accent" />
          <div>
            <p className="text-sm font-bold text-accent">
              Generating{" "}
              {GENERATE_OPTIONS.find((o) => o.type === generating)?.label}...
            </p>
            <p className="text-xs text-[#1A1A1A]/40 mt-0.5">
              Analyzing transcripts and documents to produce your deliverable.
            </p>
          </div>
        </div>
      )}

      {/* Deliverables list */}
      {deliverables.length === 0 && !generating ? (
        <div className="rounded-2xl border border-[#1A1A1A]/5 bg-white p-12 text-center">
          <Sparkles className="mx-auto h-8 w-8 text-[#1A1A1A]/20" />
          <p className="mt-3 text-sm font-bold text-primary/60">
            No deliverables yet
          </p>
          <p className="mt-1 text-xs text-[#1A1A1A]/40">
            Click Generate to create investment memos, financial models, or
            presentations from your meeting data.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {deliverables.map((item) => (
            <DeliverableRow key={item.id} item={item} />
          ))}
        </div>
      )}
    </div>
  );
}
