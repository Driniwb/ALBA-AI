"""Lightweight chat-to-module handoff, with explicit user navigation.

The router looks for a *task request*, not a keyword alone. Informational
questions stay in the chat. No AI request, upload or navigation occurs until
the user explicitly clicks the recommended module.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import MutableMapping

# Keep the links aligned with the pages registered by app.py.
MODULES = {
    "legal": ("Legal Drafting", "pages/3_Legal_Drafting.py", "legal_source", 10500),
    "toc": ("ToC Builder", "pages/1_ToC_Builder.py", None, 0),
    "eu": ("EU Reporting", "pages/4_EU_Reporting.py", "eu_source", 8000),
    "communication": ("Communication Studio", "pages/2_Communication_Studio.py", "comm_source", 8000),
    "writing": ("Writing Assistant", "writing_assistant.py", "alba_writing_source", 4000),
}

@dataclass(frozen=True)
class Handoff:
    key: str
    label: str
    page: str
    source_key: str | None
    max_chars: int
    defaults: tuple[tuple[str, str], ...] = ()


def _has(pattern: str, value: str) -> bool:
    return bool(re.search(pattern, value, flags=re.IGNORECASE))


# Imperatives/instructions, not mere mentions of a topic.
_TASK = (
    r"\b(?:draft|drafting|prepare|create|write|revise|review|edit|amend|"
    r"translate|adapt|transpose|compile|generate|produce|redraft|"
    r"hart(?:o|im|oni|oj|uar)?|p[eë]rgatit|p[eë]rpil|rishik|korrigj|"
    r"p[eë]rshtat|p[eë]rkthe|transpoz|p[eë]raf(?:ro|rim|ruar)|"
    r"ndrysho|plot[eë]so|shkruaj|gjenero|b[eë]j(?:m[eë])?|"
    r"formulo|riformulo)\b"
)
_TOC = r"\b(?:toc|table of concordance|tabel[aeë](?:n)?\s+(?:e\s+)?p[eë]rputhshm[eë]ris[eë]|konkordanc[eë])\b"
_EU = (
    r"\b(?:information note|administrative capacit(?:y|ies)|"
    r"kapacitet(?:et)?\s+administrativ(?:e|ë)?|"
    r"negotiating position|pozicion(?:in)?\s+negociues|"
    r"closing benchmark|kriter(?:et)?\s+p[eë]rmbyll[eë]s|"
    r"eu (?:report|reporting)|raportim(?:in)?\s+(?:p[eë]r|n[eë])\s+be|"
    r"reply\s+to\s+(?:the\s+)?european commission|"
    r"p[eë]rgjigj(?:e|en)\s+(?:p[eë]r|ndaj)\s+komision(?:it)?\s+evropian|"
    r"acquis progress report|chapter\s*14|kapitull(?:i|in)?\s*14)\b"
)
_LEGAL = (
    r"\b(?:projekt\s*[- ]?\s*(?:vkm|ligj|udh[eë]zim|rregullore)|"
    r"draft\s+(?:law|regulation|legislation)|"
    r"vkm|vendim\s+(?:i\s+)?k[eë]shillit\s+t[eë]\s+ministrave|"
    r"amendment(?:s)?\s+to\s+(?:a\s+)?(?:law|act)|"
    r"ndryshim(?:e)?\s+(?:t[eë]|n[eë])\s+ligj|"
    r"p[eë]rafrim(?:in)?\s+(?:me\s+)?(?:direktiv|acquis)|"
    r"transpozim(?:in)?|legal drafting|hartim(?:i)?\s+ligjor)\b"
)
_COMM = (
    r"\b(?:press\s+(?:release|statement)|njoftim\s+p[eë]r\s+shtyp|"
    r"komunikat[eë]\s+(?:p[eë]r\s+)?shtyp|social\s+media|"
    r"rrjet(?:et)?\s+sociale|instagram|linkedin|facebook|"
    r"newsletter|website article|artikull\s+(?:p[eë]r\s+)?web|"
    r"postim(?:e|in)?|fushat[eë]\s+komunikimi)\b"
)
_WRITING = (
    r"\b(?:email|e-mail|procesverbal|meeting minutes|"
    r"grammar|spelling|drejtshkrim|terminologji|"
    r"gjuha\s+institucionale|shqipe\s+zyrtare|"
    r"proofread|copyedit|translation|p[eë]rkthim|"
    r"tekst\s+zyrtar|official letter)\b"
)


def suggest_handoff(query: str) -> Handoff | None:
    """Recommend at most one module, and never for a general explanation."""
    if not isinstance(query, str) or not query.strip():
        return None
    # Ignore appended document content: it is source, not a navigation command.
    query = query.split("\n\n[PUBLIC DOCUMENT EXCERPT:", 1)[0].strip()
    q = query.casefold()
    if not _has(_TASK, q):
        return None
    if _has(_TOC, q):
        key, defaults = "toc", ()
    elif _has(_EU, q):
        key = "eu"
        report = (
            "administrative_capacity" if _has(r"administrative capacit|kapacitet.{0,15}administrativ", q)
            else "negotiating_position" if _has(r"negotiating position|pozicion.{0,15}negociues", q)
            else "eu_letter" if _has(r"reply to|p[eë]rgjigj.{0,25}komision", q)
            else "progress_report" if _has(r"progress report|benchmark|kriter.{0,20}p[eë]rmbyll", q)
            else "information_note"
        )
        defaults = (("eu_document_type", report), (
            "eu_mode", "review" if _has(r"\b(?:review|rishik|korrigj|revise)\w*\b", q)
            else "create"
        ))
    elif _has(_LEGAL, q):
        key = "legal"
        act = (
            "vkm" if _has(r"\bvkm\b|k[eë]shillit t[eë] ministrave", q)
            else "instruction" if _has(r"\budh[eë]zim\b|ministerial instruction", q)
            else "regulation" if _has(r"\brregullore\b|technical regulation", q)
            else "law"
        )
        mode = (
            "transpose" if _has(r"transpoz|p[eë]rafr|approximate|eu acquis", q)
            else "amend" if _has(r"amend|ndryshim|riformulo", q)
            else "review" if _has(r"\b(?:review|rishik|korrigj)\w*\b", q)
            else "new"
        )
        defaults = (("legal_act_type", act), ("legal_mode", mode))
    elif _has(_COMM, q):
        key = "communication"
        fmt = (
            "instagram" if _has(r"instagram", q)
            else "linkedin" if _has(r"linkedin", q)
            else "facebook" if _has(r"facebook", q)
            else "x" if _has(r"\b(?:twitter|tweet)\b", q)
            else "newsletter" if _has(r"newsletter", q)
            else "web_article" if _has(r"website article|artikull.{0,12}web", q)
            else "press_statement" if _has(r"press statement", q)
            else "press_release"
        )
        group = (
            "Social Media" if fmt in {"instagram", "linkedin", "facebook", "x"}
            else "Newsletter & Web" if fmt in {"newsletter", "web_article"}
            else "Press & Media"
        )
        defaults = (("comm_group", group), ("comm_target_format", fmt),
                    ("comm_mode", "create"))
    elif _has(_WRITING, q):
        key = "writing"
        doc = (
            "Institutional email" if _has(r"email|e-mail", q)
            else "Meeting minutes" if _has(r"procesverbal|meeting minutes", q)
            else "Official letter" if _has(r"official letter|shkres[eë]", q)
            else "Report / information note"
        )
        task = (
            "Draft a document from notes" if _has(r"draft|hart|write|shkruaj|prepare|p[eë]rgatit|create", q)
            else "Adapt English into formal Albanian" if _has(r"translate|p[eë]rkth", q)
            else "Check legal and administrative terminology" if _has(r"terminolog|term", q)
            else "Improve Albanian institutional language"
        )
        defaults = (("alba_writing_document_format", doc),
                    ("alba_writing_action", task))
    else:
        return None
    title, page, field, limit = MODULES[key]
    return Handoff(key, title, page, field, limit, tuple(defaults))


def prepare_handoff(handoff: Handoff, message: str, state: MutableMapping) -> None:
    """Prepopulate only the requested destination. No model call is made."""
    if handoff.key not in MODULES or MODULES[handoff.key][1] != handoff.page:
        raise ValueError("Unknown ALBA destination.")
    if not isinstance(message, str):
        raise ValueError("Invalid handoff text.")
    for key, value in handoff.defaults:
        state[key] = value
    if handoff.source_key:
        # Keep the latest instruction and any attached public excerpt. The
        # destination page limits source sizes and runs its own privacy gate.
        state[handoff.source_key] = message[:handoff.max_chars]
