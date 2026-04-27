# Load tests — security/scale audit verification

Three k6 scripts cover the verification scenarios from the audit's
"Load test (1k concurrent)" section. They are **never run automatically**;
you invoke them by hand against staging when you want to validate the
P0–P3 fixes under realistic load.

## Setup

Install [k6](https://k6.io/docs/get-started/installation/) (`brew install k6`
on macOS).

## Scripts

### `dashboard.k6.js`
1k concurrent VUs hitting `/dashboard` for 4 minutes.
Asserts P95 < 800 ms and no 5xx.

```bash
SUPABASE_TOKEN=eyJ... BASE_URL=https://staging.example.com \
  k6 run dashboard.k6.js
```

### `qa.k6.js`
100 Q&A requests/min against the rate-limited `/qa/ask` route.
Asserts that 429s are tolerated (rate-limit working) but no 5xx (no
retry storm, no Postgres pool starve).

```bash
TOKEN_1=eyJ... TOKEN_2=eyJ... DEAL_ID=<uuid> \
  BASE_URL=https://staging-worker.example.com \
  k6 run qa.k6.js
```

### `recall-webhook.k6.js`
50 simulated live meetings × 1 partial transcript/sec for 10 minutes.
Exercises the `asyncio.Semaphore(8)` cap on transcript_segments upserts.

**Important:** the script does not produce a valid Recall HMAC. Run only
against a staging worker with `RECALL_WEBHOOK_SECRET` unset, or add an
HMAC signing step. **Never run this against production.**

```bash
MEETING_COUNT=50 BASE_URL=https://staging-worker.example.com \
  k6 run recall-webhook.k6.js
```

## Pre-flight checklist

Before running any of these against staging:

- [ ] Migrations 0009 and 0010 applied to the target database
- [ ] `INNGEST_SIGNING_KEY` set in the Vercel deploy
- [ ] `SUPABASE_JWT_SECRET` set in the worker if you're issuing HS256 tokens
- [ ] Test users exist with seed data so the dashboard / Q&A scripts have
      something to fetch
- [ ] Sentry / Datadog dashboards open in another tab so you can watch for
      regressions in real time
