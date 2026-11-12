"""Read-only official legal-source connectivity and identity probe for ALBA 2.0.

This is intentionally NOT a legal status or consolidated-version verifier.
A reachable official URL and a matching act identifier are necessary but not
sufficient to certify that a version is current and legally applicable.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from html.parser import HTMLParser
import json
import re
from typing import Callable
from urllib.parse import urljoin, urlsplit

import requests

MAX_RESPONSE_BYTES = 1_000_000
MAX_REDIRECTS = 2
ALLOWED_HOSTS = {
    "AL": {"qbz.gov.al", "www.qbz.gov.al"},
    "EU": {"eur-lex.europa.eu", "publications.europa.eu", "data.europa.eu"},
}
CELEX = re.compile(r"^[03][0-9]{4}[A-Z][0-9]{4}(?:-[0-9]{8})?$")
QBZ_ELI = re.compile(
    r"^/eli/(?:ligj|vendim|udhezim|urdher|dekret|rregullore)/"
    r"[0-9]{4}/[0-9]{2}/[0-9]{2}/[0-9]+(?:-[0-9]+)?/?$"
)
VERSION = re.compile(
    r"Versioni\s+([0-9]+)\s*,\s*n[ëe]\s+fuqi\s+nga\s+"
    r"([0-9]{2})/([0-9]{2})/([0-9]{4})",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class ProbeResult:
    case_id: str
    jurisdiction: str
    source_url: str
    checked_at_utc: str
    outcome: str
    identity_observed: bool
    candidate_version_date: str | None
    # QBZ publishes both a version timeline and the "Ndryshuar nga"
    # cross-reference list. They are distinct evidence streams.
    qbz_version_candidates: list[dict[str, str]]
    qbz_amending_acts_declared: int | None
    qbz_amending_acts_observed: list[dict[str, str]]
    version_verified: bool
    status_verified: bool
    details: str

    # version_verified/status_verified are deliberately ALWAYS False in
    # this phase: full legal-effect verification needs the actual texts,
    # amending acts, corrigenda, and commencement/application checks.


class VisibleText(HTMLParser):
    """Extract visible text, not script-embedded app code or metadata claims."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hidden_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.hidden_depth = max(0, self.hidden_depth - 1)

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            self.parts.append(data)

    def extract(self, html: str) -> str:
        self.feed(html)
        return re.sub(r"\s+", " ", " ".join(self.parts)).strip()


def validate_official_url(url: str, jurisdiction: str) -> None:
    if jurisdiction not in ALLOWED_HOSTS:
        raise ValueError("Unsupported jurisdiction.")
    p = urlsplit(url)
    if (p.scheme != "https" or p.hostname not in ALLOWED_HOSTS[jurisdiction]
            or p.username or p.password or p.port not in {None, 443}
            or p.fragment):
        raise ValueError("Not an allowed official HTTPS source.")
    if jurisdiction == "AL" and not QBZ_ELI.fullmatch(p.path):
        raise ValueError("Not a canonical QBZ ELI act path.")
    if jurisdiction == "EU":
        if p.hostname == "eur-lex.europa.eu":
            if p.path != "/legal-content/EN/TXT/" or not re.fullmatch(
                r"uri=CELEX%3A[03][0-9]{4}[A-Z][0-9]{4}(?:-[0-9]{8})?",
                p.query, flags=re.IGNORECASE
            ):
                raise ValueError("Expected an exact CELEX text URL.")
        elif p.hostname == "publications.europa.eu":
            if not re.fullmatch(r"/resource/celex/[03][0-9]{4}[A-Z][0-9]{4}(?:-[0-9]{8})?", p.path):
                raise ValueError("Expected a Cellar CELEX resource.")
        else:
            raise ValueError("Unsupported EU document endpoint for this pilot.")


def _qbz_version_candidates(text: str) -> list[dict[str, str]]:
    """Observe the version timeline without certifying any version as current."""
    versions: dict[int, str] = {}
    for number, day, month, year in VERSION.findall(text):
        try:
            when = date(int(year), int(month), int(day)).isoformat()
        except ValueError:
            continue
        versions[int(number)] = when
    return [
        {"version": str(number), "effective_from": when}
        for number, when in sorted(versions.items(), key=lambda item: item[0])
    ]


def _qbz_amending_acts(text: str) -> tuple[int | None, list[dict[str, str]]]:
    """Read QBZ 'Ndryshuar nga' in Ndërvarësia, excluding other relations.

    The displayed count and extracted references are *observations*, not
    confirmation that amendments were incorporated into the latest version.
    """
    relation_marker = re.search(r"Nd[ëe]rvar[ëe]sia", text, re.IGNORECASE)
    if relation_marker is None:
        return None, []
    relations = text[relation_marker.end():]
    match = re.search(
        r"Ndryshuar\s+nga\s*\(\s*(\d+)\s*\)", relations, re.IGNORECASE,
    )
    if match is None:
        return None, []
    declared = int(match.group(1))
    section = relations[match.end():]
    # Other linked acts (e.g. 'Bazë ligjore për') are NOT amendments.
    section = re.split(r"Baz[ëe]\s+ligjore\s+p[ëe]r", section, 1, flags=re.IGNORECASE)[0]
    act_pattern = re.compile(
        r"(Ligj|Vendim|Udh[ëe]zim|Urdh[ëe]r|Dekret)\s+nr\.\s*"
        r"(\d+(?:/\d+)?)\s*,\s*dat[ëe]\s*(\d{2}/\d{2}/\d{4})",
        re.IGNORECASE,
    )
    seen: set[tuple[str, str, str]] = set()
    observed: list[dict[str, str]] = []
    for kind, number, when in act_pattern.findall(section):
        key = (kind.casefold(), number, when)
        if key in seen:
            continue
        seen.add(key)
        observed.append({"type": kind, "number": number, "date": when})
    return declared, observed


def _candidate_version(versions: list[dict[str, str]], as_of: date) -> str | None:
    applicable = [
        date.fromisoformat(item["effective_from"])
        for item in versions
        if date.fromisoformat(item["effective_from"]) <= as_of
    ]
    return max(applicable).isoformat() if applicable else None


def probe_case(
    case: dict, *, get: Callable | None = None, as_of: date | None = None
) -> ProbeResult:
    """Test source accessibility and limited visible identity, fail closed."""
    source, jurisdiction = case["url"], case["jurisdiction"]
    validate_official_url(source, jurisdiction)
    as_of = as_of or date.today()
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    identity = False
    candidate = None
    version_candidates: list[dict[str, str]] = []
    amendments_declared: int | None = None
    amendments_observed: list[dict[str, str]] = []
    outcome, details = "unavailable", "Source was not fetched."
    fetch = get or requests.get
    current = source
    try:
        for _ in range(MAX_REDIRECTS + 1):
            response = fetch(
                current, timeout=12, allow_redirects=False,
                headers={"User-Agent": "ALBA-Source-Probe/0.1 (read-only legal research)"},
            )
            if 300 <= response.status_code < 400:
                location = response.headers.get("Location")
                if not location:
                    outcome, details = "redirect_error", "Redirect has no Location header."
                    break
                target = urljoin(current, location)
                # Redirecting to an arbitrary domain is never allowed.
                try:
                    validate_official_url(target, jurisdiction)
                except ValueError:
                    outcome, details = "redirect_blocked", "Redirect target is not an allowed legal document URL."
                    break
                current = target
                continue
            if response.status_code != 200:
                outcome, details = "http_error", f"Official source returned HTTP {response.status_code}."
                break
            content_type = response.headers.get("Content-Type", "").split(";")[0].lower()
            if content_type not in {"text/html", "application/xhtml+xml", "text/plain"}:
                outcome, details = "unsupported_format", "The response is not readable HTML/text."
                break
            if len(response.content) > MAX_RESPONSE_BYTES:
                outcome, details = "too_large", "Response exceeds the pilot size limit."
                break
            text = VisibleText().extract(response.text) if "html" in content_type else response.text
            if "verify that you're not a robot" in text.casefold():
                outcome, details = "access_challenge", "Official site requested browser verification."
                break
            if jurisdiction == "AL":
                # Full title/status/version cannot be inferred merely from the
                # presence of a permalink. The version is only a candidate.
                expected_num = urlsplit(source).path.rstrip("/").split("/")[-1]
                identity = bool(
                    re.search(r"Nr\.\s*i\s*aktit\s*[:\s]*" + re.escape(expected_num) + r"\b", text, re.I)
                    and re.search(r"Data\s+e\s+aktit", text, re.I)
                    and "Permalink ELI" in text
                )
                if identity:
                    version_candidates = _qbz_version_candidates(text)
                    candidate = _candidate_version(version_candidates, as_of)
                    amendments_declared, amendments_observed = _qbz_amending_acts(text)
            else:
                celex = re.search(r"CELEX%3A([03][0-9]{4}[A-Z][0-9]{4}(?:-[0-9]{8})?)", source, re.I)
                if not celex:
                    celex = re.search(r"/celex/([03][0-9]{4}[A-Z][0-9]{4}(?:-[0-9]{8})?)", source, re.I)
                identity = bool(celex and celex.group(1).upper() in text.upper())
            outcome = "identity_candidate" if identity else "document_unconfirmed"
            details = (
                "Visible metadata may identify the act; the current consolidated "
                "text and amendments have NOT been verified."
                if identity else
                "HTTP 200 is insufficient: the official legal document identity "
                "could not be confirmed from the visible response."
            )
            break
        else:
            outcome, details = "redirect_error", "Too many redirects."
    except (requests.RequestException, OSError, ValueError) as exc:
        outcome, details = "network_error", type(exc).__name__ + ": source could not be fetched."
    return ProbeResult(
        case_id=str(case["id"]), jurisdiction=jurisdiction, source_url=source,
        checked_at_utc=checked_at, outcome=outcome,
        identity_observed=identity, candidate_version_date=candidate,
        qbz_version_candidates=version_candidates,
        qbz_amending_acts_declared=amendments_declared,
        qbz_amending_acts_observed=amendments_observed,
        version_verified=False, status_verified=False, details=details,
    )


def run_manifest(manifest: list[dict], *, get: Callable | None = None) -> list[ProbeResult]:
    """Run explicit cases; never imply that these read-only probes certify law."""
    if not isinstance(manifest, list) or len(manifest) > 50:
        raise ValueError("Manifest must be a list of at most 50 cases.")
    if len({item["id"] for item in manifest}) != len(manifest):
        raise ValueError("Duplicate case IDs.")
    return [probe_case(item, get=get) for item in manifest]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ALBA official-source connectivity pilot (NO legal certification)")
    parser.add_argument("--manifest", default="tests/fixtures/legal_source_pilot_20.json")
    parser.add_argument("--output", default="", help="Optional output JSON path")
    args = parser.parse_args()
    with open(args.manifest, encoding="utf-8") as stream:
        cases = json.load(stream)
    report = {
        "disclaimer": "Connectivity/identity probe only; no status or consolidated version is verified.",
        "results": [asdict(item) for item in run_manifest(cases)],
    }
    raw = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as stream:
            stream.write(raw + "\n")
    else:
        print(raw)
