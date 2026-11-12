"""Official EUR-Lex/Cellar corrigendum retrieval and provision impact review.

Read only. Resolve a corrigendum's CELEX identifier to its unique Cellar
*work* through official CDM metadata, then request the English XHTML
expression using the work URI. Do not infer whether a correction affects
the relevant legal provision from mere existence of its CELEX identifier.

No result in this module certifies complete legal applicability.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime, timezone
from hashlib import sha256
import argparse
import json
import re
from typing import Callable
from urllib.parse import urljoin, urlsplit

import requests

from eurlex_cellar import _VisibleText, MAX_DOCUMENT_BYTES
from eurlex_verification import _rows, SPARQL_URL
from eurlex_oj_review import review_oj_amendment

CORRIGENDUM = re.compile(r"^3(\d{4})([LRD])(\d{4})R\((\d{2})\)$")
BASE_CELEX = re.compile(r"^3\d{4}[LRD]\d{4}$")
CELLAR_WORK = re.compile(
    r"^https?://publications\.europa\.eu/resource/cellar/"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$"
)
MAX_CORRIGENDA = 12
MAX_TEXT = 100_000
DATE = re.compile(r"\b([0-9]{1,2})\.([0-9]{1,2})\.([0-9]{4})\b")
TARGET = re.compile(
    r"\bconcerning\s+Article\s+([0-9]{1,3}[a-z]?)\s*"
    r"\(([0-9]{1,2})\)\s+of\s+Directive\s+(?:\(EU\)\s+)?"
    r"([0-9]{4})/([0-9]{1,4})/(EU|EC|EEC)\b",
    re.IGNORECASE,
)
CHANGE = re.compile(
    r"\bfor:\s*[‘“](.{1,1400}?)[’”]\s*,?\s*"
    r"read:\s*[‘“](.{1,1400}?)[’”]",
    flags=re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class CorrigendumEvidence:
    celex: str
    checked_at_utc: str
    requested_language: str
    queried_as_of: str
    official_celex_url: str
    official_work_url: str | None
    official_content_url: str | None
    official_text_sha256: str | None
    official_text_retrieved: bool
    heading_confirmed: bool
    language_confirmed: bool
    published_date: str | None
    target_base_celex: str | None
    target_article: str | None
    target_paragraph: str | None
    before_text: str | None
    after_text: str | None
    affects_requested_provision: bool | None
    corrected_text_matches_consolidation: bool | None
    # This is a correction-document evidence result, NOT a certification
    # that all the provisions of the act are in force or applicable.
    fully_legally_verified: bool
    outcome: str
    limitations: list[str]


@dataclass(frozen=True)
class CorrigendaReview:
    base_celex: str
    amendment_celex: str
    as_of: str
    requested_provision: str
    observed_corrigenda_count: int
    reviewed: list[CorrigendumEvidence]
    relevant_corrigenda: list[str]
    unrelated_corrigenda: list[str]
    unresolved_corrigenda: list[str]
    exact_correction_match_confirmed: bool
    all_corrigendum_texts_retrieved: bool
    full_legal_verification: bool
    outcome: str
    limitations: list[str]


def _validate_corrigendum(celex: str) -> tuple[str, str]:
    match = CORRIGENDUM.fullmatch(celex or "")
    if not match:
        raise ValueError("Expected an original EU act corrigendum CELEX R(01) identifier.")
    year, kind, number, _counter = match.groups()
    return celex, f"3{year}{kind}{number}"


def work_query(corrigendum_celex: str) -> str:
    celex, _amendment = _validate_corrigendum(corrigendum_celex)
    return (
        "PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>\n"
        "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n"
        "SELECT DISTINCT ?work WHERE {\n"
        f'  ?work cdm:resource_legal_id_celex "{celex}"^^xsd:string .\n'
        "} LIMIT 10"
    )


def _resolve_work(celex: str, *, post: Callable) -> str:
    bindings = _rows(work_query(celex), post=post, row_limit=10)
    works = set()
    for item in bindings:
        val = item.get("work", {}).get("value") if isinstance(item, dict) else None
        if not isinstance(val, str):
            raise ValueError("Invalid official Cellar work binding.")
        match = CELLAR_WORK.fullmatch(val)
        if match is None:
            raise ValueError("Unexpected Cellar work URI returned.")
        works.add("https://publications.europa.eu/resource/cellar/" + match.group(1))
    if len(works) != 1:
        raise ValueError("Corrigendum work identifier is missing or ambiguous.")
    return works.pop()


def _allowed_stream(url: str, work_url: str) -> bool:
    p = urlsplit(url)
    base = urlsplit(work_url)
    if (p.scheme != "https" or p.hostname != "publications.europa.eu"
            or p.username or p.password or p.port not in (None, 443)
            or p.fragment):
        return False
    # Restrict follow-up requests to manifestations of the selected work.
    if not (p.path == base.path or
            p.path.startswith(base.path + ".") and
            re.fullmatch(
                re.escape(base.path) + r"\.\d{4}\.\d{2}/DOC_\d+",
                p.path
            )):
        return False
    return p.query in ("", "language=en")


def _get_official_xhtml(work_url: str, *, get: Callable) -> tuple[str, str]:
    url = work_url + "?language=en"
    for _ in range(5):
        # Cellar advertises legacy HTTP redirect targets. Convert ONLY a
        # known Publications Office URL before issuing another request.
        if url.startswith("http://publications.europa.eu/resource/cellar/"):
            url = "https://" + url[len("http://"):]
        if not _allowed_stream(url, work_url):
            raise ValueError("Corrigendum resolver redirected outside its official work.")
        response = get(
            url, timeout=24, allow_redirects=False,
            headers={
                "Accept": "application/xhtml+xml",
                "Accept-Language": "eng",
                "User-Agent": "ALBA-Corrigenda/0.1 (read-only)",
            },
        )
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("Location")
            if not location:
                raise ValueError("Official Cellar content redirect missing.")
            url = urljoin(url, location)
            continue
        if response.status_code != 200:
            raise ValueError("Official Cellar document HTTP " + str(response.status_code))
        if len(response.content) > MAX_DOCUMENT_BYTES:
            raise ValueError("Corrigendum document larger than permitted size.")
        mime = response.headers.get("Content-Type", "").lower()
        if "application/xhtml+xml" not in mime and "text/html" not in mime:
            raise ValueError("Not an official HTML/XHTML manifestation.")
        text = _VisibleText().plain_text(response.text)
        if len(text) < 120 or len(text) > MAX_TEXT:
            raise ValueError("Corrigendum text unavailable or unexpectedly large.")
        if "verify that you" in text.lower() and "robot" in text.lower():
            raise ValueError("Source requires browser verification.")
        return url, text
    raise ValueError("Excessive redirects from official corrigendum work.")


def _heading_ok(text: str, celex: str) -> bool:
    _unused, amendment = _validate_corrigendum(celex)
    year, kind, number = amendment[1:5], amendment[5], int(amendment[6:])
    heading = text[:1300]
    expected = {"L": "Directive", "R": "Regulation", "D": "Decision"}[kind]
    return bool(
        re.search(r"Official Journal of the European Union\s+EN\b",
                  heading, re.IGNORECASE)
        and re.search(
            rf"\bCorrigendum\s+to\s+{expected}\s+\(EU\)\s+"
            rf"{year}/{number}\b", heading, re.IGNORECASE,
        )
    )


def _date_from_heading(text: str) -> str | None:
    # The OJ header gives publication date; for an unknown layout do not
    # manufacture a date from references later in the body.
    m = DATE.search(text[:130])
    if m is None:
        return None
    day, month, year = map(int, m.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _target(text: str) -> tuple[str | None, str | None, str | None]:
    m = TARGET.search(text[:4000])
    if not m:
        return None, None, None
    article, paragraph, year, number, kind = m.groups()
    prefix = {"EU": "L", "EC": "L", "EEC": "L"}[kind.upper()]
    return f"3{year}{prefix}{int(number):04d}", article.lower(), paragraph


def _normalized(text: str) -> str:
    # Treat typography/whitespace differences as formatting, not
    # differences in legal provisions.
    return re.sub(r"\s+", " ", re.sub(
        r"[‘’“”'\"\u00a0]", " ", text
    )).strip().casefold()


def _crosscheck(corrected: str, original: str, consolidated: str) -> bool | None:
    after, before, target = map(_normalized, (corrected, original, consolidated))
    if not target or not after:
        return None
    # Remove a leading paragraph number, whose formatting differs between
    # OJ amending act and the flattened consolidation.
    after = re.sub(r"^\d+\.\s*", "", after)
    before = re.sub(r"^\d+\.\s*", "", before)
    if len(after) < 35:
        return None
    return after in target and before not in target


def inspect_corrigendum(
    celex: str, *, base_celex: str, provision_article: str,
    provision_paragraph: str, consolidated_provision: str,
    as_of: date | None = None, post: Callable | None = None,
    get: Callable | None = None,
) -> CorrigendumEvidence:
    _celex, _amendment = _validate_corrigendum(celex)
    if not BASE_CELEX.fullmatch(base_celex):
        raise ValueError("Invalid base CELEX.")
    if not re.fullmatch(r"[0-9]{1,3}[a-z]?", provision_article, re.I):
        raise ValueError("Invalid article.")
    if not re.fullmatch(r"[1-9][0-9]?", provision_paragraph):
        raise ValueError("Invalid paragraph.")

    as_of = as_of or date.today()
    checked = datetime.now(timezone.utc).isoformat(timespec="seconds")
    official = ("https://eur-lex.europa.eu/legal-content/EN/ALL/"
                "?uri=CELEX%3A" + celex.replace("(", "%28").replace(")", "%29"))
    work = url = digest = published = None
    before = after = None
    target_base = target_article = target_para = None
    confirmed = lang_confirmed = read = False
    relevant = match = None
    outcome = "document_unavailable"
    limits = []
    try:
        work = _resolve_work(celex, post=post or requests.post)
        url, text = _get_official_xhtml(work, get=get or requests.get)
        read = True
        digest = sha256(text.encode("utf-8")).hexdigest()
        confirmed = _heading_ok(text, celex)
        lang_confirmed = bool(re.search(
            r"Official Journal of the European Union\s+EN\b",
            text[:500], re.IGNORECASE,
        ))
        published = _date_from_heading(text)
        target_base, target_article, target_para = _target(text)
        changes = CHANGE.search(text[:9000])
        if changes:
            before, after = (re.sub(r"\s+", " ", v).strip() for v in changes.groups())
        if published and date.fromisoformat(published) > as_of:
            limits.append("This correction was published after the requested legal date.")
            outcome = "not_published_at_requested_date"
        elif not confirmed or not lang_confirmed:
            limits.append("Corrigendum identity or EN language not confirmed from official text.")
            outcome = "document_identity_unconfirmed"
        elif target_base is None or target_article is None:
            limits.append("Affected directive and paragraph were not explicitly identifiable.")
            outcome = "target_unconfirmed"
        else:
            relevant = bool(
                target_base == base_celex
                and target_article == provision_article.casefold()
                and target_para == provision_paragraph
            )
            if not relevant:
                outcome = "other_provision_or_act"
            elif before is None or after is None:
                outcome = "correction_pair_unconfirmed"
                limits.append("For/read correction passage could not be extracted reliably.")
            else:
                match = _crosscheck(after, before, consolidated_provision)
                if match is True:
                    outcome = "corrected_text_consistent_with_consolidation"
                elif match is False:
                    outcome = "corrected_text_not_matched"
                    limits.append("The corrected text was not matched against the selected consolidation.")
                else:
                    outcome = "consolidated_provision_unavailable"
    except (ValueError, requests.RequestException, TypeError, KeyError) as exc:
        limits.append("Official source could not be retrieved or interpreted: " + str(exc)[:150])
    limits.append(
        "Full legal applicability still requires effective-date, language, "
        "activation and other corrigendum checks."
    )
    return CorrigendumEvidence(
        celex=celex, checked_at_utc=checked,
        requested_language="EN", queried_as_of=as_of.isoformat(),
        official_celex_url=official, official_work_url=work,
        official_content_url=url, official_text_sha256=digest,
        official_text_retrieved=read, heading_confirmed=confirmed,
        language_confirmed=lang_confirmed, published_date=published,
        target_base_celex=target_base, target_article=target_article,
        target_paragraph=target_para, before_text=before, after_text=after,
        affects_requested_provision=relevant,
        corrected_text_matches_consolidation=match,
        fully_legally_verified=False, outcome=outcome, limitations=limits,
    )


def review_amendment_corrigenda(
    base_celex: str, amendment_celex: str, *, as_of: date | None = None,
    article: str, paragraph: str,
    post: Callable | None = None, get: Callable | None = None,
) -> CorrigendaReview:
    """One source-backed result per corrigendum, with no implicit certification."""
    day = as_of or date.today()
    oj = review_oj_amendment(
        base_celex, amendment_celex, as_of=day,
        provision_article=article, provision_paragraph=paragraph,
        post=post, get=get,
    )
    items = []
    unresolved = []
    relevant = []
    unrelated = []
    corrigenda = oj.observed_corrigenda_celex
    if len(corrigenda) > MAX_CORRIGENDA:
        raise ValueError("Too many corrections for a bounded automatic review.")
    for celex in corrigenda:
        e = inspect_corrigendum(
            celex, base_celex=base_celex,
            provision_article=article, provision_paragraph=paragraph,
            consolidated_provision=oj.provision_text or "",
            as_of=day, post=post, get=get,
        )
        items.append(e)
        if e.affects_requested_provision is True:
            relevant.append(celex)
        elif e.affects_requested_provision is False:
            unrelated.append(celex)
        if (e.affects_requested_provision is None or
                e.affects_requested_provision is True and
                e.corrected_text_matches_consolidation is not True):
            unresolved.append(celex)
    complete = bool(oj.corrigendum_discovery_checked and
                    len(corrigenda) == len(items) and
                    all(e.official_text_retrieved and e.heading_confirmed
                        and e.language_confirmed for e in items))
    match = bool(relevant) and all(
        item.corrected_text_matches_consolidation is True
        for item in items if item.affects_requested_provision is True
    )
    if not oj.corrigendum_discovery_checked:
        outcome = "corrigendum_discovery_unconfirmed"
    elif not complete or unresolved:
        outcome = "corrigendum_review_incomplete"
    else:
        outcome = "corrigenda_inspected"
    return CorrigendaReview(
        base_celex=base_celex, amendment_celex=amendment_celex,
        as_of=day.isoformat(), requested_provision=f"{article}({paragraph})",
        observed_corrigenda_count=len(corrigenda), reviewed=items,
        relevant_corrigenda=relevant, unrelated_corrigenda=unrelated,
        unresolved_corrigenda=unresolved,
        exact_correction_match_confirmed=match,
        all_corrigendum_texts_retrieved=complete,
        full_legal_verification=False, outcome=outcome,
        limitations=oj.unresolved + [
            "Even a textually consistent corrigendum does not by itself "
            "certify the relevant legal provision's applicability."
        ],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read official Cellar corrigendum texts and compare provisions.")
    parser.add_argument("base_celex")
    parser.add_argument("amendment_celex")
    parser.add_argument("--article", required=True)
    parser.add_argument("--paragraph", required=True)
    parser.add_argument("--as-of", default=date.today().isoformat())
    args = parser.parse_args()
    report = review_amendment_corrigenda(
        args.base_celex, args.amendment_celex,
        article=args.article, paragraph=args.paragraph,
        as_of=date.fromisoformat(args.as_of),
    )
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
