// Inngest webhook — this is the endpoint Inngest's cloud service calls to
// invoke our functions. Configured in the Inngest dashboard under
// "Sync new app" with URL https://<vercel>/api/inngest.

import { serve } from "inngest/next";
import { inngest } from "@/lib/inngest/client";
import { functions } from "@/lib/inngest/functions";

export const { GET, POST, PUT } = serve({
  client: inngest,
  functions,
});
