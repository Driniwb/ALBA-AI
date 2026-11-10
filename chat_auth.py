"""OIDC identity checks for persistent ALBA conversations.

Streamlit validates OIDC on login but does not automatically check whether
the stored identity token has since expired. This local check prevents using
a stale cookie for database-backed access.
"""
from __future__ import annotations

from datetime import datetime, timezone
from collections.abc import Mapping

from chat_store import owner_key_from_oidc


def verified_chat_owner(claims: Mapping, *, now_seconds: float | None = None) -> str:
    """Return a pseudonymous owner ID only for a current identity token.

    This is a *supplement* to Streamlit's provider-validated login, not an
    independent JWT signature verification. The caller must confirm
    st.user.is_logged_in and use claims received from Streamlit.
    """
    if not isinstance(claims, Mapping):
        raise ValueError("Authenticated OIDC claims required.")
    expiry = claims.get("exp")
    if isinstance(expiry, bool) or not isinstance(expiry, (int, float)):
        raise ValueError("OIDC token expiry claim is missing.")
    now = (
        datetime.now(timezone.utc).timestamp()
        if now_seconds is None else float(now_seconds)
    )
    if expiry <= now:
        raise ValueError("OIDC identity has expired.")
    not_before = claims.get("nbf")
    if (not_before is not None
            and (not isinstance(not_before, (int, float))
                 or isinstance(not_before, bool) or not_before > now + 60)):
        raise ValueError("OIDC identity is not yet valid.")
    issued = claims.get("iat")
    if (issued is not None
            and (not isinstance(issued, (int, float))
                 or isinstance(issued, bool) or issued > now + 60)):
        raise ValueError("OIDC issue time is invalid.")
    return owner_key_from_oidc(claims.get("iss", ""), claims.get("sub", ""))
