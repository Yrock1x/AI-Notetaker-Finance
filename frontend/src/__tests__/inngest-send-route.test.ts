import { describe, it, expect, beforeEach, vi } from "vitest";
import { NextRequest } from "next/server";

// The route computes its worker base URL at import time.
vi.hoisted(() => {
  process.env.NEXT_PUBLIC_API_URL = "http://worker.test";
});

vi.mock("@/lib/inngest/client", () => ({
  inngest: { send: vi.fn() },
}));

import { POST } from "@/app/api/inngest/send/route";
import { inngest } from "@/lib/inngest/client";

const sendMock = vi.mocked(inngest.send);
const fetchMock = vi.fn<typeof fetch>();
vi.stubGlobal("fetch", fetchMock);

const API_BASE = "http://worker.test/api/v1";
const COOKIE = "cogni_session=abc123";
const MEETING_ID = "11111111-2222-4333-8444-555555555555";
const DOCUMENT_ID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";
const SESSION_ID = "99999999-8888-4777-8666-555555555555";

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

// Route worker calls by URL suffix; anything unrouted is a test bug.
function mockWorker(routes: Record<string, Response | (() => Response | Promise<Response>)>) {
  fetchMock.mockImplementation(async (input) => {
    const url = String(input);
    for (const [suffix, response] of Object.entries(routes)) {
      if (url === `${API_BASE}${suffix}`) {
        return typeof response === "function" ? response() : response.clone();
      }
    }
    throw new Error(`unexpected worker fetch: ${url}`);
  });
}

function makeRequest(
  body: unknown,
  { cookie = COOKIE }: { cookie?: string | null } = {}
): NextRequest {
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (cookie) headers.cookie = cookie;
  return new NextRequest("http://app.test/api/inngest/send", {
    method: "POST",
    headers,
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
}

const validSession = () => json(200, { id: "user-1" });

beforeEach(() => {
  fetchMock.mockReset();
  sendMock.mockReset();
});

describe("POST /api/inngest/send — authentication", () => {
  it("rejects a request with no cookie without touching the worker or Inngest", async () => {
    const res = await POST(makeRequest({ name: "meeting/uploaded" }, { cookie: null }));
    expect(res.status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(sendMock).not.toHaveBeenCalled();
  });

  it("rejects when the worker says the session is invalid", async () => {
    mockWorker({ "/auth/session": json(401, { detail: "no session" }) });
    const res = await POST(
      makeRequest({ name: "meeting/uploaded", data: { meeting_id: MEETING_ID } })
    );
    expect(res.status).toBe(401);
    expect(sendMock).not.toHaveBeenCalled();
  });

  it("rejects when the session check itself fails (worker down)", async () => {
    mockWorker({
      "/auth/session": () => {
        throw new Error("ECONNREFUSED");
      },
    });
    const res = await POST(
      makeRequest({ name: "meeting/uploaded", data: { meeting_id: MEETING_ID } })
    );
    expect(res.status).toBe(401);
    expect(sendMock).not.toHaveBeenCalled();
  });

  it("forwards the caller's cookie verbatim on the session check", async () => {
    mockWorker({
      "/auth/session": validSession(),
      [`/meetings/${MEETING_ID}`]: json(200, { id: MEETING_ID }),
    });
    await POST(makeRequest({ name: "meeting/uploaded", data: { meeting_id: MEETING_ID } }));
    const sessionCall = fetchMock.mock.calls.find(([url]) =>
      String(url).endsWith("/auth/session")
    );
    expect(sessionCall).toBeDefined();
    const headers = new Headers((sessionCall![1] as RequestInit).headers);
    expect(headers.get("cookie")).toBe(COOKIE);
  });
});

describe("POST /api/inngest/send — event allowlist & payload validation", () => {
  beforeEach(() => {
    mockWorker({ "/auth/session": validSession() });
  });

  it("rejects malformed JSON bodies", async () => {
    const res = await POST(makeRequest("{not json"));
    expect(res.status).toBe(400);
    expect(sendMock).not.toHaveBeenCalled();
  });

  it("rejects events not on the allowlist (internal pipeline events)", async () => {
    for (const name of [
      "meeting/bot-completed",
      "zoom/recording.completed",
      "calendar/sync.requested",
      "bot/auto-schedule.requested",
    ]) {
      const res = await POST(makeRequest({ name, data: {} }));
      expect(res.status).toBe(400);
    }
    expect(sendMock).not.toHaveBeenCalled();
  });

  it("rejects a missing event name", async () => {
    const res = await POST(makeRequest({ data: { meeting_id: MEETING_ID } }));
    expect(res.status).toBe(400);
    expect(sendMock).not.toHaveBeenCalled();
  });

  it("rejects a non-UUID meeting_id before any ownership lookup", async () => {
    const res = await POST(
      makeRequest({ name: "meeting/uploaded", data: { meeting_id: "1 OR 1=1" } })
    );
    expect(res.status).toBe(400);
    // Only the session check fired — no resource GET with attacker input.
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(sendMock).not.toHaveBeenCalled();
  });

  it("rejects a missing session_id for bot events", async () => {
    const res = await POST(makeRequest({ name: "bot/scheduled", data: {} }));
    expect(res.status).toBe(400);
    expect(sendMock).not.toHaveBeenCalled();
  });
});

describe("POST /api/inngest/send — cross-tenant ownership checks", () => {
  it("rejects meeting/uploaded when the worker denies the meeting (404)", async () => {
    mockWorker({
      "/auth/session": validSession(),
      [`/meetings/${MEETING_ID}`]: json(404, { detail: "not found" }),
    });
    const res = await POST(
      makeRequest({ name: "meeting/uploaded", data: { meeting_id: MEETING_ID } })
    );
    expect(res.status).toBe(403);
    expect(sendMock).not.toHaveBeenCalled();
  });

  it("rejects document/uploaded when the worker denies the document (403)", async () => {
    mockWorker({
      "/auth/session": validSession(),
      [`/documents/${DOCUMENT_ID}`]: json(403, { detail: "forbidden" }),
    });
    const res = await POST(
      makeRequest({ name: "document/uploaded", data: { document_id: DOCUMENT_ID } })
    );
    expect(res.status).toBe(403);
    expect(sendMock).not.toHaveBeenCalled();
  });

  it("rejects meeting/uploaded when the ownership lookup errors out", async () => {
    mockWorker({
      "/auth/session": validSession(),
      [`/meetings/${MEETING_ID}`]: () => {
        throw new Error("socket hang up");
      },
    });
    const res = await POST(
      makeRequest({ name: "meeting/uploaded", data: { meeting_id: MEETING_ID } })
    );
    expect(res.status).toBe(403);
    expect(sendMock).not.toHaveBeenCalled();
  });

  it("rejects bot/scheduled when the session id is not in the caller's org", async () => {
    mockWorker({
      "/auth/session": validSession(),
      "/bot-sessions": json(200, [{ id: "some-other-session" }]),
    });
    const res = await POST(
      makeRequest({ name: "bot/scheduled", data: { session_id: SESSION_ID } })
    );
    expect(res.status).toBe(403);
    expect(sendMock).not.toHaveBeenCalled();
  });

  it("rejects bot/cancelled when the session listing fails", async () => {
    mockWorker({
      "/auth/session": validSession(),
      "/bot-sessions": () => {
        throw new Error("socket hang up");
      },
    });
    const res = await POST(
      makeRequest({ name: "bot/cancelled", data: { session_id: SESSION_ID } })
    );
    expect(res.status).toBe(502);
    expect(sendMock).not.toHaveBeenCalled();
  });
});

describe("POST /api/inngest/send — authorized sends", () => {
  it("forwards meeting/uploaded with user attribution after the checks pass", async () => {
    mockWorker({
      "/auth/session": validSession(),
      [`/meetings/${MEETING_ID}`]: json(200, { id: MEETING_ID }),
    });
    const res = await POST(
      makeRequest({
        name: "meeting/uploaded",
        data: { meeting_id: MEETING_ID, deal_id: DOCUMENT_ID },
      })
    );
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ ok: true });
    expect(sendMock).toHaveBeenCalledExactlyOnceWith({
      name: "meeting/uploaded",
      data: { meeting_id: MEETING_ID, deal_id: DOCUMENT_ID },
      user: { external_id: "user-1" },
    });
  });

  it("forwards document/uploaded when the worker confirms access", async () => {
    mockWorker({
      "/auth/session": validSession(),
      [`/documents/${DOCUMENT_ID}`]: json(200, { id: DOCUMENT_ID }),
    });
    const res = await POST(
      makeRequest({ name: "document/uploaded", data: { document_id: DOCUMENT_ID } })
    );
    expect(res.status).toBe(200);
    expect(sendMock).toHaveBeenCalledOnce();
  });

  it("forwards bot/scheduled when the session id belongs to the caller", async () => {
    mockWorker({
      "/auth/session": validSession(),
      "/bot-sessions": json(200, [{ id: "other" }, { id: SESSION_ID }]),
    });
    const res = await POST(
      makeRequest({ name: "bot/scheduled", data: { session_id: SESSION_ID } })
    );
    expect(res.status).toBe(200);
    expect(sendMock).toHaveBeenCalledExactlyOnceWith({
      name: "bot/scheduled",
      data: { session_id: SESSION_ID },
      user: { external_id: "user-1" },
    });
  });

  it("omits user attribution when the session payload has no id", async () => {
    mockWorker({
      "/auth/session": json(200, {}),
      [`/meetings/${MEETING_ID}`]: json(200, { id: MEETING_ID }),
    });
    const res = await POST(
      makeRequest({ name: "meeting/uploaded", data: { meeting_id: MEETING_ID } })
    );
    expect(res.status).toBe(200);
    expect(sendMock.mock.calls[0][0]).not.toHaveProperty("user");
  });
});
