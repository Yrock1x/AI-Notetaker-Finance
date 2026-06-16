// Contract tests for the internal worker response schemas. The shapes mirror
// the Pydantic models in backend/app/api/v1/internal/ — these tests pin the
// tolerances that matter (nullable ids) and that garbage is rejected rather
// than carried into Inngest event fan-outs.

import { describe, it, expect } from "vitest";
import {
  transcribeResponseSchema,
  autoScheduleDueResponseSchema,
  zoomIngestResponseSchema,
  activeIntegrationsResponseSchema,
  calendarSyncResponseSchema,
  ensureSubscriptionResponseSchema,
} from "@/lib/worker-contracts";

describe("worker contracts", () => {
  it("accepts the documented happy-path shapes", () => {
    expect(() => {
      transcribeResponseSchema.parse({ transcript_id: "t1", segment_count: 42 });
      autoScheduleDueResponseSchema.parse({
        scheduled: [{ session_id: "s1", meeting_id: "m1", deal_id: "d1" }],
      });
      zoomIngestResponseSchema.parse({ meeting_id: "m1", status: "uploaded" });
      activeIntegrationsResponseSchema.parse({
        integrations: [{ org_id: "o1", user_id: "u1", platform: "zoom" }],
      });
      calendarSyncResponseSchema.parse({
        platform: "google",
        events_seen: 10,
        meetings_upserted: 3,
      });
      ensureSubscriptionResponseSchema.parse({
        subscription_id: "sub1",
        expiration: "2026-06-12T00:00:00Z",
        action: "renewed",
      });
    }).not.toThrow();
  });

  it("tolerates the worker's nullable ids", () => {
    // zoom ingest returns meeting_id=null on the no-credential path; the
    // pipeline must see that (and skip the fan-out), not fail validation.
    expect(
      zoomIngestResponseSchema.parse({ meeting_id: null, status: "no_credential" })
        .meeting_id
    ).toBeNull();
    // deal_id is null for calendar-synced meetings not yet assigned to a deal.
    expect(() =>
      autoScheduleDueResponseSchema.parse({
        scheduled: [{ session_id: "s1", meeting_id: "m1", deal_id: null }],
      })
    ).not.toThrow();
  });

  it("rejects payloads that would poison an event fan-out", () => {
    // A missing/garbage id must throw (→ Inngest retry), not propagate.
    expect(() => transcribeResponseSchema.parse({})).toThrow();
    expect(() =>
      autoScheduleDueResponseSchema.parse({
        scheduled: [{ meeting_id: "m1", deal_id: "d1" }],
      })
    ).toThrow();
    expect(() =>
      activeIntegrationsResponseSchema.parse({ integrations: [{ org_id: 1 }] })
    ).toThrow();
    expect(() => zoomIngestResponseSchema.parse({ status: "uploaded" })).toThrow();
  });
});
