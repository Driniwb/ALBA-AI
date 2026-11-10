"""English-only user-facing UI copy for errors from Albanian drafting backends.

The underlying legal-writing and communication prompts remain in Albanian,
because ALBA's *output* is intended to be Albanian. Internal exceptions are
not rendered verbatim to avoid exposing source text or inconsistent languages.
"""
from privacy_guard import BLOCK_NOTICE, BLOCK_NOTICE_SQ


def friendly_error(error: Exception | str, *, context: str = "general") -> str:
    message = str(error)
    if message == BLOCK_NOTICE_SQ or "ALBA e bllokoi" in message:
        return BLOCK_NOTICE
    if "Cloudflare" in message or "shërbimi AI" in message:
        return "The AI service could not complete the request. Check its configuration or try again."
    if "tejkalon" in message or "too long" in message or "shumë i gjatë" in message:
        return "The supplied text is too long. Select a shorter section."
    if "Mungon përkthimi" in message:
        return "Some selected provisions have no translation yet. Complete them before exporting."
    if "rreshta bosh" in message or "shtatë kolona" in message or "7 kolona" in message:
        return "The blank Word ToC template must use the required seven-column layout."
    if context == "template":
        return (
            "The Word template could not be processed. Upload a blank seven-column "
            "DOCX, not a completed concordance table."
        )
    if context == "toc":
        return (
            "The directive could not be processed. Check the file type, "
            "article structure, or choose a shorter text-based document."
        )
    if context == "communication":
        return "The draft could not be generated. Check the input and try again."
    return "The request could not be processed. Check the text and attachment."
