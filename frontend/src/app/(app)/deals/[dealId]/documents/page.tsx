"use client";

import { useParams } from "next/navigation";
import { useDocuments } from "@/hooks/use-documents";
import { DocumentUpload } from "@/components/documents/document-upload";
import { DocumentList } from "@/components/documents/document-list";
import { LoadingState } from "@/components/shared/loading-state";
import { EmptyState } from "@/components/shared/empty-state";

export default function DocumentsPage() {
  const params = useParams<{ dealId: string }>();
  const { data, isLoading } = useDocuments(params.dealId);

  const documents = Array.isArray(data) ? data : data?.items ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Documents</h2>
      </div>

      <DocumentUpload dealId={params.dealId} />

      {isLoading ? (
        <LoadingState message="Loading documents..." />
      ) : documents.length === 0 ? (
        <EmptyState
          title="No documents yet"
          description="Upload documents to include them in the deal's knowledge base for Q&A."
        />
      ) : (
        <DocumentList documents={documents} />
      )}
    </div>
  );
}
