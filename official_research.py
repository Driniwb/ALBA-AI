"""Conservative official-source navigation for ALBA legal research.

This is NOT a general web search engine or automatic comparative-law analysis.
Generate source URLs only from identified act references; never invent content.
EUR-Lex CELEX/NIM URL patterns follow the Publications Office guidance.
QBZ direct-link evidence must have an identifiable act/date; a numbered
act without date cannot simply be guessed as an ELI URL.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import quote

QBZ_BASE = "https://qbz.gov.al"
EU_BASE = "https://eur-lex.europa.eu/legal-content/EN"
EU_NIM_INDEX = "https://eur-lex.europa.eu/collection/n-law/mne.html?locale=en"

_AL_LAW = re.compile(
    r"(?i)\b(?:ligji(?:n|t)?|law)\s*(?:nr\.?|no\.?)\s*"
    r"(\d{1,4})\s*/\s*(20\d{2})\b"
)
_AL_DCM = re.compile(
    r"(?i)\b(?:vkm|vendimi?\s+nr\.?)\s*(?:nr\.?\s*)?"
    r"(\d{1,4})\s*/\s*(20\d{2})\b"
)
_EU_DIR = re.compile(
    r"(?i)\b(?:direktiv\w*|directive)\s*(?:\((?:EU|BE|EC)\)\s*)?"
    r"(20\d{2})\s*/\s*(\d{1,4})\b"
)
_CELEX = re.compile(r"(?i)\b(3\d{4}L\d{4})\b")
_LINK_REQUEST = re.compile(
    r"(?i)\b(?:link\w*|lidhj\w*|url|adres\w*|version\w*|"
    r"gjej\w*|find|where|open|hap|burim\w*|source\w*)\b"
)
_COUNTRIES = re.compile(
    r"(?i)\b(?:transpozim\w*|vende\w*|shtete\w*|"
    r"national\s+transposition|member\s+states|german\w*|"
    r"franc\w*|ital\w*|span\w*|vergleich\w*|compare|"
    r"krahas\w*|implement\w*|praktik\w*)\b"
)

# Exact identifiers independently checked against the official public
# act register. This is intentionally NOT an open-ended list of guessed dates.
_KNOWN_QBZ = {
    ("vendim", "584", "2003"): (
        "https://qbz.gov.al/eli/vendim/2003/08/28/584",
        "VKM nr. 584/2003, datë 28.8.2003, Rregullorja e Këshillit të Ministrave",
    ),
}

@dataclass(frozen=True)
class OfficialLink:
    label: str
    url: str
    scope: str  # known_act, official_eu_act, national_transposition, search
    note: str


def detect_reference(question: str, history: list[dict] | None = None) -> tuple[str, str, str] | None:
    """Resolve short follow-ups ('give me the link') against this chat alone."""
    candidates = [question]
    if history and _LINK_REQUEST.search(question):
        # Most recent earlier user question is stronger than a generated
        # assistant statement; do not borrow context from a different chat.
        candidates.extend(
            item.get("content", "")
            for item in reversed(history[-12:])
            if item.get("role") == "user"
        )
    for value in candidates:
        match = _AL_LAW.search(value)
        if match:
            return ("ligj", str(int(match.group(1))), match.group(2))
        match = _AL_DCM.search(value)
        if match:
            return ("vendim", str(int(match.group(1))), match.group(2))
        match = _CELEX.search(value)
        if match:
            return ("eu", match.group(1).upper(), "")
        match = _EU_DIR.search(value)
        if match:
            return ("eu", f"3{match.group(1)}L{int(match.group(2)):04d}", "")
    return None


def official_links(
    question: str, history: list[dict] | None = None
) -> list[OfficialLink]:
    identifier = detect_reference(question, history)
    if not identifier:
        return []
    kind, num, year = identifier
    if kind == "eu":
        out = [OfficialLink(
            label="EUR-Lex – teksti i direktivës " + num,
            url=f"{EU_BASE}/TXT/?uri=CELEX:{num}",
            scope="official_eu_act",
            note="Link zyrtar sipas CELEX; statusi dhe ndryshimet kontrollohen në faqen e aktit.",
        )]
        out.append(OfficialLink(
            label="National Transposition Measures – shtetet e BE-së",
            url=f"{EU_BASE}/NIM/?uri=CELEX:{num}",
            scope="national_transposition",
            note="Regjistri zyrtar i masave të njoftuara, jo vlerësim automatik i cilësisë së transpozimit.",
        ))
        return out
    if (kind, num, year) == ("ligj", "44", "2023"):
        # The Gazette PDF and consolidated base-law ELI are indexed and
        # independently visible. A standalone ELI for this amending act has
        # NOT been confirmed; do not fabricate one.
        return [
            OfficialLink(
                label="QBZ – Fletorja Zyrtare nr. 101/2023 (Ligji 44/2023)",
                url="https://qbz.gov.al/alfresco/webdav/FZ/2023/101/FZ-2023-101.pdf",
                scope="official_gazette",
                note="Botim zyrtar me tekstin e ligjit nr. 44/2023.",
            ),
            OfficialLink(
                label="QBZ – Ligji bazë nr. 69/2012, versionet e konsoliduara",
                url="https://qbz.gov.al/eli/ligj/2012/06/21/69",
                scope="known_act",
                note="Ligji bazë i ndryshuar nga ligji 44/2023; "
                     "zgjidhni dhe verifikoni versionin e zbatueshëm.",
            ),
        ]
    known = _KNOWN_QBZ.get((kind, num, year))
    if known:
        return [OfficialLink(
            label="QBZ – " + known[1],
            url=known[0], scope="known_act",
            note="Identitet i aktit i kontrolluar më parë; fuqia, ndryshimet dhe versioni final duhen konfirmuar në QBZ.",
        )]
    term = f'{kind} nr. {num}/{year}'
    search_url = (
        "https://www.google.com/search?q=" +
        quote('site:qbz.gov.al/eli/ "' + term + '"')
    )
    return [
        OfficialLink(
            label=f"Kërkim i aktit {term} në faqet e QBZ",
            url=search_url, scope="search",
            note="Kjo është lidhje kërkimi, JO faqe e verifikuar e aktit.",
        ),
        OfficialLink(
            label="Regjistri zyrtar QBZ",
            url=QBZ_BASE + "/",
            scope="search",
            note="Kontrolloni numrin, datën, titullin dhe versionet e aktit.",
        ),
    ]


def link_answer(question: str, history: list[dict] | None = None) -> str | None:
    """Answer explicit source-link requests with real URLs; no AI invention."""
    if not _LINK_REQUEST.search(question):
        return None
    links = official_links(question, history)
    if not links:
        return None
    reference = detect_reference(question, history)
    lines = ["Këto janë lidhjet për referencën e identifikuar në këtë bisedë:"]
    for entry in links:
        lines.append(f"- [{entry.label}]({entry.url}) — {entry.note}")
    if reference and reference[:2] == ("ligj", "44") and reference[2] == "2023":
        lines.append(
            "**Saktësim:** Ligji nr. 44/2023 lidhet me ndryshimet në "
            "legjislacionin për arsimin parauniversitar; nuk është ligji "
            "“Për administratën publike”."
        )
    lines.append(
        "ALBA nuk ka ende motor të përgjithshëm kërkimi me verifikim "
        "automatik të çdo akti. Linku i kërkimit nuk duhet trajtuar si "
        "version i konfirmuar në fuqi."
    )
    return "\n\n".join([lines[0], "\n".join(lines[1:])])
