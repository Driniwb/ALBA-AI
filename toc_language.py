"""Conservative local language recognition for a ToC directive.

No external service or hidden upload. This module only determines whether
ALBA should translate an English-language source or preserve Albanian text.
Ambiguous, mixed or unsupported languages must NEVER be silently treated as
verified Albanian or automatically sent for translation.
"""
from __future__ import annotations

from collections import Counter
import re

from toc_builder import Provision

EN_WORDS = {
    "the", "and", "of", "shall", "must", "may", "means", "this",
    "that", "directive", "article", "member", "states", "transport",
    "competent", "authority", "provisions", "requirements", "within",
    "according", "referred", "provided", "apply", "ensure", "scope",
    "notwithstanding", "subject", "including", "where", "which", "are",
    "between", "under", "with", "for",
}
SQ_WORDS = {
    "dhe", "për", "të", "në", "është", "janë", "sipas", "nëse",
    "duhet", "mund", "neni", "nenit", "pikës", "këtij", "kësaj",
    "përcaktuar", "dispozitat", "shtetet", "anëtare", "autoriteti",
    "ligjit", "ligj", "zbatohet", "zbatohen", "kompetent",
    "transportit", "transportin", "pajisjeve", "kërkesat",
    "mjetet", "shkronjës", "parashikuar", "rastet", "fusha",
}
EN_HEADING = re.compile(r"(?im)^\s*article\s+\d+[a-z]?\b")
SQ_HEADING = re.compile(r"(?im)^\s*neni\s+\d+[a-z]?\b")
WORD = re.compile(r"[a-zA-ZëËçÇ]+")


def detect_toc_language(units: list[Provision]) -> str:
    """Return 'en', 'sq' or 'uncertain'; never guess on marginal evidence."""
    if not units:
        return "uncertain"
    text = "\n".join(unit.text for unit in units)
    words = [word.casefold() for word in WORD.findall(text)]
    counts = Counter(words)
    en = sum(counts[w] for w in EN_WORDS)
    sq = sum(counts[w] for w in SQ_WORDS)
    en_heads = len(EN_HEADING.findall(text))
    sq_heads = len(SQ_HEADING.findall(text))
    if en_heads and sq_heads:
        return "uncertain"
    # Heading evidence helps, but content must agree: mixed translations are
    # not a safe basis for deciding whether to call the AI translation model.
    en += en_heads * 3
    sq += sq_heads * 3
    if en >= 4 and en >= sq * 2:
        return "en"
    if sq >= 4 and sq >= en * 2:
        return "sq"
    return "uncertain"
