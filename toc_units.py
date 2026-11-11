"""Conservative article/paragraph/letter splitting for a 7-column Word ToC.

Article heading and title belong to the FIRST substantive unit, not to a
separate introductory row. No source character may be silently omitted.
"""
from __future__ import annotations

import re
from toc_builder import Provision, split_provisions

# Standalone paragraph/letter numbering at the start of a line. Never match
# decimals or technical references such as 1.8.7.
PARAGRAPH = re.compile(
    r"^\s*(?:(\d{1,3})\.(?!\d)|\((\d{1,3})\))(?=\s|$)"
)
LETTER = re.compile(r"^\s*\(([a-z])\)(?=\s|$)", re.IGNORECASE)
ARTICLE_NUM = re.compile(r"^(?:Article|Neni)\s+(\d+[a-z]?)\b", re.I)
ANNEX_NUM = re.compile(r"^(?:ANNEX|ANEKSI|ANEKS)\s+([IVXLCDM]+|\d+)\b", re.I)
MAX_SELECTED_ARTICLES = 120


def split_toc_units(text: str) -> list[Provision]:
    """Split by legal unit, merging article title into the next paragraph.

    For an unnumbered article keep the complete article as one row. For
    numbered articles place 'Article X', its heading and point 1 in the SAME
    row (reference X.1); subsequent paragraphs and letters become new rows.
    """
    articles = split_provisions(text)
    result: list[Provision] = []
    for article in articles:
        match = ARTICLE_NUM.match(article.reference)
        annex = ANNEX_NUM.match(article.reference)
        if not match and not annex:
            result.append(article)
            continue

        base = match.group(1) if match else article.reference
        lines = article.text.split("\n")
        markers: list[tuple[int, str]] = []
        active_paragraph: str | None = None
        for i, line in enumerate(lines[1:], 1):
            pm = PARAGRAPH.match(line)
            lm = LETTER.match(line)
            if pm:
                num = pm.group(1) or pm.group(2)
                active_paragraph = num
                ref = f"{base}.{num}"
            elif lm:
                letter = lm.group(1).lower()
                ref = (
                    f"{base}.{active_paragraph}.{letter}"
                    if active_paragraph else f"{base}.{letter}"
                )
            else:
                continue
            markers.append((i, ref))

        if not markers:
            # No separate 'Neni X (hyrja)' row.
            result.append(Provision(f"Neni {base}" if match else base, article.text))
            continue

        for i, (start, ref) in enumerate(markers):
            # Keep heading + title and all text before point 1 in point 1.
            from_line = 0 if i == 0 else start
            to_line = markers[i + 1][0] if i + 1 < len(markers) else len(lines)
            part = "\n".join(lines[from_line:to_line])
            if part:
                result.append(Provision(ref, part))

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    reconstruction = "\n".join(unit.text for unit in result)
    if reconstruction != normalized:
        raise AssertionError("Segmentation did not preserve every source character.")
    if len(result) > 750:
        raise ValueError("Too many legal units (more than 750); split the directive.")
    return result


def first_n_articles(text: str, count: int = 3) -> list[Provision]:
    """Select up to N articles; heading/title stay in their first row."""
    if not 1 <= count <= MAX_SELECTED_ARTICLES:
        raise ValueError(f"Choose between 1 and {MAX_SELECTED_ARTICLES} articles.")
    all_units = split_toc_units(text)
    output: list[Provision] = []
    for unit in all_units:
        match = re.match(
            r"^(?:Neni\s+)?(\d+[a-z]?)(?:\.|$|\s*\()", unit.reference, re.I
        )
        if match:
            article_num = re.match(r"\d+", match.group(1))
            if article_num and 1 <= int(article_num.group(0)) <= count:
                output.append(unit)
    if not output:
        raise ValueError("Nenet e kërkuara nuk u identifikuan nga dokumenti.")
    return output
