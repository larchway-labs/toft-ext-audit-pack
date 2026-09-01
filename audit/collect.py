"""Read live evidence from a Launchpad install with a personal admin key.

This is the extension's half of the collection. It can only reach the evidence
items marked `credential: key` — the twelve marked `session` are refused to
every API key by name in the platform's own keyroutes.go, and no amount of
trying here will change that. So they are reported as `needs_cli`, which is a
STATE and not a failure: the pack's rule, taken from the platform it documents,
is that nothing is ever skipped and what cannot be seen is said out loud.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from . import registry

TIMEOUT = 20


class Install:
    """A Launchpad install, addressed with a personal administrator API key."""

    def __init__(self, base_url: str | None = None, token: str | None = None):
        self.base = (base_url or os.environ.get("LAUNCHPAD_URL", "")).rstrip("/")
        self.token = token or os.environ.get("LAUNCHPAD_TOKEN", "")

    @property
    def configured(self) -> bool:
        return bool(self.base and self.token)

    def get(self, route: str, params: dict | None = None):
        """One GET. Returns (ok, payload_or_reason, status)."""
        url = self.base + route
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + self.token,
            "Accept": "application/json",
            # A read taken for an audit is not somebody using the app, and the
            # platform has a header that says so. It grants nothing.
            "X-Launchpad-Scan": "1",
        })
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return True, json.loads(resp.read().decode()), resp.status
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode()[:400]
            except Exception:
                pass
            return False, f"HTTP {e.code}: {body or e.reason}", e.code
        except Exception as e:  # noqa: BLE001 — any transport failure is one state
            return False, f"{type(e).__name__}: {e}", 0


# The route each key-reachable item is actually fetched from. Kept beside the
# registry rather than inside it because the registry is the shared, language
# neutral statement of WHAT the evidence is; this is the Python client's HOW.
FETCH = {
    "install_identity": ("/api/v1/system/health", None),
    "install_settings": ("/api/v1/system/settings", None),
    "install_checks": ("/api/v1/system/checks", None),
    "users_and_roles": ("/api/v1/users", None),
    "groups_and_members": ("/api/v1/groups", None),
    "apps_and_visibility": ("/api/v1/apps", None),
    "audit_recent": ("/api/v1/admin/audit", {"limit": 200}),
    "estate_languages": ("/api/v1/admin/estate/languages", None),
    "estate_targets": ("/api/v1/admin/estate/targets", None),
    "processes": ("/api/v1/system/processes", None),
    "openapi": ("/api/v1/admin/openapi.json", None),
    "dependency_findings": ("/api/v1/admin/dependencies", None),
    "dependency_inventory": ("/api/v1/admin/packages", None),
    "storage_resources": ("/api/v1/admin/storage", None),
    "auth_providers_public": ("/api/v1/auth/providers", None),
}

# Items whose reading is a projection of another item rather than its own
# request — every settings-derived item is a slice of one document, and asking
# fifteen times for the same response would be a worse artifact, not a better
# one.
FROM_SETTINGS = {
    "setting_anonymous_access", "setting_listable", "setting_sessions",
    "setting_dormancy", "setting_refusal_copy", "setting_retention",
    "setting_api_keys", "setting_dependency_policy",
}

AUDIT_CATEGORIES = ["deploys", "access", "signins", "settings", "system"]


def collect(install: Install) -> dict:
    """Everything a personal admin key can read, plus an honest account of the rest."""
    started = datetime.now(timezone.utc)
    items = registry.evidence_items()
    results: dict[str, dict] = {}

    if not install.configured:
        for iid, item in items.items():
            results[iid] = _state(item, "unconfigured",
                                  "No LAUNCHPAD_URL and LAUNCHPAD_TOKEN set on this app.")
        return _wrap(started, results, install, configured=False)

    settings = None
    for iid, item in items.items():
        cred = item["credential"]

        if cred == "session":
            results[iid] = _state(
                item, "needs_cli",
                "Refused to every API key by name in the platform's keyroutes.go. "
                "Only a browser session reaches it — run lpaudit.")
            continue

        if item.get("source", {}).get("kind") == "screenshot":
            results[iid] = _state(item, "needs_cli",
                                  "A screenshot. Only lpaudit can take it.")
            continue

        if iid in FROM_SETTINGS:
            continue  # filled in below, from the one settings read

        if iid == "audit_by_category":
            per = {}
            for cat in AUDIT_CATEGORIES:
                ok, payload, _ = install.get("/api/v1/admin/audit",
                                             {"category": cat, "limit": 5})
                per[cat] = _summarize_audit(payload) if ok else {"error": payload}
            results[iid] = _state(item, "ok", None, value=per)
            continue

        if iid == "user_access_review":
            ok, users, _ = install.get("/api/v1/users")
            if not ok:
                results[iid] = _state(item, "error", str(users))
                continue
            rows = users if isinstance(users, list) else users.get("users", [])
            per = {}
            for u in rows[:50]:
                uid = u.get("id")
                if not uid:
                    continue
                ok2, acc, _ = install.get(f"/api/v1/users/{uid}/access")
                per[u.get("username") or uid] = acc if ok2 else {"error": acc}
            results[iid] = _state(item, "ok", None, value=per)
            continue

        route, params = FETCH.get(iid, (None, None))
        if route is None:
            results[iid] = _state(item, "not_collected",
                                  "No fetch defined for this item in the extension.")
            continue

        ok, payload, status = install.get(route, params)
        if ok:
            results[iid] = _state(item, "ok", None, value=_shrink(iid, payload))
            if iid == "install_settings":
                settings = payload
        elif status == 404:
            # 404 is the platform's answer for a capability this install does
            # not have, and for a route this caller may not read. Both are a
            # STATE. Absent is not a failure and must never render as one.
            results[iid] = _state(item, "absent",
                                  "404 — this install does not offer that capability, "
                                  "or this credential may not read it.")
        else:
            results[iid] = _state(item, "error", str(payload))

    # The settings projections, from the single settings document.
    for iid in FROM_SETTINGS:
        item = items[iid]
        if settings is None:
            results[iid] = _state(item, "error", "The settings document could not be read.")
            continue
        fields = item.get("source", {}).get("fields") or []
        results[iid] = _state(item, "ok", None,
                              value={f: settings.get(f) for f in fields})

    return _wrap(started, results, install, configured=True)


def _state(item, state, reason, value=None):
    return {
        "id": item["id"], "label": item["label"], "credential": item["credential"],
        "route": item.get("source", {}).get("route"),
        "screen": item.get("screen"),
        "reading": (item.get("reading") or "").strip(),
        "state": state, "reason": reason, "value": value,
    }


def _summarize_audit(payload):
    """Counts and the newest row's action, never the rows themselves.

    The audit feed names people and objects. The extension's job is to show that
    each category is populated on this install — a count and one action string
    does that without reproducing a governance log into a page anybody who can
    open this app could read.
    """
    rows = payload.get("entries") or payload.get("items") or payload.get("audit") or []
    if isinstance(payload, list):
        rows = payload
    return {"sampled": len(rows),
            "newest_action": (rows[0].get("action") if rows else None)}


def _shrink(iid, payload):
    """Keep a page-sized reading. The full document is the CLI's bundle."""
    if iid == "openapi":
        paths = payload.get("paths") or {}
        return {"paths": len(paths),
                "operations": sum(len(v) for v in paths.values() if isinstance(v, dict))}
    if iid == "audit_recent":
        return _summarize_audit(payload)
    if iid == "install_settings":
        return {"keys": len(payload) if isinstance(payload, dict) else None}
    if isinstance(payload, list):
        return {"rows": len(payload)}
    return payload


def _wrap(started, results, install, configured):
    by_state: dict[str, int] = {}
    for r in results.values():
        by_state[r["state"]] = by_state.get(r["state"], 0) + 1
    return {
        "collected_at": started.isoformat(),
        "base_url": install.base or None,
        "configured": configured,
        "items": results,
        "by_state": by_state,
    }
