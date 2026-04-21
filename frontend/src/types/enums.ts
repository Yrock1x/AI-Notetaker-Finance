export enum CallType {
  MANAGEMENT_PRESENTATION = "management_presentation",
  EXPERT_CALL = "expert_call",
  CUSTOMER_REFERENCE = "customer_reference",
  DILIGENCE_SESSION = "diligence_session",
  INTERNAL_DISCUSSION = "internal_discussion",
  OTHER = "other",
}

export enum DealRole {
  LEAD = "lead",
  ADMIN = "admin",
  ANALYST = "analyst",
  VIEWER = "viewer",
}

export enum DealStatus {
  ACTIVE = "active",
  ARCHIVED = "archived",
}

export enum DealType {
  BUYOUT = "buyout",
  GROWTH_EQUITY = "growth_equity",
  VENTURE = "venture",
  RECAPITALIZATION = "recapitalization",
  ADD_ON = "add_on",
  OTHER = "other",
}

export enum MeetingStatus {
  SCHEDULED = "scheduled",
  RECORDING = "recording",
  // Default state for calendar-synced meetings — pre-bot, before the
  // auto-schedule cron kicks a session. Distinct from UPLOADED, which
  // is the post-bot/finalize state.
  UPLOADING = "uploading",
  PROCESSING = "processing",
  TRANSCRIBING = "transcribing",
  ANALYZING = "analyzing",
  UPLOADED = "uploaded",
  TRANSCRIBED = "transcribed",
  ANALYZED = "analyzed",
  READY = "ready",
  FAILED = "failed",
}

export enum MeetingSource {
  ZOOM = "zoom",
  TEAMS = "teams",
  GOOGLE_MEET = "google_meet",
  UPLOAD = "upload",
  OTHER = "other",
}
