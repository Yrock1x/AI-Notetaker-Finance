"use client";

// Direct-to-Supabase document CRUD. Uploads go to a Supabase Storage bucket
// named `deal-documents`; the browser does the PUT directly with a signed
// upload URL minted server-side.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  Document,
  DocumentUploadInitiate,
  DocumentUploadInitiateResponse,
  PaginatedResponse,
} from "@/types";
import { getBrowserSupabase } from "@/lib/supabase/browser";

const DOCUMENTS_KEY = "documents";
const DOCUMENTS_BUCKET = "deal-documents";

export function useDocuments(dealId: string | undefined) {
  return useQuery<PaginatedResponse<Document>>({
    queryKey: [DOCUMENTS_KEY, dealId],
    queryFn: async () => {
      const supabase = getBrowserSupabase();
      const { data, error } = await supabase
        .from("documents")
        .select("*")
        .eq("deal_id", dealId!)
        .order("created_at", { ascending: false });
      if (error) throw error;
      return {
        items: (data ?? []) as Document[],
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
    queryFn: async () => {
      const supabase = getBrowserSupabase();
      const { data, error } = await supabase
        .from("documents")
        .select("*")
        .eq("id", documentId!)
        .single();
      if (error) throw error;
      return data as Document;
    },
    enabled: !!documentId,
  });
}

export function useInitiateDocumentUpload() {
  return useMutation({
    mutationFn: async (payload: DocumentUploadInitiate) => {
      const supabase = getBrowserSupabase();
      const key = `${payload.deal_id}/${crypto.randomUUID()}-${payload.filename}`;
      const { data, error } = await supabase.storage
        .from(DOCUMENTS_BUCKET)
        .createSignedUploadUrl(key);
      if (error) throw error;
      return {
        file_key: key,
        upload_url: data.signedUrl,
        token: data.token,
      } as DocumentUploadInitiateResponse;
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
      const supabase = getBrowserSupabase();
      const { data: auth } = await supabase.auth.getUser();
      if (!auth.user) throw new Error("Not authenticated");

      const { data: deal, error: dealErr } = await supabase
        .from("deals")
        .select("org_id")
        .eq("id", payload.deal_id)
        .single();
      if (dealErr) throw dealErr;

      const { data, error } = await supabase
        .from("documents")
        .insert({
          org_id: deal.org_id,
          deal_id: payload.deal_id,
          title: payload.title,
          document_type: payload.document_type,
          file_key: payload.file_key,
          file_size: payload.file_size,
          uploaded_by: auth.user.id,
        })
        .select()
        .single();
      if (error) throw error;

      await fetch("/api/inngest/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: "document/uploaded",
          data: { document_id: data.id, deal_id: payload.deal_id },
        }),
      });

      return data as Document;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [DOCUMENTS_KEY] });
    },
  });
}
