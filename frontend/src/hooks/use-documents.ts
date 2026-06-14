"use client";

// Document CRUD via the worker REST API (cookie-authenticated). Uploads use
// the worker storage upload-ticket (bucket `deal-documents`): mint a ticket,
// PUT the bytes, then POST the document row.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  Document,
  DocumentUploadInitiate,
  DocumentUploadInitiateResponse,
  PaginatedResponse,
} from "@/types";
import { apiGet, apiPost } from "@/lib/worker-api";
import { sendInngestEvent } from "@/lib/inngest-send";

const DOCUMENTS_KEY = "documents";
const DOCUMENTS_BUCKET = "deal-documents";

export function useDocuments(dealId: string | undefined) {
  return useQuery<PaginatedResponse<Document>>({
    queryKey: [DOCUMENTS_KEY, dealId],
    queryFn: async () => {
      const items = await apiGet<Document[]>(`/deals/${dealId}/documents`);
      return {
        items,
        cursor: null,
        has_more: false,
      };
    },
    enabled: !!dealId,
  });
}

export function useDocument(
  _dealId: string | undefined,
  documentId: string | undefined
) {
  return useQuery<Document>({
    queryKey: [DOCUMENTS_KEY, documentId],
    queryFn: async () => apiGet<Document>(`/documents/${documentId}`),
    enabled: !!documentId,
  });
}

// Storage ticket shape from POST /storage/upload-ticket.
interface UploadTicket {
  bucket: string;
  key: string;
  upload_url: string;
  method: string;
}

export function useInitiateDocumentUpload() {
  return useMutation({
    mutationFn: async (
      payload: DocumentUploadInitiate
    ): Promise<DocumentUploadInitiateResponse> => {
      const ticket = await apiPost<UploadTicket>("/storage/upload-ticket", {
        bucket: DOCUMENTS_BUCKET,
        deal_id: payload.deal_id,
        filename: payload.filename,
      });
      return {
        file_key: ticket.key,
        upload_url: ticket.upload_url,
        token: "",
      };
    },
  });
}

export interface ConfirmDocumentUploadPayload {
  deal_id: string;
  file_key: string;
  title: string;
  document_type: string;
  file_size: number;
}

export function useConfirmDocumentUpload() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: ConfirmDocumentUploadPayload) => {
      const doc = await apiPost<Document>(
        `/deals/${payload.deal_id}/documents`,
        {
          title: payload.title,
          document_type: payload.document_type,
          file_key: payload.file_key,
          file_size: payload.file_size,
        }
      );

      await sendInngestEvent("document/uploaded", {
        document_id: doc.id,
        deal_id: payload.deal_id,
      });

      return doc;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [DOCUMENTS_KEY] });
    },
  });
}
