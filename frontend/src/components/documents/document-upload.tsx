"use client";

import { useRef, useState } from "react";
import { useInitiateDocumentUpload, useConfirmDocumentUpload } from "@/hooks/use-documents";
import { formatFileSize } from "@/lib/utils";
import { Upload, X, FileText } from "lucide-react";

interface DocumentUploadProps {
  dealId: string;
}

export function DocumentUpload({ dealId }: DocumentUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const initiateUpload = useInitiateDocumentUpload();
  const confirmUpload = useConfirmDocumentUpload();

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) setFile(selected);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const dropped = e.dataTransfer.files[0];
    if (dropped) setFile(dropped);
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError("");

    try {
      const initResult = await initiateUpload.mutateAsync({
        deal_id: dealId,
        name: file.name,
        file_name: file.name,
        file_size: file.size,
        content_type: file.type,
      });

      const uploadResponse = await fetch(initResult.upload_url, {
        method: "PUT",
        body: file,
        headers: { "Content-Type": file.type },
      });
      if (!uploadResponse.ok) {
        throw new Error(`Upload to storage failed: ${uploadResponse.status}`);
      }

      await confirmUpload.mutateAsync({
        document_id: initResult.document_id,
        upload_key: initResult.upload_key,
      });

      setFile(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-3">
      {error && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-red-800">{error}</div>
      )}

      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        className="rounded-lg border-2 border-dashed p-6 text-center"
      >
        {file ? (
          <div className="flex items-center justify-center gap-3">
            <FileText className="h-8 w-8 text-primary" />
            <div className="text-left">
              <p className="text-sm font-medium">{file.name}</p>
              <p className="text-xs text-muted-foreground">{formatFileSize(file.size)}</p>
            </div>
            <button
              onClick={() => setFile(null)}
              className="ml-2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
            <button
              onClick={handleUpload}
              disabled={uploading}
              className="ml-4 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {uploading ? "Uploading..." : "Upload"}
            </button>
          </div>
        ) : (
          <div>
            <Upload className="mx-auto h-8 w-8 text-muted-foreground" />
            <p className="mt-2 text-sm text-muted-foreground">
              Drag and drop a document, or{" "}
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="text-primary hover:underline"
              >
                browse
              </button>
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Supports PDF, DOCX, XLSX, PPTX, TXT
            </p>
          </div>
        )}
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.xlsx,.pptx,.txt"
          onChange={handleFileChange}
          className="hidden"
        />
      </div>
    </div>
  );
}
