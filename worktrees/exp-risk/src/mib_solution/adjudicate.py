"""Rule-based adjudication from FIELD_MANUAL.md policy.

Trusted Manual Adjudicator Findings outrank form fields.
Otherwise: clear disqualifiers → DENIED; else NEEDS_REVIEW.
Auto-APPROVED only when a trusted adjudicator stamp says APPROVED
(100% precision on train; never from injection answer keys).
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
    finding = (fields.get("_adjudicator_finding") or "").upper() or None

    if text_len < 20:
        return "NEEDS_REVIEW", 0.10

    # 1) Visible MIB adjudicator stamp / signed manual note (highest trust)
    if finding == "DENIED":
        return "DENIED", 0.88
    if finding == "APPROVED":
        # Stamp overrides form traps (e.g. revoked sponsor printed then corrected)
        return "APPROVED", 0.82
    if finding == "NEEDS_REVIEW":
        return "NEEDS_REVIEW", 0.55

    # 2) Clear deny signals from recovered risk_flags / registry status mapping
    if flags & DISQUALIFYING_FLAGS:
        return "DENIED", 0.72
    if visa == "TRANSIT-7":
        return "DENIED", 0.68
    if fee == "unpaid" and visa != "DIP-1":
        return "DENIED", 0.65
    if sponsor in REVOKED_SPONSORS and visa != "DIP-1":
        return "DENIED", 0.62

    # Conservative default: no auto-approve without stamp
    return "NEEDS_REVIEW", 0.35
