"""Load and join the three registries.

Nothing here talks to a Toft install. This module answers "what are the
controls, what would prove them, and which credential class does each proof
need" — questions with the same answer on every install, which is why the
control document renders with no configuration at all.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache

import yaml

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# The four values of `responsibility`, in the order a reader should meet them:
# what the platform does, what it shares, what sits below it, and what it has no
# part in. Rendered in this order everywhere so the honest half is never buried.
RESPONSIBILITIES = ["platform", "shared", "inherited", "customer"]

RESPONSIBILITY_COPY = {
    "platform": (
        "Toft implements it",
        "The install's own configuration is the evidence, and this pack reads it.",
    ),
    "shared": (
        "Toft provides the mechanism; you operate it",
        "Both halves are stated. The platform half is evidenced here; the "
        "organizational half is yours to record.",
    ),
    "inherited": (
        "Satisfied below Toft",
        "The host, the cluster, the facility or the identity provider. Toft "
        "neither implements nor weakens it — assess it at that layer.",
    ),
    "customer": (
        "Toft has no part in it",
        "Said plainly rather than padded. Cite your own programme.",
    ),
}


@lru_cache(maxsize=1)
def catalog() -> dict:
    with open(os.path.join(DATA, "nist-800-171r3.json")) as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def mapping() -> dict:
    with open(os.path.join(DATA, "mapping.yaml")) as fh:
        return yaml.safe_load(fh)


@lru_cache(maxsize=1)
def evidence_items() -> dict:
    with open(os.path.join(DATA, "evidence.yaml")) as fh:
        doc = yaml.safe_load(fh)
    return {i["id"]: i for i in doc["items"]}


@lru_cache(maxsize=1)
def requirements() -> list:
    """Every requirement, with its mapping joined on and its evidence resolved.

    A requirement with no mapping entry would be a hole in the document, so the
    join is asserted rather than defaulted: the registries are validated
    together at import time and a missing id is a startup failure, not a blank
    section somebody notices during an assessment.
    """
    m = mapping()["requirements"]
    ev = evidence_items()
    out = []
    for r in catalog()["requirements"]:
        entry = m.get(r["id"])
        if entry is None:
            raise RuntimeError(
                f"requirement {r['id']} has no mapping entry — the control "
                "document would render a blank section for it"
            )
        row = dict(r)
        row["responsibility"] = entry["responsibility"]
        row["summary"] = entry.get("summary", "")
        row["mechanism"] = entry.get("mechanism")
        row["customer"] = entry.get("customer")
        row["refs"] = entry.get("refs") or []
        row["evidence"] = [ev[e] for e in (entry.get("evidence") or [])]
        # ODP bindings, joined onto the catalog's own parameter list so a
        # parameter the mapping never addressed is still visible as a gap.
        binds = entry.get("odp") or {}
        odps = []
        for p in r["odps"]:
            b = binds.get(p["id"]) or {}
            odps.append(
                {
                    **p,
                    "bound_to": ev.get(b.get("evidence")) if b.get("evidence") else None,
                    "field": b.get("field"),
                    "value": b.get("value"),
                    "note": b.get("note"),
                    "state": (
                        "bound" if b.get("evidence")
                        else "stated" if b.get("value")
                        else "noted" if b
                        else "unaddressed"
                    ),
                }
            )
        row["odps"] = odps
        out.append(row)
    return out


@lru_cache(maxsize=1)
def families() -> list:
    """Families with their requirements attached, in catalog order."""
    by = {}
    for r in requirements():
        by.setdefault(r["family"], []).append(r)
    return [
        {**f, "requirements": by.get(f["code"], [])}
        for f in catalog()["families"]
    ]


@lru_cache(maxsize=1)
def coverage() -> dict:
    """The document's own account of itself.

    Summed from the rows rather than written down, on the platform's own rule:
    a coverage figure a human maintains is a coverage figure that goes stale.
    """
    reqs = requirements()
    ev = evidence_items().values()
    odps = [o for r in reqs for o in r["odps"]]
    return {
        "requirements": len(reqs),
        "families": len(catalog()["families"]),
        "by_responsibility": {
            k: sum(1 for r in reqs if r["responsibility"] == k) for k in RESPONSIBILITIES
        },
        "evidence_total": len(evidence_items()),
        "evidence_by_key": sum(1 for i in ev if i["credential"] == "key"),
        "evidence_by_session": sum(1 for i in ev if i["credential"] == "session"),
        "odp_total": len(odps),
        "odp_bound": sum(1 for o in odps if o["state"] == "bound"),
        "odp_stated": sum(1 for o in odps if o["state"] == "stated"),
        "odp_noted": sum(1 for o in odps if o["state"] == "noted"),
        "odp_unaddressed": sum(1 for o in odps if o["state"] == "unaddressed"),
    }


def requirement(rid: str):
    for r in requirements():
        if r["id"] == rid:
            return r
    return None
