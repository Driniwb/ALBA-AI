"""Conservative article/paragraph/letter splitting for a draft ToC.

Each unit retains the entire extracted source text span. Results are NOT
verified literal transcriptions of EUR-Lex, especially if extracted from PDF.
Sentences are not split automatically, as that needs legal-editor judgment.
"""
from __future__ import annotations

import re
from toc_builder import Provision, split_provisions

# Only standalone numbering at the beginning of a line, never "1.8.7" or dates.
PARAGRAPH = re.compile(r"^\s*(?:(\d{1,2})\.(?!\d)|\((\d{1,2})\))\s+(?=\S)")
LETTER = re.compile(r"^\s*\(([a-z])\)\s+(?=\S)", re.IGNORECASE)
ARTICLE_NUM = re.compile(r"^(?:Article|Neni)\s+(\d+[a-z]?)\b", re.I)
ANNEX_NUM = re.compile(r"^(?:ANNEX|ANEKSI|ANEKS)\s+([IVXLCDM]+|\d+)\b", re.I)


def split_toc_units(text: str) -> list[Provision]:
    """Split as far as structural markers are unambiguous; never silently omit."""
    articles = split_provisions(text)
    result: list[Provision] = []
    for article in articles:
        match = ARTICLE_NUM.match(article.reference)
        annex = ANNEX_NUM.match(article.reference)
        if match:
            base = match.group(1)
            intro_ref = f"Neni {base} (hyrja)"
        elif annex:
            base = article.reference
            intro_ref = base
        else:
            result.append(article)
            continue

        lines = article.text.split("\n")
        previous_start = 0
        previous_ref = intro_ref
        active_paragraph = None

        for i, line in enumerate(lines[1:], 1):
            pm = PARAGRAPH.match(line)
            lm = LETTER.match(line)
            if not pm and not lm:
                continue
            if pm:
                num = pm.group(1) or pm.group(2)
                active_paragraph = num
                next_ref = f"{base}.{num}"
            else:
                letter = lm.group(1).lower()
                next_ref = (
                    f"{base}.{active_paragraph}.{letter}"
                    if active_paragraph else f"{base}.{letter}"
                )
            segment = "\n".join(lines[previous_start:i])
            if segment:
                result.append(Provision(previous_ref, segment))
            previous_start = i
            previous_ref = next_ref

        tail = "\n".join(lines[previous_start:])
        if tail:
            result.append(Provision(previous_ref, tail))

    # Full reconstruction is critical: segmentation cannot silently drop text.
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    reconstruction = "\n".join(p.text for p in result)
    if reconstruction != normalized:
        raise AssertionError("Segmentation did not preserve every source character.")
    return result


def first_n_articles(text: str, count: int = 3) -> list[Provision]:
    """Pilot scope: exactly Article 1 through N, without preambles/annexes."""
    if not 1 <= count <= 8:
        raise ValueError("Pilot accepts 1 to 8 articles.")
    all_units = split_toc_units(text)
    output: list[Provision] = []
    for unit in all_units:
        m = re.match(r"^(?:Neni\s+)?(\d+)(?:\.|(?:\s*\())", unit.reference)
        if not m:
            continue
        if 1 <= int(m.group(1)) <= count:
            output.append(unit)
    if not output:
        raise ValueError("Nenet e kërkuara nuk u identifikuan nga dokumenti.")
    return output
