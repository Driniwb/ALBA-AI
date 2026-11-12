"""Read-only EUR-Lex/Cellar source evidence connector for ALBA 2.0.

Uses the official Publications Office SPARQL metadata service and Cellar
document resolver. This module does NOT certify which provisions are in force.
It records consolidated-text candidates, amending-act references, and the
actual retrieved text, without conflating a consolidation with authentic OJ law.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import json
import re
from typing import Callable
from urllib.parse import urljoin, urlsplit

import requests

SPARQL_URL = "https://publications.europa.eu/webapi/rdf/sparql"
CONTENT_ROOT = "https://publications.europa.eu/resource/celex/"
EU_LEGAL_URL = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A"
ALLOWED_HOSTS = frozenset({"publications.europa.eu", "eur-lex.europa.eu"})
BASE_CELEX = re.compile(r"^3\d{4}[LRD]\d{4}$")
CONSOLIDATED = re.compile(r"^0\d{4}[LRD]\d{4}-(\d{8})$")
MAX_SPARQL_BYTES = 450_000
MAX_DOCUMENT_BYTES = 5_000_000
MAX_DOCUMENT_CHARS = 750_000
MAX_ROWS = 100
MAX_REDIRECTS = 3


@dataclass(frozen=True)
class CellarEvidence:
    base_celex: str
    as_of: str
    checked_at_utc: str
    official_base_url: str
    metadata_endpoint: str
    observed_consolidations: list[str]
    selected_consolidation: str | None
    observed_amendments: list[str]
    consolidated_document_url: str | None
    text_sha256: str | None
    extracted_characters: int
    document_identity_observed: bool
    metadata_complete: bool
    content_retrieved: bool
    # Do not set true without authentic OJ, repeal, corrigendum, and
    # provision-level effective-date reconciliations.
    version_verified: bool
    legal_status_verified: bool
    outcome: str
    warnings: list[str]


class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in {"script", "style", "svg", "noscript"}:
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "svg", "noscript"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data: str) -> None:
        if not self.hidden and data.strip():
            self.blocks.append(data)

    def plain_text(self, html: str) -> str:
        self.feed(html)
        return re.sub(r"\s+", " ", " ".join(self.blocks)).strip()


def _validate_celex(celex: str) -> str:
    if not isinstance(celex, str) or not BASE_CELEX.fullmatch(celex):
        raise ValueError("Expected a base EU legislation CELEX such as 32010L0035.")
    return celex


def consolidation_query(base_celex: str) -> str:
    """Both documented consolidated-to-base CDM predicates are supported."""
    c = _validate_celex(base_celex)
    return (
        "PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>\n"
        "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n"
        "SELECT DISTINCT ?celex WHERE {\n"
        f'  ?base cdm:resource_legal_id_celex "{c}"^^xsd:string .\n'
        "  { ?cons cdm:act_consolidated_consolidates_resource_legal ?base . }\n"
        "  UNION\n"
        "  { ?cons cdm:act_consolidated_based_on_resource_legal ?base . }\n"
        "  ?cons cdm:resource_legal_id_celex ?celex .\n"
        f'  FILTER(STRSTARTS(STR(?celex), "0{c[1:]}-"))\n'
        "} ORDER BY DESC(?celex) LIMIT 100"
    )


def amendments_query(base_celex: str) -> str:
    c = _validate_celex(base_celex)
    return (
        "PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>\n"
        "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n"
        "SELECT DISTINCT ?celex WHERE {\n"
        f'  ?base cdm:resource_legal_id_celex "{c}"^^xsd:string .\n'
        "  ?amendment cdm:resource_legal_amends_resource_legal ?base ;\n"
        "             cdm:resource_legal_id_celex ?celex .\n"
        "} ORDER BY DESC(?celex) LIMIT 100"
    )


def _sparql_rows(query: str, *, post: Callable) -> tuple[list[str], bool]:
    response = post(
        SPARQL_URL, data={"query": query}, timeout=28,
        allow_redirects=False, headers={
            "Accept": "application/sparql-results+json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "ALBA-Official-Legal-Research/0.2",
        },
    )
    if response.status_code != 200:
        raise ValueError("Official Cellar SPARQL HTTP " + str(response.status_code))
    if len(response.content) > MAX_SPARQL_BYTES:
        raise ValueError("Cellar metadata response exceeded safe size limit.")
    content_type = response.headers.get("Content-Type", "").lower()
    if "json" not in content_type:
        raise ValueError("Cellar did not return SPARQL JSON metadata.")
    result = response.json()
    if not isinstance(result, dict):
        raise ValueError("Invalid Cellar SPARQL response.")
    bindings = result.get("results", {}).get("bindings")
    if not isinstance(bindings, list) or len(bindings) > MAX_ROWS:
        raise ValueError("Incomplete or invalid Cellar metadata bindings.")
    rows = []
    for item in bindings:
        obj = item.get("celex") if isinstance(item, dict) else None
        value = obj.get("value") if isinstance(obj, dict) else None
        if not isinstance(value, str):
            raise ValueError("Cellar metadata includes an invalid CELEX binding.")
        rows.append(value)
    # The last row could mask additional versions or amending acts.
    return rows, len(bindings) < MAX_ROWS


def select_consolidation(
    base_celex: str, observed: list[str], as_of: date
) -> tuple[str | None, list[str]]:
    _validate_celex(base_celex)
    prefix = "0" + base_celex[1:] + "-"
    candidates = []
    for entry in observed:
        matched = CONSOLIDATED.fullmatch(entry)
        if not matched or not entry.startswith(prefix):
            raise ValueError("Consolidation response contains an unexpected CELEX.")
        try:
            effective = date.fromisoformat(
                matched.group(1)[:4] + "-" + matched.group(1)[4:6] +
                "-" + matched.group(1)[6:]
            )
        except ValueError as exc:
            raise ValueError("Consolidation CELEX has invalid date.") from exc
        if effective <= as_of:
            candidates.append((effective, entry))
    chosen = max(candidates)[1] if candidates else None
    return chosen, sorted(set(observed))


def _approved_url(url: str) -> bool:
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS
            or parsed.username or parsed.password or parsed.port not in (None, 443)
            or parsed.fragment):
        return False
    if parsed.hostname == "publications.europa.eu":
        return parsed.path.startswith("/resource/celex/") or parsed.path.startswith(
            "/resource/cellar/"
        )
    return parsed.path.startswith("/legal-content/")


def _download_text(celex: str, *, get: Callable) -> tuple[str, str]:
    url = CONTENT_ROOT + celex + "?language=en"
    for _ in range(MAX_REDIRECTS + 1):
        if not _approved_url(url):
            raise ValueError("Source redirected outside official permitted content URLs.")
        r = get(url, timeout=25, allow_redirects=False, headers={
            "Accept": "application/xhtml+xml,text/html;q=0.9",
            "Accept-Language": "en",
            "User-Agent": "ALBA-Official-Legal-Research/0.2",
        })
        if r.status_code in {301, 302, 303, 307, 308}:
            location = r.headers.get("Location")
            if not location:
                raise ValueError("Official source redirect had no destination.")
            url = urljoin(url, location)
            continue
        if r.status_code != 200:
            raise ValueError("Official Cellar document HTTP " + str(r.status_code))
        if len(r.content) > MAX_DOCUMENT_BYTES:
            raise ValueError("Document exceeds text retrieval limit.")
        type_value = r.headers.get("Content-Type", "").lower()
        if not any(tag in type_value for tag in ("text/html", "application/xhtml+xml")):
            raise ValueError("Document not available as XHTML/HTML in this request.")
        text = _VisibleText().plain_text(r.text)
        if not text or len(text) > MAX_DOCUMENT_CHARS:
            raise ValueError("Document text empty or exceeds safe length.")
        if "verify that you" in text.casefold() and "robot" in text.casefold():
            raise ValueError("Official document access requires browser verification.")
        return url, text
    raise ValueError("Excessive official document redirects.")


def probe_eurlex(
    celex: str, *, as_of: date | None = None,
    post: Callable | None = None, get: Callable | None = None
) -> tuple[CellarEvidence, str]:
    """Fetch official version candidates and actual text; NEVER certify law."""
    celex = _validate_celex(celex)
    as_of = as_of or date.today()
    when = datetime.now(timezone.utc).isoformat(timespec="seconds")
    versions: list[str] = []
    amendments: list[str] = []
    chosen, text, official_url, digest = None, "", None, None
    complete, downloaded, identity = False, False, False
    outcome = "unavailable"
    warnings = [
        "The consolidated text is a documentation tool, not an authentic OJ act.",
        "Current legal effect, corrections and applicability have not been certified.",
    ]
    try:
        fetch_post = post or requests.post
        v, all_v = _sparql_rows(consolidation_query(celex), post=fetch_post)
        a, all_a = _sparql_rows(amendments_query(celex), post=fetch_post)
        versions = v
        amendments = a
        complete = all_v and all_a
        chosen, versions = select_consolidation(celex, versions, as_of)
        if not all(re.fullmatch(r"3\d{4}[LRD]\d{4}", item) for item in amendments):
            raise ValueError("Amendment response contains unexpected identifiers.")
        if chosen is None:
            outcome = "no_applicable_consolidation"
            warnings.append("No applicable dated consolidation was confirmed from this query.")
        else:
            official_url, text = _download_text(chosen, get=get or requests.get)
            downloaded = True
            digest = sha256(text.encode("utf-8")).hexdigest()
            identity = chosen in text or chosen[:11] in text
            outcome = "source_text_retrieved" if identity else "source_identity_unconfirmed"
            if not identity:
                warnings.append("Visible text did not independently confirm CELEX identity.")
        if not complete:
            warnings.append("Metadata hit the query row cap; latest version may be missing.")
    except (ValueError, requests.RequestException, KeyError, TypeError) as exc:
        warnings.append("Official source retrieval failed: " + str(exc)[:190])
        outcome = "source_unavailable"
    except Exception as exc:
        warnings.append("Metadata could not be interpreted: " + type(exc).__name__)
        outcome = "source_unavailable"

    return CellarEvidence(
        base_celex=celex, as_of=as_of.isoformat(), checked_at_utc=when,
        official_base_url=EU_LEGAL_URL + celex,
        metadata_endpoint=SPARQL_URL, observed_consolidations=versions,
        selected_consolidation=chosen,
        observed_amendments=amendments,
        consolidated_document_url=official_url,
        text_sha256=digest, extracted_characters=len(text),
        document_identity_observed=identity, metadata_complete=complete,
        content_retrieved=downloaded,
        version_verified=False, legal_status_verified=False,
        outcome=outcome, warnings=warnings,
    ), text


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Retrieve Cellar legal-source evidence (not legal certification)."
    )
    parser.add_argument("celex", help="Base act CELEX, e.g. 32010L0035")
    parser.add_argument("--as-of", default=date.today().isoformat())
    args = parser.parse_args()
    result, _text = probe_eurlex(args.celex, as_of=date.fromisoformat(args.as_of))
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
