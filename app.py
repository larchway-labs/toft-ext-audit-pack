"""Audit Pack — the NIST SP 800-171 Rev 3 control mapping for Toft, and
the live evidence a personal administrator key can reach.

Two things live here, and the split is the point:

  The control document renders with NO configuration at all. It is true of any
  Toft install, so an administrator who has just deployed this can hand an
  assessor 97 mapped requirements before configuring anything.

  The evidence pack needs TOFT_URL and TOFT_TOKEN — a personal
  administrator API key — and even then reaches only 24 of the 37 evidence
  items. The other 13 are refused to every API key by the platform itself, or
  are screenshots. Those are reported as `needs_cli`, never as blanks: the rule
  this pack borrows from the platform it documents is that nothing is ever
  skipped and what cannot be seen is said out loud, on the page, always.
"""

from __future__ import annotations

import os
import re

from flask import Flask, Response, abort, render_template, request, send_file

from audit import collect, registry

app = Flask(__name__)

# Where the CLI tarballs live in this release. Served by the app itself rather
# than linked to a download host, because the install this product is built for
# is the one with no outbound HTTPS — an audit tool a customer cannot download
# is not a tool.
DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist")

PLATFORMS = [
    ("darwin_arm64", "macOS", "Apple silicon"),
    ("darwin_amd64", "macOS", "Intel"),
    ("linux_amd64", "Linux", "x86-64"),
    ("linux_arm64", "Linux", "arm64"),
    ("windows_amd64", "Windows", "x86-64"),
]


def _base() -> str:
    """The prefix every link on this page has to carry.

    An app behind Toft's proxy is served under /apps/{slug}. Links and form
    actions carry it; a redirect's Location must not, because the proxy re-adds
    it.
    """
    return request.headers.get("X-Forwarded-Prefix", "") or os.getenv("BASE_PATH", "")


def _detect_platform(ua: str) -> str:
    ua = (ua or "").lower()
    if "mac" in ua:
        # A browser on Apple silicon still reports Intel, so this is a guess and
        # the page says so beside the button rather than pretending otherwise.
        return "darwin_arm64"
    if "windows" in ua:
        return "windows_amd64"
    if "aarch64" in ua or "arm64" in ua:
        return "linux_arm64"
    return "linux_amd64"


def _available() -> dict:
    """Which tarballs this release actually carries, with their sizes."""
    out = {}
    for key, _, _ in PLATFORMS:
        path = os.path.join(DIST, f"toftaudit_{key}.tar.gz")
        if os.path.exists(path):
            out[key] = os.path.getsize(path)
    return out


@app.context_processor
def _inject():
    return {
        "base_path": _base(),
        "coverage": registry.coverage(),
        "resp_copy": registry.RESPONSIBILITY_COPY,
        "resp_order": registry.RESPONSIBILITIES,
    }


@app.route("/")
def index():
    avail = _available()
    detected = _detect_platform(request.headers.get("User-Agent", ""))
    if detected not in avail:
        detected = next(iter(avail), None)
    return render_template(
        "index.html",
        platforms=PLATFORMS,
        available=avail,
        detected=detected,
        install_url=os.environ.get("TOFT_URL", ""),
        configured=collect.Install().configured,
    )


@app.route("/controls")
def controls():
    which = request.args.get("responsibility") or ""
    fams = registry.families()
    if which in registry.RESPONSIBILITIES:
        fams = [
            {**f, "requirements": [r for r in f["requirements"] if r["responsibility"] == which]}
            for f in fams
        ]
        fams = [f for f in fams if f["requirements"]]
    return render_template("controls.html", families=fams, filter=which)


@app.route("/controls/<rid>")
def control(rid: str):
    # A path parameter, so it is validated rather than trusted — the ids are a
    # closed set and anything else is a 404, not a lookup.
    if not re.fullmatch(r"[0-9.]{1,12}", rid):
        abort(404)
    r = registry.requirement(rid)
    if r is None:
        abort(404)
    return render_template("control.html", r=r)


@app.route("/evidence")
def evidence():
    result = collect.collect(collect.Install())
    items = registry.evidence_items()
    rows = [result["items"][i] for i in items]
    return render_template("evidence.html", result=result, rows=rows)


@app.route("/download/<platform>")
def download(platform: str):
    if platform not in dict((k, 1) for k, _, _ in PLATFORMS):
        abort(404)
    path = os.path.join(DIST, f"toftaudit_{platform}.tar.gz")
    if not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True,
                     download_name=f"toftaudit_{platform}.tar.gz")


@app.route("/healthz")
def healthz():
    return Response("ok\n", mimetype="text/plain")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
