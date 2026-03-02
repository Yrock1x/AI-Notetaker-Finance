"use client";

import { useState, useRef } from "react";
import { useInitiateMeetingUpload, useConfirmMeetingUpload } from "@/hooks/use-meetings";
import { CallType } from "@/types";
import { CALL_TYPE_LABELS } from "@/lib/constants";
import { formatFileSize } from "@/lib/utils";
import { Upload, X, FileAudio } from "lucide-react";

interface UploadDialogProps {
  dealId: string;
  open: boolean;
  onClose: () => void;
}

const ACCEPTED_TYPES = [
  "audio/mpeg",
  "audio/wav",
  "audio/mp4",
  "audio/webm",
  "video/mp4",
  "video/webm",
  "video/quicktime",
];

export function UploadDialog({ dealId, open, onClose }: UploadDialogProps) {
  const [title, setTitle] = useState("");
  const [callType, setCallType] = useState<CallType>(CallType.OTHER);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const initiateUpload = useInitiateMeetingUpload();
  const confirmUpload = useConfirmMeetingUpload();

  if (!open) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) {
      if (!ACCEPTED_TYPES.includes(selected.type)) {
        setError("Unsupported file type. Please upload an audio or video file.");
        return;
      }
      setError("");
      setFile(selected);
      if (!title) {
        setTitle(selected.name.replace(/\.[^/.]+$/, ""));
      }
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const dropped = e.dataTransfer.files[0];
    if (dropped) {
      if (!ACCEPTED_TYPES.includes(dropped.type)) {
        setError("Unsupported file type. Please upload an audio or video file.");
        return;
      }
      setError("");
      setFile(dropped);
      if (!title) {
        setTitle(dropped.name.replace(/\.[^/.]+$/, ""));
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !title) return;

    setUploading(true);
    setError("");

    try {
      // Step 1: Get presigned upload URL
      const initResult = await initiateUpload.mutateAsync({
        deal_id: dealId,
        title,
        call_type: callType,
        file_name: file.name,
        file_size: file.size,
        content_type: file.type,
      });

      // Step 2: Upload file directly to S3
      const uploadResponse = await fetch(initResult.upload_url, {
        method: "PUT",
        body: file,
        headers: { "Content-Type": file.type },
      });
      if (!uploadResponse.ok) {
        throw new Error(`Upload to storage failed: ${uploadResponse.status}`);
      }

      // Step 3: Confirm upload
      await confirmUpload.mutateAsync({
        meeting_id: initResult.meeting_id,
        upload_key: initResult.upload_key,
      });

      // Reset and close
      setTitle("");
      setCallType(CallType.OTHER);
      setFile(null);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const reset = () => {
    setTitle("");
    setCallType(CallType.OTHER);
    setFile(null);
    setError("");
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="mx-4 w-full max-w-lg rounded-lg bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Upload Meeting Recording</h2>
          <button onClick={reset} className="text-muted-foreground hover:text-foreground">
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          {error && (
            <div className="rounded-md bg-red-50 p-3 text-sm text-red-800">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium" htmlFor="upload-title">
              Meeting Title *
            </label>
            <input
              id="upload-title"
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g., Management Presentation - Acme Corp"
              className="mt-1 w-full rounded-md border px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>

          <div>
            <label className="block text-sm font-medium" htmlFor="upload-call-type">
              Call Type *
            </label>
            <select
              id="upload-call-type"
              value={callType}
              onChange={(e) => setCallType(e.target.value as CallType)}
              className="mt-1 w-full rounded-md border px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            >
              {Object.entries(CALL_TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            className="rounded-lg border-2 border-dashed p-6 text-center"
          >
            {file ? (
              <div className="flex items-center justify-center gap-3">
                <FileAudio className="h-8 w-8 text-primary" />
                <div className="text-left">
                  <p className="text-sm font-medium">{file.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatFileSize(file.size)}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setFile(null)}
                  className="ml-2 text-muted-foreground hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <div>
                <Upload className="mx-auto h-8 w-8 text-muted-foreground" />
                <p className="mt-2 text-sm text-muted-foreground">
                  Drag and drop a recording file, or{" "}
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="text-primary hover:underline"
                  >
                    browse
                  </button>
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Supports MP3, WAV, MP4, WebM, MOV
                </p>
              </div>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_TYPES.join(",")}
              onChange={handleFileChange}
              className="hidden"
            />
          </div>

          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={reset}
              className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-muted"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={uploading || !file || !title}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {uploading ? "Uploading..." : "Upload"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
