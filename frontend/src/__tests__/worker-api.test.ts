import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  API_BASE,
  ApiError,
  NotFoundError,
  buildQuery,
  apiGet,
  apiPost,
  apiPatch,
  apiDelete,
} from "@/lib/worker-api";

const fetchMock = vi.fn<typeof fetch>();
vi.stubGlobal("fetch", fetchMock);

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

beforeEach(() => {
  fetchMock.mockReset();
});

async function captureError(p: Promise<unknown>): Promise<ApiError> {
  try {
    await p;
  } catch (e) {
    return e as ApiError;
  }
  throw new Error("expected the request to reject");
}

describe("buildQuery", () => {
  it("returns an empty string for no params", () => {
    expect(buildQuery()).toBe("");
    expect(buildQuery({})).toBe("");
  });

  it("skips null, undefined and empty-string values", () => {
    expect(buildQuery({ a: 1, b: null, c: undefined, d: "", e: false })).toBe(
      "?a=1&e=false"
    );
  });

  it("URL-encodes values", () => {
    expect(buildQuery({ q: "a b&c" })).toBe("?q=a+b%26c");
  });
});

describe("request mechanics", () => {
  it("sends cookies and the Accept header on GET", async () => {
    fetchMock.mockResolvedValue(json(200, { id: "d1" }));
    await apiGet("/deals/d1");
    expect(fetchMock).toHaveBeenCalledExactlyOnceWith(
      `${API_BASE}/deals/d1`,
      expect.objectContaining({
        method: "GET",
        credentials: "include",
        headers: expect.objectContaining({ Accept: "application/json" }),
        body: undefined,
      })
    );
  });

  it("JSON-encodes bodies and sets Content-Type on writes", async () => {
    fetchMock.mockResolvedValue(json(200, { ok: true }));
    await apiPost("/deals", { name: "Project X" });
    const [, init] = fetchMock.mock.calls[0];
    expect(init).toMatchObject({
      method: "POST",
      body: JSON.stringify({ name: "Project X" }),
      headers: expect.objectContaining({ "Content-Type": "application/json" }),
    });
  });

  it("parses the JSON body on success", async () => {
    fetchMock.mockResolvedValue(json(200, { id: "m1", title: "Kickoff" }));
    await expect(apiGet("/meetings/m1")).resolves.toEqual({
      id: "m1",
      title: "Kickoff",
    });
  });

  it("returns undefined for 204 and empty bodies", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    await expect(apiDelete("/deals/d1")).resolves.toBeUndefined();

    fetchMock.mockResolvedValue(new Response("", { status: 200 }));
    await expect(apiGet("/deals/d1")).resolves.toBeUndefined();
  });
});

describe("error contract", () => {
  it("throws ApiError carrying status and parsed body on non-2xx", async () => {
    fetchMock.mockResolvedValue(json(422, { detail: "name required" }));
    const err = await captureError(apiPost("/deals", {}));
    expect(err).toBeInstanceOf(ApiError);
    expect(err).not.toBeInstanceOf(NotFoundError);
    expect(err.status).toBe(422);
    expect(err.message).toBe("name required");
    expect(err.body).toEqual({ detail: "name required" });
  });

  it("throws NotFoundError (an ApiError subclass) on 404", async () => {
    fetchMock.mockResolvedValue(json(404, { detail: "deal not found" }));
    const err = await captureError(apiGet("/deals/missing"));
    expect(err).toBeInstanceOf(NotFoundError);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(404);
    expect(err.message).toBe("deal not found");
  });

  it("falls back to the status line when the error body is not JSON", async () => {
    fetchMock.mockResolvedValue(
      new Response("<html>Bad Gateway</html>", {
        status: 502,
        statusText: "Bad Gateway",
      })
    );
    const err = await captureError(apiPatch("/deals/d1", {}));
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(502);
    expect(err.message).toBe("502 Bad Gateway");
    expect(err.body).toBeNull();
  });

  it("keeps the status line when the JSON body has no string detail", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: [{ loc: ["name"] }] }), {
        status: 422,
        statusText: "Unprocessable Entity",
      })
    );
    const err = await captureError(apiPost("/deals", {}));
    expect(err.message).toBe("422 Unprocessable Entity");
  });
});
