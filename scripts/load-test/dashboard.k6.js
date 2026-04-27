// Dashboard load profile — verification scenario from the security/scale
// audit. Drive 1k concurrent users hitting the dashboard route and assert
// P95 stays under 800 ms with no 5xx responses.
//
// Usage:
//   BASE_URL=https://staging.example.com SUPABASE_TOKEN=eyJ... k6 run dashboard.k6.js
//
// SUPABASE_TOKEN must be a valid access_token for a real seeded user in
// staging. Don't use prod tokens with this script — it will hammer Supabase
// at the configured RPS.

import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:3000";
const TOKEN = __ENV.SUPABASE_TOKEN;
if (!TOKEN) throw new Error("Set SUPABASE_TOKEN to a valid access_token");

export const options = {
  // Ramp to 1000 VUs over 1 min, hold for 3 min, ramp down.
  stages: [
    { duration: "1m", target: 1000 },
    { duration: "3m", target: 1000 },
    { duration: "30s", target: 0 },
  ],
  thresholds: {
    http_req_duration: ["p(95)<800"],
    http_req_failed: ["rate<0.01"],
  },
};

export default function () {
  const res = http.get(`${BASE_URL}/dashboard`, {
    headers: {
      Cookie: `sb-access-token=${TOKEN}`,
      "User-Agent": "k6-dashboard-load",
    },
    tags: { name: "dashboard" },
  });
  check(res, {
    "200": (r) => r.status === 200,
    "no 5xx": (r) => r.status < 500,
  });
  sleep(Math.random() * 2);
}
