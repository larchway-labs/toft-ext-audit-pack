#!/usr/bin/env python3
"""Regenerate data/nist-800-171r3.json from NIST's OSCAL release.

The catalog in data/ is GENERATED, never hand-edited — the same rule Launchpad
applies to its own schema snapshot. Run this to refresh it:

    python3 tools/extract_catalog.py            # fetches from NIST
    python3 tools/extract_catalog.py FILE.json  # from a local OSCAL file

Requirement ids, titles and statement text must stay verbatim. The only
transformations applied are the two below, and both are removals of OSCAL
plumbing that would otherwise render as noise in a document a human reads.
"""

import json
import re
import sys
import urllib.request

SOURCE = ("https://raw.githubusercontent.com/usnistgov/oscal-content/main/"
          "nist.gov/SP800-171/rev3/json/NIST_SP800-171_rev3_catalog-min.json")

OUT = "data/nist-800-171r3.json"


def clean(s):
    """Remove OSCAL's two in-prose plumbing forms. Nothing else is touched.

    1. Parameter placeholders. `{{ insert: param, A.03.01.01.ODP.01 }}` becomes
       `[A.03.01.01.ODP.01]`, because the reader needs to see WHICH parameter
       the sentence depends on — that is the whole point of the ODP table
       beside it — and the mustache form is machine syntax.

    2. Empty cross-reference links. The discussions carry
       `[](#/cprt/framework/version/SP_800_171_3_0_0/home?element=03.01.02)03.01.02`,
       which is a link with no text followed by the text it should have had. It
       renders as a wall of URL in the middle of a sentence. The link target is
       another requirement in this same document, which this pack already
       cross-links by id, so the URL carries nothing and the id after it is the
       actual content.
    """
    if not s:
        return s
    s = re.sub(r"\{\{\s*insert:\s*param,\s*([^}]+?)\s*\}\}", r"[\1]", s)
    s = re.sub(r"\[\]\(#?[^)]*\)", "", s)          # empty link, keep what follows
    s = re.sub(r"\[([^\]]+)\]\(#?[^)]*\)", r"\1", s)  # linked text, keep the text
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip()


def main():
    if len(sys.argv) > 1:
        raw = open(sys.argv[1], "rb").read()
        src = sys.argv[1]
    else:
        with urllib.request.urlopen(SOURCE, timeout=60) as r:
            raw = r.read()
        src = SOURCE

    cat = json.loads(raw)["catalog"]
    out = {
        "catalog": "NIST SP 800-171 Revision 3",
        "source": src,
        "oscal_version": cat["metadata"].get("version"),
        "oscal_last_modified": cat["metadata"].get("last-modified"),
        "generated_by": "tools/extract_catalog.py",
        "families": [],
        "requirements": [],
    }

    for g in cat["groups"]:
        code = g["id"].replace("SP_800_171_", "")
        out["families"].append({"code": code, "title": g["title"]})
        for c in g.get("controls", []):
            # Withdrawn requirements are not requirements. Rev 3 withdrew 33 of
            # them and a document listing them would be describing Rev 2.
            if any(p.get("name") == "status" and p.get("value") == "withdrawn"
                   for p in c.get("props", [])):
                continue

            stmt, objectives = [], []

            def walk(parts, depth=0):
                for p in parts:
                    if p.get("name") == "item":
                        lbl = next((x["value"] for x in p.get("props", [])
                                    if x["name"] == "label"), None)
                        stmt.append({"label": lbl, "prose": clean(p.get("prose")),
                                     "depth": depth})
                        walk(p.get("parts", []), depth + 1)
                    elif p.get("name") == "assessment-objective":
                        objectives.append(clean(p.get("prose")))

            guidance = None
            for p in c.get("parts", []):
                if p.get("name") == "statement":
                    walk(p.get("parts", []))
                    if p.get("prose"):
                        stmt.insert(0, {"label": None, "prose": clean(p["prose"]),
                                        "depth": 0})
                elif p.get("name") == "guidance" and guidance is None:
                    guidance = clean(p.get("prose"))
                elif p.get("name") == "assessment-objective":
                    objectives.append(clean(p.get("prose")))

            out["requirements"].append({
                "id": c["id"].replace("SP_800_171_", ""),
                "family": code,
                "family_title": g["title"],
                "title": c["title"],
                "statement": stmt,
                "odps": [{
                    "id": prm["id"],
                    "label": prm.get("label"),
                    "usage": prm.get("usage"),
                    "guideline": clean((prm.get("guidelines") or [{}])[0].get("prose")),
                } for prm in c.get("params", [])],
                "guidance": guidance,
                "objectives": [o for o in objectives if o],
            })

    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1)
        fh.write("\n")

    print(f"{OUT}: {len(out['requirements'])} requirements, "
          f"{len(out['families'])} families, "
          f"{sum(len(r['odps']) for r in out['requirements'])} ODPs, "
          f"{sum(len(r['objectives']) for r in out['requirements'])} objectives")


if __name__ == "__main__":
    main()
