"""CogniVault integration — the "Connect a deal to a VDR" OAuth client flow.

The shareable resource categories below are the per-deal toggles a user picks when
sharing a deal into a VDR. They gate what the partner API (/partner/v1) will serve
for that deal, *in addition to* the partner key's own scopes:

    documents   → GET /partner/v1/deals/{id}/documents
    transcripts → GET /partner/v1/meetings/{id}/transcript
    analyses    → GET /partner/v1/meetings/{id}/analyses
    search      → POST /partner/v1/deals/{id}/search

The deal record itself (list/get) is visible whenever an active connection exists.
"""

from __future__ import annotations

# Ordered for stable display; membership-checked as a set everywhere else.
SHAREABLE_SCOPES: tuple[str, ...] = ("documents", "transcripts", "analyses", "search")

__all__ = ["SHAREABLE_SCOPES"]
