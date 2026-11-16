"""Read-only official-source research for public EU and Albanian law.

Live retrieval is best-effort, bounded, and performed ONLY on a user
submission that identifies an act. A URL is not proof that its text was read.
Country-level NIM entries are notified acts, NOT proof of legal conformity.
No whole user chat, confidential data or arbitrary URLs are sent to sources.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import unescape
import re
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from official_research import detect_reference, official_links
from legal_source_documents import retrieve_qbz_document

MAX_HTML_BYTES = 5_000_000
MAX_EXCERPT_CHARS = 4800
NIM_COUNTRIES = {
    "Germany": "DE", "Spain": "ES", "France": "FR", "Italy": "IT",
    "Greece": "EL", "Netherlands": "NL", "Poland": "PL",
    "Denmark": "DK", "Finland": "FI", "Sweden": "SE",
    "Croatia": "HR",
}
COUNTRY_ALIASES = {
    "germany": "Germany", "gjermani": "Germany", "deutschland": "Germany",
    "spain": "Spain", "spanj": "Spain", "españa": "Spain",
    "france": "France", "franc": "France",
    "italy": "Italy", "itali": "Italy", "italia": "Italy",
    "greece": "Greece", "greq": "Greece",
    "netherlands": "Netherlands", "holland": "Netherlands", "holand": "Netherlands",
    "poland": "Poland", "poloni": "Poland",
    "denmark": "Denmark", "danimark": "Denmark",
    "finland": "Finland", "finland": "Finland",
    "sweden": "Sweden", "sued": "Sweden",
    "croatia": "Croatia", "kroac": "Croatia",
}
SKIP_TEXT = ("javascript", "please enable cookies", "verify that you are not a robot")
FOLLOWUP = re.compile(
    r"(?i)\b(?:this|that|it|these|those|previous|earlier|"
    r"k[eë]t[eë]|k[eë]saj|k[eë]tij|at[eë]|m[eë]\s+par[eë]|"
    r"krahaso|compare|implement|transpoz|practices?|praktik|"
    r"german|gjerman|franc|span|ital)\b"
)


@dataclass(frozen=True)
class ResearchSource:
    label: str
    url: str
    status: str   # retrieved_text, notified_measures, entry_point
    note: str


@dataclass
class ResearchBundle:
    evidence: str = ""
    sources: list[ResearchSource] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checked_at_utc: str = ""
    def was_retrieved(self) -> bool:
        return any(s.status != "entry_point" for s in self.sources)


def _safe_url(url: str) -> bool:
    parts = urlsplit(url)
    return (
        parts.scheme == "https" and parts.hostname in {
            "eur-lex.europa.eu", "publications.europa.eu",
            "qbz.gov.al", "www.qbz.gov.al"
        } and parts.username is None and parts.password is None
        and parts.port in {None, 443} and not parts.fragment
    )


def _download_html(url: str, *, get=None) -> str:
    """Bounded read, official HTTPS only, with checked redirects."""
    if not _safe_url(url):
        raise ValueError("Source URL is not an approved official endpoint.")
    caller = get or requests.get
    current = url
    for _ in range(3):
        res = caller(
            current, timeout=9, allow_redirects=False,
            headers={"User-Agent": "ALBA-Legal-Research/0.3 (public, read-only)",
                     "Accept": "text/html,application/xhtml+xml"},
            stream=True,
        )
        status = res.status_code
        if 300 <= status < 400:
            location = res.headers.get("Location", "")
            current = urljoin(current, location)
            if not _safe_url(current):
                raise ValueError("Official source redirected outside trusted domains.")
            continue
        if status != 200:
            raise ValueError(f"Official endpoint returned HTTP {status}.")
        content_type = res.headers.get("Content-Type", "text/html").split(";")[0].lower()
        if content_type not in {"text/html", "application/xhtml+xml", "text/plain"}:
            raise ValueError("Expected official HTML, got another content type.")
        chunks, size = [], 0
        if hasattr(res, "iter_content"):
            iterator = res.iter_content(chunk_size=65536)
        else:
            iterator = (res.content,)
        for chunk in iterator:
            size += len(chunk)
            if size > MAX_HTML_BYTES:
                raise ValueError("Official page exceeded the safe download limit.")
            chunks.append(chunk)
        body = b"".join(chunks).decode("utf-8", errors="replace")
        if any(term in body[:2000].casefold() for term in SKIP_TEXT):
            raise ValueError("Official site requires interactive access.")
        return body
    raise ValueError("Official site redirected too many times.")


def _normalise(s: str) -> str:
    return re.sub(r"\s+", " ", unescape(s)).strip()


def _country_requests(prompt: str, chosen: list[str] | tuple[str, ...]) -> list[str]:
    countries = [
        x for x in chosen if x in NIM_COUNTRIES
    ]
    text = prompt.casefold()
    for match, country in COUNTRY_ALIASES.items():
        if match in text and country not in countries:
            countries.append(country)
    if not countries and re.search(
        r"(?i)\b(?:member states|other countries|"
        r"shtete\w*\s+an[eë]tare|vende\w*\s+t[eë]\s+tjera|"
        r"national transposition)\b", prompt,
    ):
        countries = ["Germany", "Spain"]
    return countries[:4]


def _nim_entries(html: str, country: str) -> tuple[int | None, list[tuple[str, str]]]:
    """Extract a country section only if a nearby declared count confirms it.

    Fail closed rather than interpreting navigation links as national laws.
    The website structure can change; an empty list means 'not extracted'.
    """
    soup = BeautifulSoup(html, "html.parser")
    for elem in soup(["script", "style", "nav"]):
        elem.decompose()
    tokens = []
    for item in soup.find_all(string=True):
        value = _normalise(str(item))
        if not value or len(value) > 1200:
            continue
        p = item.parent
        href = p.get("href") if p and p.name == "a" else None
        tokens.append((value, urljoin("https://eur-lex.europa.eu/", href) if href else ""))
    for start, (value, _) in enumerate(tokens):
        if value.casefold() not in {country.casefold(), (country + " " + country).casefold()}:
            continue
        preview = " ".join(x for x, _ in tokens[start:start+45])
        found = re.search(r"Number of measures:\s*(\d{1,4})", preview, re.I)
        if not found:
            continue
        count = int(found.group(1))
        end = min(len(tokens), start+800)
        for n in range(start+5, end):
            v = tokens[n][0]
            if n > start+15 and v.casefold() in {
                (c+" "+c).casefold() for c in NIM_COUNTRIES if c != country
            }:
                end = n
                break
        entries, seen = [], set()
        for value, url in tokens[start:end]:
            if (not url or not _safe_url(url) or
                url in seen or len(value) < 18 or len(value) > 350 or
                re.search(r"(?i)^(?:national website|transposition deadline|"
                          r"number of measures|direct text access|translate)", value)):
                continue
            if "eur-lex.europa.eu" not in urlsplit(url).hostname:
                continue
            # Do not treat navigation, document title or country-name links as
            # notified national acts. These must be individual NIM records.
            if not any(x in url for x in ("/legal-content/", "/national-law/", "CELEX:7", "CELEX%3A7")):
                continue
            seen.add(url)
            entries.append((value[:240], url))
            if len(entries) >= 6:
                break
        return count, entries
    return None, []


def _eu_text_excerpt(html: str, celex: str, question: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for elem in soup(["script", "style", "nav", "footer"]):
        elem.decompose()
    for selector in (
        "#document1", "#documentContent", ".eli-container",
        ".eli-main-content", "#text", ".documentText"
    ):
        main = soup.select_one(selector)
        if main:
            break
    else:
        main = soup
    text = _normalise(main.get_text(" ", strip=True))
    if not (
        celex in text.upper()
        or (
            celex[1:5] in text
            and re.search(r"\b(?:Directive|Regulation|Decision)\b", text[:16000], re.I)
        )
    ):
        return ""
    if len(text) < 500:
        return ""
    section = re.search(r"(?i)\b(?:Article|Neni)\s+(\d{1,3})\b", question)
    if section:
        match = re.search(
            rf"(?i)\bArticle\s+{int(section.group(1))}\b", text
        )
        if match:
            return text[max(0, match.start()-120):match.start()+MAX_EXCERPT_CHARS]
    first = re.search(r"\bArticle\s+1\b", text, re.I)
    if first and first.start() < len(text) - 400:
        return text[max(0, first.start()-130):first.start()+MAX_EXCERPT_CHARS]
    return text[:MAX_EXCERPT_CHARS]


def research_for_chat(
    question: str, history: list[dict] | None = None,
    jurisdictions: list[str] | tuple[str, ...] | None = None,
    *, get=None, qbz_retrieve=None,
) -> ResearchBundle:
    """Research the act identified by the new question or an explicit follow-up.

    Source failures never suppress the user's chat message. An output with
    entry_point-only sources is NOT represented as verified research.
    """
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    bundle = ResearchBundle(checked_at_utc=now)
    history = history or []
    jurisdictions = jurisdictions or []
    reference = detect_reference(question, history if FOLLOWUP.search(question) else [])
    if not reference:
        return bundle
    kind, number, year = reference
    links = official_links(question, history)
    for link in links:
        if _safe_url(link.url):
            bundle.sources.append(ResearchSource(
                link.label, link.url, "entry_point", link.note
            ))
    if kind == "eu":
        source_url = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:" + number
        try:
            html = _download_html(source_url, get=get)
            passage = _eu_text_excerpt(html, number, question)
            if passage:
                bundle.evidence += (
                    f"\n[OFFICIAL EU TEXT EXCERPT; CELEX {number}; fetched UTC {now}; "
                    "legal status and consolidation NOT certified]\n"
                    + passage + "\n[/OFFICIAL EU TEXT EXCERPT]\n"
                )
                bundle.sources.append(ResearchSource(
                    f"EUR-Lex: read text CELEX {number}", source_url,
                    "retrieved_text", "Identifying excerpt read; not a full-act verification."
                ))
            else:
                bundle.warnings.append(
                    "EUR-Lex page opened, but its legislative text could not be identified."
                )
        except (requests.RequestException, ValueError, OSError) as exc:
            bundle.warnings.append("EUR-Lex text unavailable: " + str(exc)[:110])
        countries = _country_requests(question, jurisdictions)
        if countries:
            nim_url = "https://eur-lex.europa.eu/legal-content/EN/NIM/?uri=CELEX:" + number
            try:
                nim_html = _download_html(nim_url, get=get)
                blocks = []
                for country in countries:
                    count, measures = _nim_entries(nim_html, country)
                    if count is None:
                        bundle.warnings.append(
                            country + ": EUR-Lex NIM country entries could not be extracted."
                        )
                        continue
                    blocks.append(
                        f"{country}: EUR-Lex reports {count} notified national measure(s). "
                        "This count does not establish full compliance."
                    )
                    blocks.extend(
                        f"- {title} ({url})" for title, url in measures[:5]
                    )
                    bundle.sources.append(ResearchSource(
                        f"EUR-Lex national transposition – {country}",
                        nim_url, "notified_measures",
                        f"EUR-Lex NIM section read: {count} notified measures; "
                        "individual national texts not independently assessed.",
                    ))
                if blocks:
                    bundle.evidence += (
                        "\n[OFFICIAL EUR-LEX NIM RECORDS; retrieved UTC "
                        + now + "; notifications, NOT compliance determinations]\n"
                        + "\n".join(blocks)[:3100]
                        + "\n[/OFFICIAL EUR-LEX NIM RECORDS]\n"
                    )
            except (requests.RequestException, ValueError, OSError) as exc:
                bundle.warnings.append(
                    "EUR-Lex national transposition data unavailable: " + str(exc)[:110]
                )
        return bundle
    # Albanian law: fetch actual published PDFs ONLY when an exact permitted
    # ELI act URL was identified. Act numbers alone must never produce guessed
    # ELI document locations.
    eli = next(
        (link.url for link in bundle.sources if link.status == "entry_point"
         and re.fullmatch(
             r"https://qbz\.gov\.al/eli/(?:ligj|vendim|udhezim|urdher)/"
             r"\d{4}/\d{2}/\d{2}/\d+(?:-\d+)?", link.url
         )), None
    )
    if not eli:
        return bundle
    try:
        retriever = qbz_retrieve or retrieve_qbz_document
        evidence, raw = retriever(eli)
        if evidence.identity_observed and evidence.source_text_retrieved:
            bundle.evidence = (
                f"[OFFICIAL QBZ PDF EXCERPT; {eli}; fetched UTC {now}; "
                "current status and all amendments NOT certified]\n"
                + raw[:MAX_EXCERPT_CHARS]
                + "\n[/OFFICIAL QBZ PDF EXCERPT]"
            )
            bundle.sources.append(ResearchSource(
                "QBZ – extracted public act PDF", evidence.selected_file_url or eli,
                "retrieved_text", "A readable official PDF excerpt was obtained."
            ))
        else:
            bundle.warnings.append("QBZ PDF could not be read and identified with confidence.")
    except (requests.RequestException, ValueError, OSError) as exc:
        bundle.warnings.append("QBZ document retrieval failed: " + str(exc)[:110])
    return bundle


def source_note(bundle: ResearchBundle) -> str:
    """Persist source trace in the assistant message, across app restarts."""
    if not bundle.sources:
        return ""
    verified = [s for s in bundle.sources if s.status != "entry_point"]
    if not verified:
        return ""
    lines = [
        "\n\n---",
        "**Official source trace (read-only; not a legal-status certificate)**",
        f"Checked: {bundle.checked_at_utc} UTC",
    ]
    for item in verified[:5]:
        label = re.sub(r"[\[\]\n\r]", "", item.label)[:130]
        lines.append(f"- [{label}]({item.url}) — {item.note}")
    return "\n".join(lines)
