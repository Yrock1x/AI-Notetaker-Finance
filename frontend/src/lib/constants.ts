import { CallType, DealRole, DealStatus } from "@/types";

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
  [DealRole.MEMBER]: "Member",
  [DealRole.VIEWER]: "Viewer",
};

export const MEETING_STATUS_LABELS: Record<string, string> = {
  scheduled: "Scheduled",
  recording: "Recording",
  processing: "Processing",
  transcribing: "Transcribing",
  transcribed: "Transcribed",
  analyzing: "Analyzing",
  analyzed: "Analyzed",
  ready: "Ready",
  failed: "Failed",
};

export const DEAL_STATUS_LABELS: Record<DealStatus, string> = {
  [DealStatus.ACTIVE]: "Active",
  [DealStatus.ON_HOLD]: "On Hold",
  [DealStatus.CLOSED_WON]: "Closed Won",
  [DealStatus.CLOSED_LOST]: "Closed Lost",
  [DealStatus.ARCHIVED]: "Archived",
};
