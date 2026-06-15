"""Static tripwire against cross-tenant scope regressions.

The app replaced Postgres RLS with app-layer scoping (app/db/scope.py). Two HIGH
regressions during the migration came from a route handler fetching a
tenant-owned row by id and forgetting the org/membership check. A full audit
confirmed every handler is currently scoped; this test fails loudly if a future
change re-introduces an unscoped handler.

Heuristic: any route handler (function decorated with @router.<verb> /
@<name>_router.<verb>) that queries a tenant-owned model via ``select(Model)``
or ``session.query(Model...)`` must ALSO contain a scope guard — one of the
known helper calls, an ``in_org`` check, or an inline ``<Model>.org_id == ...``
filter. Handlers that legitimately need no model-level guard (signature-gated
storage PUT/GET) are explicitly allowlisted.

If this test flags a handler, either add the missing scope guard or — if the
handler is genuinely exempt — add it to ``EXEMPT_HANDLERS`` with a comment
explaining why.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "app"

# Route-handler modules that serve user/partner traffic and touch tenant data.
HANDLER_MODULES = [
    *(APP / "api" / "v1" / "store").glob("*.py"),
    APP / "api" / "v1" / "qa.py",
    APP / "api" / "v1" / "analysis.py",
    APP / "api" / "v1" / "deliverables.py",
    APP / "api" / "v1" / "partner" / "router.py",
    APP / "api" / "v1" / "cognivault.py",
    APP / "realtime" / "sse.py",
]

# Tables that carry tenant data (directly via org_id or through a meeting/deal).
TENANT_MODELS = {
    "Deal", "Meeting", "Document", "Analysis", "Transcript", "TranscriptSegment",
    "MeetingBotSession", "MeetingParticipant", "MeetingChatMessage", "QaInteraction",
    "Embedding", "Deliverable", "ActionItemCompletion", "IntegrationCredential",
    "GraphSubscription", "DealVdrConnection",
}

# Names that prove a membership/org check happened in the handler.
GUARD_NAMES = {
    "org_scoped", "meeting_scoped",
    "scoped_deal_or_404", "scoped_meeting_or_404", "_scoped_deal_or_404",
    "_scoped_shared_deal_or_404", "_scoped_shared_meeting_or_404", "_active_connection",
    "require_org", "in_org",
    "_require_deal_access", "_require_meeting_org",
    "deal_org_id",
}

# Handlers that touch a tenant model but are safe without a model-level guard,
# with the reason. Storage PUT/GET prove access via the HMAC signature in the
# URL (local.verify), not a principal.
EXEMPT_HANDLERS = {
    "put_object",   # signature-gated (local.verify)
    "get_object",   # signature-gated (local.verify)
}


def _root_name(node: ast.AST) -> str | None:
    """Resolve ``Model`` from ``Model`` or ``Model.col`` (the first arg of a
    select()/query() call)."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _root_name(node.value)
    return None


def _is_route_handler(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for dec in fn.decorator_list:
        # @router.get(...), @meeting_qa_router.post(...), @limiter.limit(...)
        func = dec.func if isinstance(dec, ast.Call) else dec
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id.endswith("router")
            and func.attr in {"get", "post", "put", "patch", "delete"}
        ):
            return True
    return False


def _queries_tenant_model(fn: ast.AST) -> set[str]:
    """Return the tenant models the function queries via select()/query()."""
    hit: set[str] = set()
    for node in ast.walk(fn):
        if not (isinstance(node, ast.Call) and node.args):
            continue
        func = node.func
        is_select = isinstance(func, ast.Name) and func.id == "select"
        is_query = isinstance(func, ast.Attribute) and func.attr == "query"
        if is_select or is_query:
            m = _root_name(node.args[0])
            if m in TENANT_MODELS:
                hit.add(m)
    return hit


def _has_scope_guard(fn: ast.AST) -> bool:
    for node in ast.walk(fn):
        # A known guard call/attribute name anywhere in the body.
        if isinstance(node, ast.Name) and node.id in GUARD_NAMES:
            return True
        if isinstance(node, ast.Attribute) and node.attr in GUARD_NAMES:
            return True
        # An inline ``<Model>.org_id`` filter (e.g. .where(Meeting.org_id == ...)).
        if isinstance(node, ast.Attribute) and node.attr == "org_id":
            return True
    return False


def _iter_handlers():
    for path in HANDLER_MODULES:
        # Skip macOS AppleDouble sidecar files (._foo.py) that appear when the
        # repo lives on a non-HFS volume — they aren't real source.
        if not path.exists() or path.name.startswith("._"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            is_fn = isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            if is_fn and _is_route_handler(node):
                yield path, node


def test_handler_modules_discovered():
    """Guard against the glob silently matching nothing (e.g. a moved dir)."""
    handlers = list(_iter_handlers())
    assert len(handlers) >= 20, f"expected many route handlers, found {len(handlers)}"


def test_every_tenant_query_handler_is_scoped():
    unscoped: list[str] = []
    for path, fn in _iter_handlers():
        if fn.name in EXEMPT_HANDLERS:
            continue
        models = _queries_tenant_model(fn)
        if models and not _has_scope_guard(fn):
            rel = path.relative_to(APP.parent)
            unscoped.append(
                f"{rel}:{fn.lineno} {fn.name}() queries {sorted(models)} "
                "without a scope guard"
            )

    assert not unscoped, (
        "Route handler(s) query a tenant-owned model without an org/membership "
        "scope guard (cross-tenant IDOR risk). Add a scope guard, or allowlist "
        "with justification:\n  " + "\n  ".join(unscoped)
    )
