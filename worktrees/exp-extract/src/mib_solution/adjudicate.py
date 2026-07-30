"""Rule-based adjudication from FIELD_MANUAL.md policy.

Baseline policy: only emit DENIED on clear disqualifiers; otherwise NEEDS_REVIEW.
Never auto-APPROVED — catastrophic false approval is heavily penalized by the scorer.
"""

from __future__ import annotations

DISQUALIFYING_FLAGS = {
    "memory_tampering",
    "planetary_embargo",
    "active_warrant",
    "biohazard_red",
}

REVOKED_SPONSORS = {
    "SPN-0007",
    "SPN-0139",
    "SPN-4040",
}


def _split_flags(value: str) -> set[str]:
    raw = (value or "").strip().casefold()
    if raw in {"", "none", "null", "unknown"}:
        return set()
    return {part.strip() for part in raw.split("|") if part.strip()}


def adjudicate(fields: dict) -> tuple[str, float]:
    """Return (adjudication, confidence)."""
    flags = _split_flags(fields.get("risk_flags", "none"))
    fee = (fields.get("fee_status") or "unknown").casefold()
    visa = (fields.get("visa_class") or "unknown").upper()
    sponsor = (fields.get("sponsor_id") or "").upper()
    text_len = int(fields.get("_text_len") or 0)

    if text_len < 20:
        return "NEEDS_REVIEW", 0.10

    # Clear deny signals only
    if flags & DISQUALIFYING_FLAGS:
        return "DENIED", 0.70
    if visa == "TRANSIT-7":
        return "DENIED", 0.68
    if fee == "unpaid" and visa != "DIP-1":
        return "DENIED", 0.65
    if sponsor in REVOKED_SPONSORS and visa != "DIP-1":
        return "DENIED", 0.62

    # Baseline: no auto-approve (avoids catastrophic false approvals)
    return "NEEDS_REVIEW", 0.35
