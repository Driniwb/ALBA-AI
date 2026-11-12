"""ALBA v2 — official EU legislation verification gate (read-only).

Separate verified source retrieval, Cellar legal metadata, and *unresolved*
legal-effect analysis. A consolidated document is NOT legally authentic, and
this gate never certifies every article as applicable without provision review.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
from datetime import date, datetime, timezone
import json
import re
from typing import Callable

import requests

from eurlex_cellar import (
    SPARQL_URL, MAX_SPARQL_BYTES, _validate_celex, probe_eurlex,
)

CDM = "http://publications.europa.eu/ontology/cdm#"
STATUS_FIELDS = {
    "resource_legal_in-force": "in_force",
    "resource_legal_date_entry-into-force": "entry_into_force",
    "resource_legal_date_end-of-validity": "end_of_validity",
}
RELEVANT_RELATIONS = {
    "resource_legal_repeals_resource_legal": "repeals",
    "resource_legal_implicitly_repeals_resource_legal": "implicitly_repeals",
    "resource_legal_corrects_resource_legal": "corrects",
}
MAX_STATUS_ROWS = 50
MAX_RELATION_ROWS = 100


@dataclass(frozen=True)
class LegalVerificationReport:
    base_celex: str
    as_of: str
    checked_at_utc: str
    consolidated_celex: str | None
    original_act_url: str
    consolidated_text_url: str | None
    cellar_source_url: str | None
    official_metadata_url: str
    in_force_flag: bool | None
    entry_into_force: str | None
    end_of_validity: str | None
    observed_amendments: list[str]
    observed_repealing_acts: list[str]
    observed_corrigenda: list[str]
    observed_corrigendum_citations: list[str]
    observed_consolidation_markers: list[str]
    missing_amendments_in_text: list[str]
    text_retrieved: bool
    text_identity_confirmed: bool
    metadata_status_checked: bool
    metadata_status_consistent: bool
    amendment_list_crosschecked: bool
    full_legal_verification: bool
    outcome: str
    reasons: list[str]


def status_query(celex: str) -> str:
    c = _validate_celex(celex)
    names = ", ".join("cdm:" + name for name in STATUS_FIELDS)
    return (
        "PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>\n"
        "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n"
        "SELECT DISTINCT ?predicate ?value WHERE {\n"
        f'  ?act cdm:resource_legal_id_celex "{c}"^^xsd:string ; ?predicate ?value .\n'
        f"  FILTER (?predicate IN ({names}))\n"
        "} LIMIT 50"
    )


def relationships_query(celex: str) -> str:
    c = _validate_celex(celex)
    rels = ", ".join("cdm:" + name for name in RELEVANT_RELATIONS)
    return (
        "PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>\n"
        "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n"
        "SELECT DISTINCT ?predicate ?celex WHERE {\n"
        f'  ?base cdm:resource_legal_id_celex "{c}"^^xsd:string .\n'
        "  ?other ?predicate ?base ; cdm:resource_legal_id_celex ?celex .\n"
        f"  FILTER (?predicate IN ({rels}))\n"
        "} LIMIT 100"
    )


def _rows(query: str, *, post: Callable, row_limit: int) -> list[dict]:
    response = post(
        SPARQL_URL,
        data={"query": query},
        headers={
            "Accept": "application/sparql-results+json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "ALBA-LegalVerification/0.1 (read-only)",
        },
        allow_redirects=False, timeout=28,
    )
    if response.status_code != 200:
        raise ValueError("Cellar SPARQL HTTP " + str(response.status_code))
    if len(response.content) > MAX_SPARQL_BYTES:
        raise ValueError("Metadata response too large.")
    if "json" not in response.headers.get("Content-Type", "").lower():
        raise ValueError("Cellar SPARQL metadata was not JSON.")
    try:
        bindings = response.json()["results"]["bindings"]
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError("Invalid Cellar SPARQL JSON structure.") from exc
    if not isinstance(bindings, list) or len(bindings) >= row_limit:
        raise ValueError("Incomplete or oversized Cellar metadata result.")
    return bindings


def _binding(item: dict, key: str) -> str:
    obj = item.get(key)
    if not isinstance(obj, dict) or not isinstance(obj.get("value"), str):
        raise ValueError("Malformed Cellar metadata binding: " + key)
    return obj["value"]


def _interpret_status(rows: list[dict]) -> tuple[bool | None, str | None, str | None]:
    parsed: dict[str, set[str]] = {}
    for item in rows:
        key = _binding(item, "predicate").removeprefix(CDM)
        if key not in STATUS_FIELDS:
            raise ValueError("Unexpected status predicate.")
        parsed.setdefault(STATUS_FIELDS[key], set()).add(_binding(item, "value"))
    for key in parsed:
        if len(parsed[key]) > 1:
            raise ValueError("Contradictory Cellar status metadata: " + key)
    in_force_value = next(iter(parsed["in_force"])) if "in_force" in parsed else None
    if in_force_value not in (None, "true", "false", "1", "0"):
        raise ValueError("Unexpected Cellar in-force flag.")
    flag = None if in_force_value is None else in_force_value in ("true", "1")
    def _date(key: str) -> str | None:
        if key not in parsed:
            return None
        raw = next(iter(parsed[key]))
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:T.*)?", raw):
            raise ValueError("Invalid legal date field.")
        try:
            value = date.fromisoformat(raw[:10])
        except ValueError as exc:
            raise ValueError("Invalid legal calendar date.") from exc
        return value.isoformat()
    return flag, _date("entry_into_force"), _date("end_of_validity")


def _interpret_relations(rows: list[dict]) -> tuple[list[str], list[str]]:
    repealing: set[str] = set()
    corrections: set[str] = set()
    for item in rows:
        prop = _binding(item, "predicate").removeprefix(CDM)
        if prop not in RELEVANT_RELATIONS:
            raise ValueError("Unexpected change relation.")
        celex = _binding(item, "celex")
        # Corrigenda may have a valid suffix R(01), not accepted by base regex.
        if not re.fullmatch(r"3\d{4}[LRD]\d{4}(?:R\(\d+\))?", celex):
            raise ValueError("Unexpected change document CELEX.")
        if prop == "resource_legal_corrects_resource_legal":
            corrections.add(celex)
        else:
            repealing.add(celex)
    return sorted(repealing), sorted(corrections)


def _textual_amendment_present(text: str, celex: str) -> bool:
    """Check header citation only; don't mistake arbitrary body mentions."""
    # Example 32024L2749 -> DIRECTIVE (EU) 2024/2749 in the header.
    year, number = celex[1:5], str(int(celex[6:]))
    search_region = text[:5000]
    return bool(re.search(
        rf"\b{re.escape(year)}\s*/\s*0*{re.escape(number)}\b",
        search_region, flags=re.IGNORECASE,
    ))


def _consolidation_markers(text: str) -> list[str]:
    region = text[:7000]
    found = []
    for marker in ("Amended by:", "Corrected by:", "Corrigendum", "►M1", "►C1"):
        if marker.casefold() in region.casefold():
            found.append(marker)
    return found


def _corrigendum_citations(text: str) -> list[str]:
    """Extract human-readable corrigendum OJ citations from the official header.

    An OJ citation isn't necessarily a CELEX and doesn't, on its own,
    establish whether the corrigendum affects the requested language.
    """
    region = text[:7000]
    section = re.search(
        r"Corrected by:\s*(.+?)(?:▼B|CHAPTER\s+1|Article\s+1|$)",
        region, flags=re.IGNORECASE | re.DOTALL,
    )
    if not section:
        return []
    pairs = re.findall(
        r"\bCorrigendum\s*,?\s*OJ\s+L\s+(\d+)\s*,\s*"
        r"(\d{1,2}\.\d{1,2}\.\d{4})",
        section.group(1), flags=re.IGNORECASE,
    )
    return list(dict.fromkeys("OJ L " + number + ", " + when for number, when in pairs))


def verify_eurlex(
    celex: str, *, as_of: date | None = None,
    post: Callable | None = None, get: Callable | None = None,
) -> LegalVerificationReport:
    celex = _validate_celex(celex)
    day = as_of or date.today()
    current_day = date.today()
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    reasons: list[str] = []
    status = None
    entry = None
    end = None
    repeals: list[str] = []
    corrections: list[str] = []
    text = ""
    evidence = None
    metadata_checked = False
    metadata_consistent = False
    crosschecked = False
    missing: list[str] = []
    markers: list[str] = []
    corrigendum_citations: list[str] = []
    error = False

    try:
        evidence, text = probe_eurlex(celex, as_of=day, post=post, get=get)
        if not (evidence.content_retrieved and evidence.document_identity_observed
                and evidence.metadata_complete):
            reasons.append("A complete, identified consolidated text could not be confirmed.")
        else:
            markers = _consolidation_markers(text)
            corrigendum_citations = _corrigendum_citations(text)
            missing = [
                item for item in evidence.observed_amendments
                if not _textual_amendment_present(text, item)
            ]
            crosschecked = not missing and bool(markers or not evidence.observed_amendments)
            if missing:
                reasons.append("Amending acts absent from consolidated document header: "
                               + ", ".join(missing))
            if not crosschecked:
                reasons.append("Consolidated amendment markers could not be reconciled.")
        fetch = post or requests.post
        rows = _rows(status_query(celex), post=fetch, row_limit=MAX_STATUS_ROWS)
        status, entry, end = _interpret_status(rows)
        metadata_checked = True
        relation_rows = _rows(relationships_query(celex), post=fetch,
                              row_limit=MAX_RELATION_ROWS)
        repeals, corrections = _interpret_relations(relation_rows)
        if day != current_day:
            reasons.append(
                "The Cellar in-force flag describes present status, not historical status."
            )
        elif status is None:
            reasons.append("Cellar does not provide an unambiguous in-force flag.")
        elif status is False:
            reasons.append("Cellar reports that the base act is not in force.")
        elif entry is None:
            reasons.append("Entry-into-force date is not available in official metadata.")
        elif date.fromisoformat(entry) > day:
            reasons.append("Base act has not yet entered into force.")
        elif end and date.fromisoformat(end) <= day:
            reasons.append("Date of end of validity has been reached.")
        else:
            metadata_consistent = True
        if repeals:
            reasons.append("Official repeal relationship(s) require date and effect review: "
                           + ", ".join(repeals))
        if corrections or "Corrected by:" in markers or corrigendum_citations:
            reasons.append("Corrigenda require independent review, including language scope.")
    except (ValueError, requests.RequestException) as exc:
        reasons.append("Official Cellar verification metadata unavailable: "
                       + str(exc)[:180])
        error = True

    # A current-law verdict needs proof of effective dates per provision,
    # authentic OJ amendments/corrections and repeals, not just version text.
    verified = False
    if error:
        outcome = "verification_blocked"
    elif not evidence or not evidence.content_retrieved or not evidence.document_identity_observed:
        outcome = "verification_blocked"
    elif not metadata_consistent:
        outcome = "metadata_unconfirmed"
    elif missing:
        outcome = "amendment_mismatch"
    else:
        outcome = "source_and_status_metadata_checked"
    reasons.append(
        "Full legal verification is withheld: provision-level application dates, "
        "transitional rules, authoritative OJ acts and late changes need review."
    )
    return LegalVerificationReport(
        base_celex=celex, as_of=day.isoformat(), checked_at_utc=checked_at,
        consolidated_celex=evidence.selected_consolidation if evidence else None,
        original_act_url=(
            "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A" + celex
        ),
        consolidated_text_url=(
            "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A"
            + evidence.selected_consolidation
            if evidence and evidence.selected_consolidation else None
        ),
        cellar_source_url=evidence.consolidated_document_url if evidence else None,
        official_metadata_url=SPARQL_URL,
        in_force_flag=status, entry_into_force=entry, end_of_validity=end,
        observed_amendments=evidence.observed_amendments if evidence else [],
        observed_repealing_acts=repeals, observed_corrigenda=corrections,
        observed_corrigendum_citations=corrigendum_citations,
        observed_consolidation_markers=markers,
        missing_amendments_in_text=missing,
        text_retrieved=bool(evidence and evidence.content_retrieved),
        text_identity_confirmed=bool(evidence and evidence.document_identity_observed),
        metadata_status_checked=metadata_checked,
        metadata_status_consistent=metadata_consistent,
        amendment_list_crosschecked=crosschecked,
        full_legal_verification=verified,
        outcome=outcome, reasons=reasons,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Cellar metadata and consolidated-text verification (fail closed)."
    )
    parser.add_argument("celex", help="Base act CELEX, e.g. 32010L0035")
    parser.add_argument("--as-of", default=date.today().isoformat())
    args = parser.parse_args()
    report = verify_eurlex(args.celex, as_of=date.fromisoformat(args.as_of))
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
