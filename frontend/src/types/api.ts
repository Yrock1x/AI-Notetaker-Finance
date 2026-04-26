import { CallType, DealRole, DealStatus, DealType, MeetingSource } from "./enums";

// Generic paginated response (cursor-based)
export interface PaginatedResponse<T> {
  items: T[];
  cursor: string | null;
  has_more: boolean;
}

// API error
export interface ApiError {
  detail: string;
  status_code: number;
  errors?: Record<string, string[]>;
}

// Deal requests
export interface DealCreate {
  name: string;
  target_company?: string;
  deal_type: DealType;
  description?: string;
  stage?: string;
}

export interface DealUpdate {
  name?: string;
  target_company?: string;
  deal_type?: DealType;
  status?: DealStatus;
  description?: string;
  stage?: string;
}

export interface DealFilters {
  search?: string;
  status?: string;
  deal_type?: string;
  cursor?: string;
  limit?: number;
}

// Deal member requests — either user_id (existing user) or email (invite flow)
export interface DealMemberAdd {
  user_id?: string;
  email?: string;
  role: DealRole;
}

// Meeting requests
export interface MeetingCreate {
  title: string;
  call_type: CallType;
  source: MeetingSource;
  scheduled_at?: string;
  participants?: string[];
  metadata?: Record<string, unknown>;
}

// Meeting upload ticket — worker mints a Supabase Storage signed PUT URL.
// The frontend then inserts the `meetings` row directly via supabase-js and
// fires the `meeting/uploaded` Inngest event.
export interface MeetingUploadInitiate {
  deal_id: string;
  filename: string;
  content_type: string;
  // file.size from the browser File API. The worker rejects above-cap
  // requests before consuming a signed-URL slot.
  size_bytes: number;
}

export interface MeetingUploadInitiateResponse {
  file_key: string;
  upload_url: string;
  token: string;
}

// Analysis requests
export interface AnalysisRequest {
  call_type: CallType;
  force_rerun?: boolean;
}

// Q&A requests
export interface QARequest {
  question: string;
  include_meeting_ids?: string[];
  include_document_ids?: string[];
}

export interface QAResponse {
  id: string;
  deal_id: string;
  question: string;
  answer: string;
  citations: Array<{
    source_type: string;
    source_id: string;
    source_title: string;
    text_excerpt: string;
    timestamp?: number;
    page?: number;
  }>;
  grounding_score?: number;
  model_used: string;
  created_at: string;
}

// Document requests
export interface DocumentCreate {
  name: string;
  file_type: string;
  file_size: number;
  content_type: string;
  metadata?: Record<string, unknown>;
}

// Deal-document upload — signed Supabase Storage PUT URL.
export interface DocumentUploadInitiate {
  deal_id: string;
  filename: string;
  content_type: string;
}

export interface DocumentUploadInitiateResponse {
  file_key: string;
  upload_url: string;
  token: string;
}

// Transcript filters
export interface TranscriptSegmentFilters {
  speaker_label?: string;
  start_time?: number;
  end_time?: number;
  page?: number;
  page_size?: number;
}

// Auth types
export interface LoginRequest {
  email: string;
  password: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  token_type: string;
}
