"""ALBA v2 — Official Journal amending-act and corrigendum review.

Reads the authentic OJ *amending act* from the official Cellar resolver,
extracts narrowly anchored operative dates, discovers corrigenda from Cellar
CDM relations, and checks the selected consolidation's provision text.

Never confuse:
* EU act entry into force with its Member State transposition deadline;
* the application of national measures with each EU provision's applicability;
* availability of a correction CELEX with its authentic text/affected language;
* a documentary consolidation with authentic Official Journal legislation.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import re
from typing import Callable

import requests

from eurlex_cellar import _download_text, probe_eurlex
from eurlex_verification import (
    _rows, _interpret_status, _interpret_relations,
    relationships_query, status_query, MAX_RELATION_ROWS, MAX_STATUS_ROWS,
)

ACT = re.compile(r"^3(\d{4})([LRD])(\d{4})$")
MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}
DATE_WORDS = r"(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(\d{4})"


@dataclass(frozen=True)
class OfficialJournalReview:
    base_celex: str
    amendment_celex: str
    as_of: str
    checked_at_utc: str
    oj_act_url: str
    oj_content_url: str | None
    oj_text_sha256: str | None
    oj_characters: int
    oj_heading_identified: bool
    base_mentioned_in_amending_text: bool
    amending_act_in_force_flag: bool | None
    amending_act_entry_into_force: str | None
    national_transposition_deadline: str | None
    national_measures_application_date: str | None
    observed_corrigenda_celex: list[str]
    corrigendum_discovery_checked: bool
    corrigendum_texts_verified: bool
    selected_consolidation: str | None
    consolidation_heading_confirmed: bool
    amended_provision: str | None
    provision_text: str | None
    conditional_application_identified: bool
    complete_legal_verification: bool
    outcome: str
    unresolved: list[str]


def _celex(c: str) -> tuple[str, str, str]:
    match = ACT.fullmatch(c or "")
    if not match:
        raise ValueError("Only original EU legal act CELEX identifiers are accepted.")
    return match.groups()


def _oj_identity(text: str, amendment: str) -> bool:
    year, kind, number = _celex(amendment)
    patterns = {
        "L": "DIRECTIVE", "R": "REGULATION", "D": "DECISION",
    }
    heading = re.sub(r"\s+", " ", text[:1250])
    return (
        "Official Journal of the European Union" in heading
        and bool(re.search(
            rf"\b{patterns[kind]}\b.{{0,40}}\b{year}/0*{int(number)}\b",
            heading, flags=re.IGNORECASE,
        ))
    )


def _mentions_amended_base(text: str, base_celex: str) -> bool:
    year, kind, number = _celex(base_celex)
    label = {"L": "Directive", "R": "Regulation", "D": "Decision"}[kind]
    # An operative amendment clause is evidence; a title/preamble mention is
    # insufficient to locate which provision has changed.
    target = rf"{label}\s+(?:\(EU\)\s+)?{year}/0*{int(number)}/(?:EU|EC|EEC)"
    # The OJ commonly uses "Directive XXXX is amended as follows", not
    # "In Directive XXXX". Require a verb showing an operative change.
    return bool(re.search(
        rf"\b{target}\s+is\s+amended\s+as\s+follows",
        text, flags=re.IGNORECASE,
    ) or re.search(
        rf"\bIn\s+{target}\s*[,;:]?\s+the\s+following\s+amendments",
        text, flags=re.IGNORECASE,
    ))


def _date_words(raw: str) -> str | None:
    match = re.fullmatch(DATE_WORDS, raw.strip(), flags=re.IGNORECASE)
    if not match:
        return None
    day, month, year = match.groups()
    try:
        return date(int(year), MONTHS[month.lower()], int(day)).isoformat()
    except ValueError:
        return None


def _transposition_dates(text: str) -> tuple[str | None, str | None]:
    # Only operative transposition section, not incidental mentions.
    match = re.search(
        r"\bArticle\s+11\s+Transposition\b(.{0,2600}?)"
        r"\bArticle\s+12\s+Entry into force\b",
        text, flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None, None
    scope = match.group(1)
    deadline = re.search(
        rf"\bBy\s+{DATE_WORDS}\s+Member States shall adopt",
        scope, flags=re.IGNORECASE,
    )
    applied = re.search(
        rf"\bapply those measures from\s+{DATE_WORDS}",
        scope, flags=re.IGNORECASE,
    )
    def date_from(m: re.Match | None) -> str | None:
        return _date_words(" ".join(m.groups())) if m else None
    return date_from(deadline), date_from(applied)


def _article_text(text: str, article: str, paragraph: str | None = None) -> str | None:
    # Only a numbered provision anchor, never a general semantic assertion.
    if not re.fullmatch(r"\d{1,3}[a-z]?", article, re.I):
        raise ValueError("Invalid article identifier.")
    start = re.search(
        rf"\bArticle\s+{re.escape(article)}\s+(?=[A-Z])", text, flags=re.IGNORECASE,
    )
    if start is None:
        return None
    following = re.search(
        r"\bArticle\s+\d{1,3}[a-z]?\s+(?=[A-Z])", text[start.end():],
        flags=re.IGNORECASE,
    )
    end = start.end() + following.start() if following else min(len(text), start.end()+15000)
    article_text = text[start.start():end]
    if paragraph is None:
        return article_text[:2500]
    if not re.fullmatch(r"[1-9]\d?", paragraph):
        raise ValueError("Invalid paragraph identifier.")
    boundaries = list(re.finditer(r"\b([1-9]\d?)\.\s+", article_text))
    for i, boundary in enumerate(boundaries):
        if boundary.group(1) != paragraph:
            continue
        finish = boundaries[i+1].start() if i+1 < len(boundaries) else len(article_text)
        return article_text[boundary.end():finish][:1200].strip()
    return None


def review_oj_amendment(
    base_celex: str, amendment_celex: str, *,
    as_of: date | None = None,
    provision_article: str | None = None,
    provision_paragraph: str | None = None,
    post: Callable | None = None,
    get: Callable | None = None,
) -> OfficialJournalReview:
    _celex(base_celex)
    _celex(amendment_celex)
    as_of = as_of or date.today()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    reasons: list[str] = []
    url, source, digest = None, "", None
    identity = False
    base_mentioned = False
    in_force, start_date = None, None
    deadline, application = None, None
    corregenda: list[str] = []
    corr_checked = False
    selected, consolidated_heading, provision, conditional = None, False, None, False
    try:
        url, source = _download_text(amendment_celex, get=get or requests.get)
        digest = sha256(source.encode("utf-8")).hexdigest()
        identity = _oj_identity(source, amendment_celex)
        base_mentioned = _mentions_amended_base(source, base_celex)
        deadline, application = _transposition_dates(source)
        if not identity:
            reasons.append("The Official Journal heading did not confirm the amending act.")
        if not base_mentioned:
            reasons.append("Operative amending clause for the requested base act was not confirmed.")

        fetch = post or requests.post
        rows = _rows(status_query(amendment_celex), post=fetch, row_limit=MAX_STATUS_ROWS)
        in_force, start_date, _end = _interpret_status(rows)
        if in_force is None or not start_date:
            reasons.append("Complete entry-into-force metadata for the amendment was not found.")
        if as_of != date.today():
            reasons.append("The present-day in-force flag cannot certify a historical status.")
        if as_of != date.today():
            reasons.append("Cellar's present-day in-force flag does not certify historical legal status.")
        if start_date and date.fromisoformat(start_date) > as_of:
            reasons.append("The amending act entered into force after the requested date.")
        if application and date.fromisoformat(application) > as_of:
            reasons.append("The published date for application of national measures is in the future.")

        relation_rows = _rows(
            relationships_query(amendment_celex), post=fetch,
            row_limit=MAX_RELATION_ROWS,
        )
        _repealing, corregenda = _interpret_relations(relation_rows)
        corr_checked = True
        if corregenda:
            reasons.append(
                "Corrigenda are registered but their authoritative texts and "
                "affected language versions require separate examination."
            )
        else:
            reasons.append(
                "No corrigenda returned by this relation query; this does "
                "not establish absence of corrections."
            )

        consolidation, consolidated_text = probe_eurlex(
            base_celex, as_of=as_of, post=fetch, get=get or requests.get,
        )
        selected = consolidation.selected_consolidation
        consolidated_heading = bool(
            consolidation.content_retrieved
            and consolidation.document_identity_observed
        )
        if provision_article:
            if consolidated_heading:
                provision = _article_text(
                    consolidated_text, provision_article, provision_paragraph,
                )
            if provision is None:
                reasons.append("Requested article/paragraph could not be anchored in the consolidated text.")
            # For 2010/35/EU, Article 33a makes Articles 33b–33d subject
            # to emergency activation and crisis-relevant designation.
            if base_celex == "32010L0035" and provision_article.lower() in {"33b", "33c", "33d"}:
                context = _article_text(consolidated_text, "33a") if consolidated_heading else None
                conditional = bool(
                    context and "only if the Commission has adopted" in context
                    and "only during the internal market emergency mode" in context
                )
                if conditional:
                    reasons.append("The selected provision is subject to emergency-mode conditions in Article 33a.")
                else:
                    reasons.append("Emergency-mode applicability conditions could not be confirmed.")
        if not consolidated_heading:
            reasons.append("The applicable consolidated text could not be identified.")
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        reasons.append("Official Journal evidence could not be fully retrieved: "
                       + str(exc)[:180])
    except Exception as exc:
        reasons.append("Official metadata could not be processed: "
                       + type(exc).__name__)

    if not source or not identity:
        outcome = "oj_source_unconfirmed"
    elif not base_mentioned:
        outcome = "operative_amendment_unconfirmed"
    elif not corr_checked:
        outcome = "change_history_unconfirmed"
    elif not consolidated_heading:
        outcome = "consolidated_text_unconfirmed"
    elif provision_article and provision is None:
        outcome = "provision_unconfirmed"
    else:
        outcome = "oj_and_change_metadata_checked"

    reasons.append(
        "Full legal certification withheld until every applicable corrigendum "
        "and provision-specific effective condition is checked against authentic OJ text."
    )

    return OfficialJournalReview(
        base_celex=base_celex, amendment_celex=amendment_celex,
        as_of=as_of.isoformat(), checked_at_utc=now,
        oj_act_url=(
            "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A"
            + amendment_celex
        ),
        oj_content_url=url, oj_text_sha256=digest,
        oj_characters=len(source), oj_heading_identified=identity,
        base_mentioned_in_amending_text=base_mentioned,
        amending_act_in_force_flag=in_force,
        amending_act_entry_into_force=start_date,
        national_transposition_deadline=deadline,
        national_measures_application_date=application,
        observed_corrigenda_celex=corregenda,
        corrigendum_discovery_checked=corr_checked,
        corrigendum_texts_verified=False,
        selected_consolidation=selected,
        consolidation_heading_confirmed=consolidated_heading,
        amended_provision=(
            f"{provision_article}({provision_paragraph})"
            if provision_article and provision_paragraph
            else provision_article
        ),
        provision_text=provision,
        conditional_application_identified=conditional,
        complete_legal_verification=False,
        outcome=outcome, unresolved=reasons,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Review OJ amendments and corrigenda.")
    parser.add_argument("base_celex")
    parser.add_argument("amendment_celex")
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--article", default=None)
    parser.add_argument("--paragraph", default=None)
    args = parser.parse_args()
    report = review_oj_amendment(
        args.base_celex, args.amendment_celex,
        as_of=date.fromisoformat(args.as_of),
        provision_article=args.article, provision_paragraph=args.paragraph,
    )
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
