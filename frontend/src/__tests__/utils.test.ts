import { describe, it, expect } from "vitest";
import { formatTimestamp, formatDuration, formatFileSize, cn } from "@/lib/utils";
import {
  CallType,
  DealRole,
  DealStatus,
  DealType,
  MeetingStatus,
  MeetingSource,
} from "@/types/enums";
import {
  CALL_TYPE_LABELS,
  DEAL_ROLE_LABELS,
  MEETING_STATUS_LABELS,
  DEAL_STATUS_LABELS,
} from "@/lib/constants";

// ---------------------------------------------------------------------------
// formatTimestamp
// ---------------------------------------------------------------------------
describe("formatTimestamp", () => {
  it("should format 0 seconds as 00:00", () => {
    expect(formatTimestamp(0)).toBe("00:00");
  });

  it("should format seconds less than a minute with leading zero", () => {
    expect(formatTimestamp(5)).toBe("00:05");
  });

  it("should format exact minutes correctly", () => {
    expect(formatTimestamp(60)).toBe("01:00");
    expect(formatTimestamp(120)).toBe("02:00");
  });

  it("should format mixed minutes and seconds", () => {
    expect(formatTimestamp(90)).toBe("01:30");
    expect(formatTimestamp(754)).toBe("12:34");
  });

  it("should handle large values (over an hour)", () => {
    expect(formatTimestamp(3661)).toBe("61:01");
  });

  it("should floor fractional seconds", () => {
    expect(formatTimestamp(5.9)).toBe("00:05");
    expect(formatTimestamp(59.99)).toBe("00:59");
  });

  it("should clamp negative values to 0", () => {
    expect(formatTimestamp(-10)).toBe("00:00");
    expect(formatTimestamp(-1)).toBe("00:00");
  });
});

// ---------------------------------------------------------------------------
// formatDuration
// ---------------------------------------------------------------------------
describe("formatDuration", () => {
  it("should format 0 seconds as '0s'", () => {
    expect(formatDuration(0)).toBe("0s");
  });

  it("should format seconds only", () => {
    expect(formatDuration(45)).toBe("45s");
  });

  it("should format minutes only (no leftover seconds)", () => {
    expect(formatDuration(120)).toBe("2m");
  });

  it("should format minutes and seconds", () => {
    expect(formatDuration(90)).toBe("1m 30s");
  });

  it("should format hours only", () => {
    expect(formatDuration(3600)).toBe("1h");
  });

  it("should format hours and minutes", () => {
    expect(formatDuration(3660)).toBe("1h 1m");
  });

  it("should format hours, minutes, and seconds", () => {
    expect(formatDuration(3661)).toBe("1h 1m 1s");
  });

  it("should format hours and seconds (no minutes)", () => {
    expect(formatDuration(3605)).toBe("1h 5s");
  });

  it("should floor fractional seconds", () => {
    expect(formatDuration(1.9)).toBe("1s");
  });

  it("should clamp negative values to 0s", () => {
    expect(formatDuration(-100)).toBe("0s");
  });
});

// ---------------------------------------------------------------------------
// formatFileSize
// ---------------------------------------------------------------------------
describe("formatFileSize", () => {
  it("should format bytes", () => {
    expect(formatFileSize(0)).toBe("0 B");
    expect(formatFileSize(512)).toBe("512 B");
    expect(formatFileSize(1023)).toBe("1023 B");
  });

  it("should format kilobytes", () => {
    expect(formatFileSize(1024)).toBe("1.0 KB");
    expect(formatFileSize(1536)).toBe("1.5 KB");
    expect(formatFileSize(10240)).toBe("10.0 KB");
  });

  it("should format megabytes", () => {
    expect(formatFileSize(1024 * 1024)).toBe("1.0 MB");
    expect(formatFileSize(1.5 * 1024 * 1024)).toBe("1.5 MB");
  });

  it("should format gigabytes", () => {
    expect(formatFileSize(1024 * 1024 * 1024)).toBe("1.0 GB");
    expect(formatFileSize(2.5 * 1024 * 1024 * 1024)).toBe("2.5 GB");
  });

  it("should handle boundary between KB and MB", () => {
    // 1 byte below 1 MB
    expect(formatFileSize(1024 * 1024 - 1)).toContain("KB");
    // exact 1 MB
    expect(formatFileSize(1024 * 1024)).toContain("MB");
  });
});

// ---------------------------------------------------------------------------
// cn (className merge utility)
// ---------------------------------------------------------------------------
describe("cn", () => {
  it("should merge class names", () => {
    const result = cn("px-2", "py-1");
    expect(result).toBe("px-2 py-1");
  });

  it("should handle conditional classes via clsx", () => {
    const result = cn("base", false && "hidden", "end");
    expect(result).toBe("base end");
  });

  it("should resolve tailwind conflicts via twMerge", () => {
    // twMerge should resolve px-2 vs px-4 to the last one
    const result = cn("px-2 py-1", "px-4");
    expect(result).toBe("py-1 px-4");
  });

  it("should handle empty input", () => {
    const result = cn();
    expect(result).toBe("");
  });

  it("should handle undefined and null inputs", () => {
    const result = cn("a", undefined, null, "b");
    expect(result).toBe("a b");
  });
});

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------
describe("Enums", () => {
  describe("CallType", () => {
    it("should have all expected values", () => {
      expect(CallType.MANAGEMENT_PRESENTATION).toBe("management_presentation");
      expect(CallType.EXPERT_CALL).toBe("expert_call");
      expect(CallType.CUSTOMER_REFERENCE).toBe("customer_reference");
      expect(CallType.DILIGENCE_SESSION).toBe("diligence_session");
      expect(CallType.INTERNAL_DISCUSSION).toBe("internal_discussion");
      expect(CallType.OTHER).toBe("other");
    });

    it("should have exactly 6 members", () => {
      const values = Object.values(CallType);
      expect(values).toHaveLength(6);
    });
  });

  describe("DealRole", () => {
    it("should have all expected values", () => {
      expect(DealRole.LEAD).toBe("lead");
      expect(DealRole.ADMIN).toBe("admin");
      expect(DealRole.ANALYST).toBe("analyst");
      expect(DealRole.VIEWER).toBe("viewer");
    });

    it("should have exactly 4 members", () => {
      const values = Object.values(DealRole);
      expect(values).toHaveLength(4);
    });
  });

  describe("DealStatus", () => {
    it("should have all expected values", () => {
      expect(DealStatus.ACTIVE).toBe("active");
      expect(DealStatus.ON_HOLD).toBe("on_hold");
      expect(DealStatus.CLOSED_WON).toBe("closed_won");
      expect(DealStatus.CLOSED_LOST).toBe("closed_lost");
      expect(DealStatus.ARCHIVED).toBe("archived");
    });

    it("should have exactly 5 members", () => {
      const values = Object.values(DealStatus);
      expect(values).toHaveLength(5);
    });
  });

  describe("DealType", () => {
    it("should have all expected values", () => {
      expect(DealType.BUYOUT).toBe("buyout");
      expect(DealType.GROWTH_EQUITY).toBe("growth_equity");
      expect(DealType.VENTURE).toBe("venture");
      expect(DealType.RECAPITALIZATION).toBe("recapitalization");
      expect(DealType.ADD_ON).toBe("add_on");
      expect(DealType.OTHER).toBe("other");
    });

    it("should have exactly 6 members", () => {
      const values = Object.values(DealType);
      expect(values).toHaveLength(6);
    });
  });

  describe("MeetingStatus", () => {
    it("should have all expected values", () => {
      expect(MeetingStatus.SCHEDULED).toBe("scheduled");
      expect(MeetingStatus.RECORDING).toBe("recording");
      expect(MeetingStatus.PROCESSING).toBe("processing");
      expect(MeetingStatus.TRANSCRIBING).toBe("transcribing");
      expect(MeetingStatus.ANALYZING).toBe("analyzing");
      expect(MeetingStatus.TRANSCRIBED).toBe("transcribed");
      expect(MeetingStatus.ANALYZED).toBe("analyzed");
      expect(MeetingStatus.READY).toBe("ready");
      expect(MeetingStatus.FAILED).toBe("failed");
    });

    it("should have exactly 9 members", () => {
      const values = Object.values(MeetingStatus);
      expect(values).toHaveLength(9);
    });
  });

  describe("MeetingSource", () => {
    it("should have all expected values", () => {
      expect(MeetingSource.ZOOM).toBe("zoom");
      expect(MeetingSource.TEAMS).toBe("teams");
      expect(MeetingSource.GOOGLE_MEET).toBe("google_meet");
      expect(MeetingSource.UPLOAD).toBe("upload");
      expect(MeetingSource.OTHER).toBe("other");
    });

    it("should have exactly 5 members", () => {
      const values = Object.values(MeetingSource);
      expect(values).toHaveLength(5);
    });
  });
});

// ---------------------------------------------------------------------------
// Constants (label maps)
// ---------------------------------------------------------------------------
describe("Constants", () => {
  describe("CALL_TYPE_LABELS", () => {
    it("should map every CallType to a human-readable string", () => {
      for (const val of Object.values(CallType)) {
        expect(CALL_TYPE_LABELS[val as CallType]).toBeDefined();
        expect(typeof CALL_TYPE_LABELS[val as CallType]).toBe("string");
      }
    });

    it("should have specific expected labels", () => {
      expect(CALL_TYPE_LABELS[CallType.MANAGEMENT_PRESENTATION]).toBe(
        "Management Presentation"
      );
      expect(CALL_TYPE_LABELS[CallType.EXPERT_CALL]).toBe("Expert Call");
      expect(CALL_TYPE_LABELS[CallType.OTHER]).toBe("Other");
    });
  });

  describe("DEAL_ROLE_LABELS", () => {
    it("should map every DealRole to a human-readable string", () => {
      for (const val of Object.values(DealRole)) {
        expect(DEAL_ROLE_LABELS[val as DealRole]).toBeDefined();
      }
    });

    it("should have specific expected labels", () => {
      expect(DEAL_ROLE_LABELS[DealRole.LEAD]).toBe("Lead");
      expect(DEAL_ROLE_LABELS[DealRole.VIEWER]).toBe("Viewer");
    });
  });

  describe("MEETING_STATUS_LABELS", () => {
    it("should map every MeetingStatus to a human-readable string", () => {
      for (const val of Object.values(MeetingStatus)) {
        expect(MEETING_STATUS_LABELS[val as MeetingStatus]).toBeDefined();
      }
    });

    it("should have specific expected labels", () => {
      expect(MEETING_STATUS_LABELS[MeetingStatus.SCHEDULED]).toBe("Scheduled");
      expect(MEETING_STATUS_LABELS[MeetingStatus.READY]).toBe("Ready");
      expect(MEETING_STATUS_LABELS[MeetingStatus.FAILED]).toBe("Failed");
    });
  });

  describe("DEAL_STATUS_LABELS", () => {
    it("should map every DealStatus to a human-readable string", () => {
      for (const val of Object.values(DealStatus)) {
        expect(DEAL_STATUS_LABELS[val as DealStatus]).toBeDefined();
      }
    });

    it("should have specific expected labels", () => {
      expect(DEAL_STATUS_LABELS[DealStatus.ACTIVE]).toBe("Active");
      expect(DEAL_STATUS_LABELS[DealStatus.CLOSED_WON]).toBe("Closed Won");
      expect(DEAL_STATUS_LABELS[DealStatus.ARCHIVED]).toBe("Archived");
    });
  });
});
