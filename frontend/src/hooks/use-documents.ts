import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import type {
  Document,
  DocumentUploadInitiate,
  DocumentUploadConfirm,
  DocumentUploadInitiateResponse,
  PaginatedResponse,
} from "@/types";

const DOCUMENTS_KEY = "documents";

export function useDocuments(dealId: string | undefined) {
  return useQuery({
    queryKey: [DOCUMENTS_KEY, dealId],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<Document>>(
        `/deals/${dealId}/documents`
      );
      return data;
    },
    enabled: !!dealId,
  });
}

export function useDocument(
  dealId: string | undefined,
  documentId: string | undefined
) {
  return useQuery({
    queryKey: [DOCUMENTS_KEY, dealId, documentId],
    queryFn: async () => {
      const { data } = await apiClient.get<Document>(
        `/deals/${dealId}/documents/${documentId}`
      );
      return data;
    },
    enabled: !!dealId && !!documentId,
  });
}

export function useInitiateDocumentUpload() {
  return useMutation({
    mutationFn: async (payload: DocumentUploadInitiate) => {
      const { data } = await apiClient.post<DocumentUploadInitiateResponse>(
        `/deals/${payload.deal_id}/documents/upload/initiate`,
        payload
      );
      return data;
    },
  });
}

export function useConfirmDocumentUpload() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: DocumentUploadConfirm) => {
      const { data } = await apiClient.post<Document>(
        `/documents/${payload.document_id}/upload/confirm`,
        payload
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [DOCUMENTS_KEY] });
    },
  });
}
