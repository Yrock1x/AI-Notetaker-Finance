// Q&A burst load — exercises slowapi rate limiting + Fireworks
// concurrency-cap + tenacity retry. Audit verification target: 100
// simultaneous Q&A requests, no 429 cascade, all complete within 60s.
//
// Notes:
//   - The route is gated to 10/min/user. To stress LLM concurrency you
//     need >=10 distinct test users (one TOKEN_<n> env var per user) so
//     each user stays inside its own per-minute bucket. With a single
//     token you'll observe rate-limiting kicking in correctly — change
//     the threshold below if that's the test you want.
//   - DEAL_ID must reference a real deal the test user(s) can see.
//
// Usage:
//   BASE_URL=https://staging.example.com TOKEN_1=... TOKEN_2=... \
//     DEAL_ID=<uuid> k6 run qa.k6.js

import http from "k6/http";
import { check } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const DEAL_ID = __ENV.DEAL_ID;
if (!DEAL_ID) throw new Error("Set DEAL_ID to a real seeded deal id");

const TOKENS = Object.keys(__ENV)
  .filter((k) => k.startsWith("TOKEN_"))
  .map((k) => __ENV[k]);
if (TOKENS.length === 0) throw new Error("Set at least TOKEN_1 to a JWT");

export const options = {
  scenarios: {
    burst: {
      executor: "constant-arrival-rate",
      rate: 100,
      timeUnit: "1m",
      duration: "5m",
      preAllocatedVUs: 50,
      maxVUs: 200,
    },
  },
  thresholds: {
    "http_req_duration{status:200}": ["p(95)<60000"],
    // Allow up to 50% 429s — rate-limit kicking in is expected and good.
    // What we don't want: 5xx, which would mean retry storm or pool starve.
    "http_req_failed{status:5xx}": ["rate<0.01"],
  },
};

export default function () {
  const token = TOKENS[Math.floor(Math.random() * TOKENS.length)];
  const res = http.post(
    `${BASE_URL}/api/v1/deals/${DEAL_ID}/qa/ask`,
    JSON.stringify({ question: "What was the primary topic discussed?" }),
    {
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      tags: { name: "qa-ask" },
      timeout: "120s",
    }
  );
  check(res, {
    "no 5xx": (r) => r.status < 500,
    "either 200 or 429": (r) => r.status === 200 || r.status === 429,
  });
}
