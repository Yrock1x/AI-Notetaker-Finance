import { CallType, DealRole, DealStatus, MeetingStatus } from "@/types";

export const CALL_TYPE_LABELS: Record<CallType, string> = {
  [CallType.MANAGEMENT_PRESENTATION]: "Management Presentation",
  [CallType.EXPERT_CALL]: "Expert Call",
  [CallType.CUSTOMER_REFERENCE]: "Customer Reference",
  [CallType.DILIGENCE_SESSION]: "Diligence Session",
  [CallType.INTERNAL_DISCUSSION]: "Internal Discussion",
  [CallType.OTHER]: "Other",
};

export const DEAL_ROLE_LABELS: Record<DealRole, string> = {
  [DealRole.LEAD]: "Lead",
  [DealRole.ADMIN]: "Admin",
  [DealRole.ANALYST]: "Analyst",
  [DealRole.VIEWER]: "Viewer",
};

export const MEETING_STATUS_LABELS: Record<MeetingStatus, string> = {
  [MeetingStatus.SCHEDULED]: "Scheduled",
  [MeetingStatus.RECORDING]: "Recording",
  [MeetingStatus.PROCESSING]: "Processing",
  [MeetingStatus.TRANSCRIBING]: "Transcribing",
  [MeetingStatus.ANALYZING]: "Analyzing",
  [MeetingStatus.TRANSCRIBED]: "Transcribed",
  [MeetingStatus.ANALYZED]: "Analyzed",
  [MeetingStatus.READY]: "Ready",
  [MeetingStatus.FAILED]: "Failed",
};

export const DEAL_STATUS_LABELS: Record<DealStatus, string> = {
  [DealStatus.ACTIVE]: "Active",
  [DealStatus.ON_HOLD]: "On Hold",
  [DealStatus.CLOSED_WON]: "Closed Won",
  [DealStatus.CLOSED_LOST]: "Closed Lost",
  [DealStatus.ARCHIVED]: "Archived",
};
