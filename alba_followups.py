"""Deterministic Albanian/EU-law follow-up suggestions for saved chat answers.

No network calls, false citation promises or synthetic source counts.
Only the latest explicit question is used; uploaded document text is excluded.
"""
from __future__ import annotations

import re


_DIRECTIVE = re.compile(
    r"(?i)\b(?:directive|direktiv(?:a|e|ën|ës)?|dir\.?)[^\n]{0,35}?"
    r"((?:EU|EC|BE)?\s*\(?\s*\d{4}\s*/\s*\d{2,4}\s*\)?)\b"
)
_CELEX_DIR = re.compile(r"\b(?:3|0)\d{4}L\d{4}\b", re.I)
_TOPIC_CHAPTER = re.compile(
    r"(?i)\b(?:chapter|kapitull(?:i|in)?|ch\.)\s*(\d{1,2})\b"
)
_ALBANIAN = re.compile(
    r"(?i)(?:[ëç]|\b(?:si|mund|të|për|ligjin|shqipëri|shqiptar|"
    r"bëj|hartoj|dua|aktin|vkm|udhëzim|pyetje|krahaso|më)\b)"
)


def _subject(query: str) -> str:
    match = _DIRECTIVE.search(query)
    if match:
        number = re.sub(r"\s+", "", match.group(1)).strip("()")
        return "Direktivën " + number
    match = _TOPIC_CHAPTER.search(query)
    if match:
        return "Kapitullin " + match.group(1)
    return "aktin përkatës"


def follow_up_questions(question: str, answer: str = "") -> list[str]:
    """Return three immediately actionable prompts related to Albania.

    The answer is not trusted as evidence and is never used to fabricate legal
    status; this allows safe suggestions even when a model reply was inaccurate.
    """
    if not isinstance(question, str) or not question.strip():
        return []
    clean = question.split("\n\n[PUBLIC DOCUMENT EXCERPT:", 1)[0].strip()[:400]
    q = clean.casefold()
    shqip = bool(_ALBANIAN.search(clean))
    subj = _subject(clean)
    chapter = _TOPIC_CHAPTER.search(clean)
    directive = bool(_DIRECTIVE.search(clean) or _CELEX_DIR.search(clean))
    transposition = bool(re.search(
        r"p[eë]rafr|transpoz|implement|concordance|p[eë]rputhshm",
        q,
    ))
    reporting = bool(re.search(
        r"administrative capacit|information note|kapacitet|report|"
        r"raport|negociat|commission|komision|closing benchmark|"
        r"kriter.p[eë]rmbyll", q,
    ))
    drafting = bool(re.search(
        r"draft|hart|ligj|vkm|udh[eë]zim|rregullore|memo|memorandum|"
        r"document|dokument|docx|word|letter|shkres", q,
    ))

    if directive or transposition:
        if shqip:
            return [
                f"Cilat janë detyrimet kryesore të {subj} për përafrimin në Shqipëri?",
                f"Si të strukturohet tabela e përputhshmërisë për {subj}?",
                f"Çfarë informacioni institucional duhet të mbledhim në Shqipëri për zbatimin e {subj}?",
            ]
        return [
            f"What obligations under {subj.replace('Direktivën', 'Directive')} matter for Albania's approximation?",
            f"How should an Albanian table of concordance be structured for {subj.replace('Direktivën', 'Directive')}?",
            f"What institutional evidence should Albania collect to demonstrate implementation?",
        ]
    if reporting or chapter:
        title = ("Kapitullin " + chapter.group(1)) if chapter else "këtë temë"
        if shqip:
            return [
                f"Cila është struktura e Information Note për {title}?",
                "Cilat institucione shqiptare duhet të japin të dhëna dhe FTE?",
                "Përgatit pyetjet për institucionet, vetëm për kapacitetet administrative.",
            ]
        return [
            "What structure should Albania use for the European Commission information note?",
            "Which Albanian institutions should report staffing (FTE) and implementation evidence?",
            "Draft targeted administrative-capacity questions for the responsible institutions.",
        ]
    if drafting:
        if shqip:
            return [
                "Harto një memorandum juridik për zbatimin në Shqipëri.",
                "Përgatit strukturën e një projekt-VKM-je sipas teknikës legjislative shqiptare.",
                "Krijo një listë kontrolli për referencat në QBZ dhe përputhjen me acquis.",
            ]
        return [
            "Draft a legal memorandum on the implications for Albania.",
            "Prepare the structure of an Albanian draft Council of Ministers decision (VKM).",
            "What official QBZ and EUR-Lex sources should be checked before finalising the document?",
        ]
    if shqip:
        return [
            "Si zbatohet kjo çështje në kuadrin ligjor shqiptar?",
            "Cilat dispozita duhen kontrolluar në QBZ dhe EUR-Lex?",
            "Përgatit një përmbledhje juridike me çështjet për verifikim.",
        ]
    return [
        "How does this issue relate to Albanian legislation?",
        "Which official QBZ and EUR-Lex texts should be checked?",
        "Prepare a short legal briefing for an Albanian institution.",
    ]
