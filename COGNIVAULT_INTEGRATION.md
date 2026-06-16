# CogniScribe ↔ CogniVault integration contract

This is the spec for the **CogniVault side** of per-deal sharing. CogniScribe (the
meeting-intelligence app) is already built against this contract; CogniVault must
implement the two halves below.

CogniVault plays **two roles**:
1. **OAuth Authorization Server** for the "Connect a deal to a VDR" flow
   (CogniScribe is the OAuth *client*).
2. **API consumer (M2M)** that pulls shared deal data from CogniScribe's
   `/partner/v1` API.

---

## 0. Values the two teams exchange (do this first)

**CogniVault → give to CogniScribe** (set as env on the CogniScribe worker):
| CogniScribe env var | Value |
|---|---|
| `COGNIVAULT_CLIENT_ID` | the OAuth client id CogniVault issues for CogniScribe |
| `COGNIVAULT_CLIENT_SECRET` | the matching client secret |
| `COGNIVAULT_AUTHORIZE_URL` | e.g. `https://app.cognivault.com/oauth/authorize` |
| `COGNIVAULT_TOKEN_URL` | e.g. `https://app.cognivault.com/oauth/token` |

**CogniScribe → give to CogniVault:**
- A **partner API key** (raw string). CogniScribe mints it with
  `python -m scripts.mint_partner_key --org <org_id>` and shares it once.
  CogniVault stores it and sends it as `Authorization: Bearer <key>`.
- CogniScribe's **public API base URL** (where `/partner/v1` lives), e.g.
  `https://cogniscribe-worker.fly.dev`.
- The **redirect URI to allowlist** on the CogniVault OAuth client:
  `https://<cogniscribe-public-api>/api/v1/cognivault/callback`

---

## 1. OAuth "Connect VDR" flow (CogniVault = Authorization Server)

A CogniScribe user clicks "Connect to CogniVault VDR" on a deal. CogniScribe
redirects them to CogniVault. **CogniVault is responsible for the access decision:
only a VDR admin may authorize.** CogniScribe does not model VDR roles — if the user
isn't an admin, CogniVault must NOT issue a code.

### 1a. `GET /oauth/authorize`  (CogniVault implements)

CogniScribe sends the user here with query params:

| param | value |
|---|---|
| `client_id` | `COGNIVAULT_CLIENT_ID` |
| `response_type` | `code` |
| `redirect_uri` | `https://<cogniscribe>/api/v1/cognivault/callback` |
| `state` | opaque signed token — **echo it back unchanged** |
| `scope` | `vdr.share` |
| `deal_ref` | the CogniScribe deal id being shared (use to pre-associate the VDR) |
| `deal_name` | the deal's display name (for the consent screen) |

CogniVault must:
1. Authenticate the user (its own login).
2. **Verify the user administers a VDR; let them pick which VDR** to share this deal
   into. Block non-admins here.
3. Show consent ("Allow CogniScribe to share deal *{deal_name}* into VDR *X*?").
4. Redirect back to `redirect_uri` with `?code=<authcode>&state=<same state>`.
   - On denial/error redirect with `?error=<reason>&state=<same state>`
     (**always include `state`** so CogniScribe can return the user to the deal).

### 1b. `POST /oauth/token`  (CogniVault implements)

CogniScribe exchanges the code server-to-server. Request is **form-encoded**:

```
grant_type=authorization_code
code=<authcode>
redirect_uri=https://<cogniscribe>/api/v1/cognivault/callback
client_id=<COGNIVAULT_CLIENT_ID>
client_secret=<COGNIVAULT_CLIENT_SECRET>
```

Response is JSON. **`vdr_id` is required** (the connect fails without it):

```jsonc
{
  "vdr_id": "vdr_abc123",        // REQUIRED — the VDR the user chose
  "vdr_name": "Project Atlas VDR", // optional, shown in CogniScribe UI
  "access_token": "...",          // optional (stored encrypted; reserved for future use)
  "refresh_token": "...",         // optional
  "expires_in": 3600,             // optional
  "scope": "vdr.share"            // optional
}
```

After this, CogniScribe stores a per-deal connection (`deal_id → vdr_id` + share
scopes) and the deal becomes pullable (see §2).

---

## 2. Pulling shared deal data (CogniVault = API consumer)

CogniVault calls CogniScribe's **partner API** with the Bearer key. Only deals that
have an active VDR connection are visible; each carries its `vdr_id` so CogniVault
routes it to the right VDR. Per-deal `shared_scopes` narrow which resource types are
available.

**Auth header on every request:** `Authorization: Bearer <partner_api_key>`

| Method & path | Returns / notes | Required share scope |
|---|---|---|
| `GET /partner/v1/deals` | All shared deals in the org. Each item includes `vdr_id` + `shared_scopes`. **Poll this to discover new/changed shares**; group by `vdr_id`. | — |
| `GET /partner/v1/deals/{deal_id}` | One shared deal (+ `vdr_id`, `shared_scopes`). | — |
| `GET /partner/v1/deals/{deal_id}/documents` | Documents (incl. `extracted_text`, `file_key`). | `documents` |
| `GET /partner/v1/meetings/{meeting_id}/transcript` | Full transcript text. | `transcripts` |
| `GET /partner/v1/meetings/{meeting_id}/analyses` | Completed analyses (`structured_output`). | `analyses` |
| `POST /partner/v1/deals/{deal_id}/search` | Body `{"query_vector": [768 floats], "top_k": 15}` → nearest chunks. | `search` |

**Status codes that matter:**
- A deal with **no active connection / revoked / soft-deleted** → **404** (invisible).
- A deal that's shared but the **resource category is withheld** → **403**.
- So: treat 404 as "not shared (anymore)" and stop ingesting that deal; treat 403 as
  "this category isn't shared for this deal."

**Revocation is immediate** — when a CogniScribe user disconnects or unchecks a
category, the very next pull returns 404/403. There's no event; just re-poll.

**To find which meetings belong to a deal:** meeting ids come from CogniScribe's own
data; for now, the deal's documents + search are the primary content. (If you need a
meetings-by-deal listing on the partner API, ask — it's not exposed yet.)

**Embedding compatibility for `search`:** `query_vector` is a raw 768-dim embedding.
It must come from the **same embedding model CogniScribe indexes with**
(`nomic-embed-text`, 768-dim). If CogniVault can't produce compatible vectors, use
the document/transcript endpoints instead of `search`.

---

## 3. Minimal end-to-end sequence

```
1. (one-time) CogniVault registers CogniScribe as an OAuth client → client_id/secret.
   CogniScribe mints a partner key → CogniVault stores it.
2. User in CogniScribe: deal → Settings → "Connect to CogniVault VDR".
3. CogniScribe → GET CogniVault /oauth/authorize (deal_ref, deal_name, state, ...).
4. CogniVault: login → check VDR admin → pick VDR → consent → redirect with code+state.
5. CogniScribe → POST CogniVault /oauth/token → {vdr_id, ...}. Connection saved.
6. CogniVault polls GET /partner/v1/deals → sees the deal tagged vdr_id → pulls
   documents/transcripts/analyses/search per shared_scopes → ingests into that VDR.
7. User toggles a category off / disconnects → next pull 404s/403s → CogniVault stops.
```

---

## 4. Quick reference — what CogniVault must BUILD

- [ ] OAuth `GET /oauth/authorize` with **VDR-admin gating** + VDR picker + consent.
- [ ] OAuth `POST /oauth/token` returning **`vdr_id`** (+ optional vdr_name/tokens).
- [ ] Register CogniScribe as a client; allowlist its `/api/v1/cognivault/callback`.
- [ ] An ingest worker that holds the partner key, polls `GET /partner/v1/deals`,
      and pulls per-deal content by `vdr_id` + `shared_scopes`, honoring 404/403.
