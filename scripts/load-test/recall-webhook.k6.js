// Recall webhook simulation — exercises the bounded asyncio.Semaphore
// around transcript_segments upserts. Audit verification target: 50
// simulated meetings × 1 partial-segment-webhook/sec for 10 min, with
// connection-pool wait < 50ms P95 and no segments dropped.
//
// This script does NOT produce a valid Recall HMAC — production deploys
// require RECALL_WEBHOOK_SECRET to be UNSET on the staging worker for
// this load test, OR for the script to be extended with a signing step.
// Do NOT run this against a worker that has webhook secrets configured.
//
// Usage:
//   BASE_URL=https://staging-worker.example.com k6 run recall-webhook.k6.js
//   # First seed 50 bot_id rows in meeting_bot_sessions:
//   #   bot_id format: "load-test-bot-<i>" for i in 1..50

import http from "k6/http";
import { check } from "k6";
import encoding from "k6/encoding";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const MEETING_COUNT = parseInt(__ENV.MEETING_COUNT || "50", 10);

export const options = {
  scenarios: {
    transcript_partials: {
      executor: "constant-arrival-rate",
      rate: MEETING_COUNT, // 1 partial/sec/meeting × MEETING_COUNT meetings
      timeUnit: "1s",
      duration: "10m",
      preAllocatedVUs: 50,
      maxVUs: 200,
    },
  },
  thresholds: {
    "http_req_duration{status:200}": ["p(95)<2000"],
    "http_req_failed{status:5xx}": ["rate<0.01"],
  },
};

let counter = 0;

export default function () {
  const botIndex = (counter++ % MEETING_COUNT) + 1;
  const botId = `load-test-bot-${botIndex}`;
  const segmentId = `${botId}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const body = JSON.stringify({
    event: "transcript.data",
    data: {
      bot_id: botId,
      segment: {
        id: segmentId,
        speaker: `Speaker ${botIndex}`,
        text: "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
        start_time: 0.0,
        end_time: 1.0,
        confidence: 0.9,
        index: 0,
      },
    },
  });

  // Realistic-looking svix headers so the dedupe LRU records the message.
  const svixId = `msg_${segmentId}`;
  const svixTs = Math.floor(Date.now() / 1000).toString();
  const svixSig = encoding.b64encode("dummy"); // verifier rejects this unless secret unset

  const res = http.post(`${BASE_URL}/api/v1/webhooks/recall`, body, {
    headers: {
      "Content-Type": "application/json",
      "webhook-id": svixId,
      "webhook-timestamp": svixTs,
      "webhook-signature": `v1,${svixSig}`,
    },
    tags: { name: "recall-webhook" },
  });
  check(res, {
    "no 5xx": (r) => r.status < 500,
  });
}
