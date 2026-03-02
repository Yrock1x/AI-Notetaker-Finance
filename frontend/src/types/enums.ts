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
  ON_HOLD = "on_hold",
  CLOSED_WON = "closed_won",
  CLOSED_LOST = "closed_lost",
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
  PROCESSING = "processing",
  TRANSCRIBING = "transcribing",
  ANALYZING = "analyzing",
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
