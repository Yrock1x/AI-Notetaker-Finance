import {
  CallType,
  DealRole,
  DealStatus,
  DealType,
  MeetingSource,
  MeetingStatus,
} from "./enums";

export interface Organization {
  id: string;
  name: string;
  slug: string;
  settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  avatar_url?: string;
  org_id: string;
  role: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Deal {
  id: string;
  org_id: string;
  name: string;
  target_company?: string;
  deal_type: DealType;
  status: DealStatus;
  description?: string;
  stage?: string;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface DealMember {
  id: string;
  deal_id: string;
  user_id: string;
  role: DealRole;
  user?: User;
  created_at: string;
}

export interface Meeting {
  id: string;
  deal_id: string;
  org_id: string;
  title: string;
  meeting_date?: string;
  duration_seconds?: number;
  source: MeetingSource;
  status: MeetingStatus;
  error_message?: string;
  bot_enabled?: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface Transcript {
  id: string;
  meeting_id: string;
  full_text: string;
  language: string;
  confidence_score?: number;
  word_count: number;
  created_at: string;
  updated_at: string;
}

export interface TranscriptSegment {
  id: string;
  transcript_id: string;
  speaker_label: string;
  speaker_name?: string;
  start_time: number;
  end_time: number;
  text: string;
  confidence: number;
  segment_index: number;
}

export interface Analysis {
  id: string;
  meeting_id: string;
  analysis_type: CallType;
  call_type: CallType;
  status: MeetingStatus;
  result?: Record<string, unknown>;
  model_version: string;
  processing_time_ms?: number;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface Document {
  id: string;
  deal_id: string;
  title: string;
  document_type: string;
  file_size: number;
  uploaded_by: string;
  created_at: string;
  updated_at: string;
}

export interface Citation {
  source_type: string;
  source_id: string;
  source_title: string;
  text_excerpt: string;
  timestamp?: number;
  page?: number;
}

export interface QAInteraction {
  id: string;
  deal_id: string;
  question: string;
  answer: string;
  citations: Citation[];
  model_version: string;
  processing_time_ms: number;
  asked_by: string;
  created_at: string;
}

export interface BotSession {
  id: string;
  meeting_id: string;
  platform: MeetingSource;
  status: string;
  join_url?: string;
  bot_user_id?: string;
  started_at?: string;
  ended_at?: string;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

export interface AuditLog {
  id: string;
  org_id: string;
  user_id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  details: Record<string, unknown>;
  ip_address?: string;
  user_agent?: string;
  created_at: string;
}
