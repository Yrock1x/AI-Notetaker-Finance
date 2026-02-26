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
  status?: DealStatus;
  deal_type?: DealType;
  search?: string;
  page?: number;
  page_size?: number;
}

// Deal member requests
export interface DealMemberAdd {
  user_id: string;
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

export interface MeetingUploadInitiate {
  deal_id: string;
  title: string;
  call_type: CallType;
  file_name: string;
  file_size: number;
  content_type: string;
}

export interface MeetingUploadConfirm {
  meeting_id: string;
  upload_key: string;
}

export interface MeetingUploadInitiateResponse {
  meeting_id: string;
  upload_url: string;
  upload_key: string;
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
  answer: string;
  citations: Array<{
    source_type: string;
    source_id: string;
    source_title: string;
    excerpt: string;
    timestamp?: number;
    page_number?: number;
    confidence: number;
  }>;
  processing_time_ms: number;
}

// Document requests
export interface DocumentCreate {
  name: string;
  file_type: string;
  file_size: number;
  content_type: string;
  metadata?: Record<string, unknown>;
}

export interface DocumentUploadInitiate {
  deal_id: string;
  name: string;
  file_name: string;
  file_size: number;
  content_type: string;
}

export interface DocumentUploadConfirm {
  document_id: string;
  upload_key: string;
}

export interface DocumentUploadInitiateResponse {
  document_id: string;
  upload_url: string;
  upload_key: string;
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
