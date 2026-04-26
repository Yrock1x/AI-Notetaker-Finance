// Inngest webhook — this is the endpoint Inngest's cloud service calls to
// invoke our functions. Configured in the Inngest dashboard under
// "Sync new app" with URL https://<vercel>/api/inngest.
//
// Without INNGEST_SIGNING_KEY in the env, the SDK runs in "dev mode" and
// accepts unsigned requests — a hole in production. Fail fast at module
// load time so a misconfigured deploy never serves traffic.

import { serve } from "inngest/next";
import { inngest } from "@/lib/inngest/client";
import { functions } from "@/lib/inngest/functions";

if (
  process.env.NODE_ENV === "production" &&
  !process.env.INNGEST_SIGNING_KEY
) {
  throw new Error(
    "INNGEST_SIGNING_KEY is required in production — without it the Inngest webhook accepts unsigned events."
  );
}

export const { GET, POST, PUT } = serve({
  client: inngest,
  functions,
  signingKey: process.env.INNGEST_SIGNING_KEY,
});
