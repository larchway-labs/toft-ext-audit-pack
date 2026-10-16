# Audit Pack

Two documents for an assessment against **NIST SP 800-171 Revision 3**: what
Toft does about each of the 97 requirements, and what your install is
actually configured to do — read live, with the route each reading came from.

Deploy it like any other extension. The control mapping renders straight away
with no configuration at all: it is true of any Toft install, so you can
hand an assessor 97 mapped requirements before you set a single variable.

## The two halves, and why there are two

The gallery app renders the **control mapping** and as much **live evidence** as
a personal administrator API key can read. That is 24 of the 37 evidence items.

The other 13 need `toftaudit`, a small command-line program you download from the
app's own home page — **and that is a fact about Toft, not a limitation of
the app.** Toft refuses its most sensitive administrative reads to *every*
API key, by name, in its own `internal/api/keyroutes.go`. Verified against a
running install:

| Route | personal admin key | browser session |
|---|---|---|
| `GET /admin/estate/reach` | **403** | 200 |
| `GET /admin/auth-providers` | **403** | 200 |
| `GET /admin/api-keys` | **403** | 200 |
| `GET /admin/git-connections` | **403** | 200 |
| `GET /system/source-policy` | **403** | 200 |
| `GET /admin/telemetry-settings` | **403** | 200 |
| `GET /admin/email-settings` | **403** | 200 |
| `GET /admin/integration-settings` | **403** | 200 |
| `GET /deploy-keys` | **403** | 200 |
| `GET /admin/license` | **403** | 200 |
| `GET /system/checks` | 200 | 200 |
| `GET /admin/estate/targets` | 200 | 200 |

Those refusals are the identity, configuration-management and credential
evidence — the parts of 03.01, 03.04 and 03.05 an assessor asks for first. A
token in an app's environment cannot have them however it was minted, because
"a token must not be able to inspect tokens, or the blast radius of one leak is
every leak". A human administrator's browser session can. `toftaudit` holds one.

## Running the CLI

Download it from the app's home page — one click, served by the app itself, so
it works on an install with no outbound internet access. Then:

```bash
tar xzf toftaudit_linux_amd64.tar.gz

./toftaudit --url https://toft.example.com --out ./audit-2026-09-01
```

It prompts for the administrator username and password, signs in, reads every
evidence item, photographs the screens that matter, and writes the bundle.

**Running it unattended** — the password is never a flag, so it comes from the
environment:

```bash
LPAUDIT_USER=admin LPAUDIT_PASSWORD='…' \
  ./toftaudit --url https://toft.example.com --out ./audit-2026-09-01
```

**On an install where local sign-in is switched off** and everyone arrives
through an identity provider, sign in with your browser, copy the
`toft_session` cookie value from developer tools, and hand it over:

```bash
./toftaudit --url https://toft.example.com --out ./out --cookie 'eyJhbGci…'
```

**Without a browser on your machine**, everything else still collects:

```bash
./toftaudit --url https://toft.example.com --out ./out --no-screenshots
```

### What it writes

```
audit-2026-09-01/
  report.html      one self-contained page — no network needed to read it
  evidence.json    every raw reading, in full
  screenshots/     the admin screens, as a human would see them
  manifest.txt     SHA-256 of every file above
```

### Every flag

| Flag | Environment | Meaning |
|---|---|---|
| `--url` | `LPAUDIT_URL` | the install to read (required) |
| `--out` | | directory to write the bundle into (required) |
| `--user` | `LPAUDIT_USER` | administrator username; prompted if absent |
| | `LPAUDIT_PASSWORD` | password; prompted (without echo) if absent |
| `--cookie` | `LPAUDIT_COOKIE` | an existing `toft_session`, for an install with local sign-in off |
| `--no-screenshots` | | collect the readings, take no pictures |
| `--version` | | print the version and exit |

### What it does to your install

Nothing. It issues `GET`s only, and it sends `X-Toft-Scan: 1` so an
assessment does not appear in your traffic figures as a person who opened your
apps. It refuses to run as anything but a `system_admin`, because a run by a
viewer produces a bundle full of refusals that reads exactly like an install
with nothing configured.

## Configuring the app's own evidence page (optional)

Set these in the app's **Settings → Environment**:

| Variable | Value |
|---|---|
| `TOFT_URL` | this install's base URL, e.g. `https://toft.example.com` |
| `TOFT_TOKEN` | a personal API key (`toftu_…`) belonging to an administrator |

A long-lived administrator key living in an app's environment is a real standing
risk and it buys you 24 of 37 items. `toftaudit` holds a session that ends when it
exits and gets all 37. Prefer it. The control mapping needs neither.

## What is in this repository

| Path | What |
|---|---|
| `data/nist-800-171r3.json` | the catalog — **generated**, never hand-edited |
| `data/mapping.yaml` | Toft's answer to each of the 97 requirements |
| `data/evidence.yaml` | the 37 evidence items and which credential each needs |
| `tools/extract_catalog.py` | regenerates the catalog from NIST's OSCAL release |
| `dist/` | the `toftaudit` binaries the home page serves |
| `app.py`, `templates/` | the extension |

`toftaudit`'s **source is not here** — it lives in its own repository, and only
its binaries ship with this one. The three files in `data/` are canonical here
and copied into that repository by a script that refuses on a checksum
mismatch, because the one structural guarantee this project makes is that the
control narrative and the evidence collector cannot disagree about what the
controls are.

Regenerating the catalog:

```bash
python3 tools/extract_catalog.py     # fetches NIST's current OSCAL release
```

## Honest limits

- **This is audit support.** It is not a certification, not an attestation, and
  not a substitute for an assessment.
- **Requirement ids, titles and statement text are NIST's, verbatim.**
  Everything under *How Toft addresses it* and *What you must still do* is
  this project's assertion, and is exactly what an assessor should test rather
  than take on trust.
- **The responsibility split is the document.** 21 requirements are Toft's,
  49 are shared, 8 are inherited from the layer below, and 19 have nothing to do
  with Toft at all. A pack claiming all 97 would be worthless.
- **Two shared items matter more than the rest.** MFA is the identity provider's
  and the built-in local administrator will not be covered by it; and app-to-app
  isolation in *shared* execution mode is an accepted risk that origin isolation
  must never be cited against. Both are stated on their requirement pages.
- **18 of the catalog's 88 organization-defined parameters** are bound to a live
  setting on your install. 25 more are noted as yours, and 44 are not addressed
  by this pack. That last number is shown on the page, because a coverage figure
  you cannot see is a coverage figure you cannot trust.
