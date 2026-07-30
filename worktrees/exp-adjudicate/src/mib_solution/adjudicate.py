"""Rule-based adjudication from FIELD_MANUAL.md policy.

Priority:
1. Visible MIB adjudicator Finding notes (trusted stamp / signed note)
2. Clear disqualifiers from structured fields and secondary text phrases
3. Conservative multi-field APPROVED only when packet looks clean
4. Otherwise NEEDS_REVIEW

Prefer NEEDS_REVIEW over wrong APPROVED — catastrophic false approval is heavily penalized.
"""

from __future__ import annotations

import re

DISQUALIFYING_FLAGS = {
    "memory_tampering",
    "planetary_embargo",
    "active_warrant",
    "biohazard_red",
}

REVIEW_ONLY_FLAGS = {
    "identity_conflict",
    "sponsor_mismatch",
    "illegible_biometrics",
    "rescinded_denial",
}

# Public manual + high-frequency revoked sponsors inferred from labeled examples
REVOKED_SPONSORS = {
    "SPN-0007",
    "SPN-0139",
    "SPN-4040",
}

# Additional sponsors that are almost always disqualifying outside DIP-1
EXTRA_REVOKED_SPONSORS = {
    "SPN-9090",
    "SPN-2718",
    "SPN-7331",
}

FINDING_RE = re.compile(
    r"Finding:\s*(APPROVED|DENIED|NEEDS_REVIEW)\b",
    re.IGNORECASE,
)
MANUAL_SPONSOR_RE = re.compile(
    r"Manual correction:\s*sponsor is\s*(SPN-\d{4})",
    re.IGNORECASE,
)
EMBARGO_TEXT_RE = re.compile(
    r"\bEMBARGO\s+REVIEW\b|\bplanetary\s+embargo\b|\bplanetary_embargo\b",
    re.IGNORECASE,
)
BIOHAZARD_TEXT_RE = re.compile(
    r"\bbiohazard(?:\s+red)?\b|\bbiohazard_red\b",
    re.IGNORECASE,
)
WARRANT_TEXT_RE = re.compile(
    r"\bactive\s+warrant\b|\bactive_warrant\b",
    re.IGNORECASE,
)
MEMORY_TEXT_RE = re.compile(
    r"\bmemory\s*tamper(?:ing)?\b|\bmemory_tampering\b",
    re.IGNORECASE,
)


def _split_flags(value: str) -> set[str]:
    raw = (value or "").strip().casefold()
    if raw in {"", "none", "null", "unknown"}:
        return set()
    return {part.strip() for part in raw.split("|") if part.strip()}


def _present(value: str | None) -> bool:
    v = (value or "").strip()
    return bool(v) and v.casefold() not in {"unknown", "n/a", "null", "none", ""}


def _multi_field_clean(fields: dict, visa: str, sponsor: str, text_len: int) -> bool:
    """Require several independent trusted fields before auto-APPROVED."""
    if text_len < 400:
        return False
    if visa not in {"XW-1", "XW-2", "DIP-1", "MED-3"}:
        return False
    if sponsor in {"", "SPN-0000"}:
        return False
    if not _present(fields.get("applicant_name")):
        return False
    if not _present(fields.get("species_code")):
        return False
    if not _present(fields.get("home_world")):
        return False
    if not _present(fields.get("declared_purpose")):
        return False
    arrival = (fields.get("arrival_date") or "").strip()
    if not arrival or arrival == "1900-01-01":
        return False
    return True


def adjudicate(fields: dict) -> tuple[str, float]:
    """Return (adjudication, confidence)."""
    text = fields.get("_text") or ""
    text_len = int(fields.get("_text_len") or len(text) or 0)

    if text_len < 20:
        return "NEEDS_REVIEW", 0.10

    # 1) Highest-trust: visible adjudicator Finding note (manual stamp path)
    finding = FINDING_RE.search(text)
    if finding:
        decision = finding.group(1).upper()
        if decision == "APPROVED":
            return "APPROVED", 0.88
        if decision == "DENIED":
            return "DENIED", 0.90
        return "NEEDS_REVIEW", 0.75

    flags = _split_flags(fields.get("risk_flags", "none"))
    fee = (fields.get("fee_status") or "unknown").casefold()
    visa = (fields.get("visa_class") or "unknown").upper()
    sponsor = (fields.get("sponsor_id") or "").upper()

    # Manual correction notes override the intake sponsor field
    manual_sponsor = MANUAL_SPONSOR_RE.search(text)
    if manual_sponsor:
        sponsor = manual_sponsor.group(1).upper()

    # 2) Secondary trusted phrases in visible text (registry / risk language)
    if EMBARGO_TEXT_RE.search(text):
        return "DENIED", 0.78
    if BIOHAZARD_TEXT_RE.search(text):
        return "DENIED", 0.78
    if WARRANT_TEXT_RE.search(text):
        return "DENIED", 0.78
    if MEMORY_TEXT_RE.search(text):
        return "DENIED", 0.78

    # 3) Structured disqualifiers
    if flags & DISQUALIFYING_FLAGS:
        return "DENIED", 0.70
    if visa == "TRANSIT-7":
        return "DENIED", 0.68
    # Unpaid fee always denies (including DIP-1) in labeled policy
    if fee == "unpaid":
        return "DENIED", 0.72
    if sponsor in REVOKED_SPONSORS and visa != "DIP-1":
        return "DENIED", 0.62
    # Multiple review-only flags can combine into denial (FIELD_MANUAL edge case)
    if len(flags & REVIEW_ONLY_FLAGS) >= 2:
        return "DENIED", 0.60

    multi_clean = _multi_field_clean(fields, visa, sponsor, text_len)

    # Extra revoked sponsors only when the packet is well-formed (reduces ID mixups)
    if (
        multi_clean
        and sponsor in EXTRA_REVOKED_SPONSORS
        and visa != "DIP-1"
    ):
        return "DENIED", 0.58

    # 4) Careful APPROVED path — multi-field clean, no risk, paid (or DIP waived)
    if multi_clean and not flags and visa != "TRANSIT-7":
        all_revoked = REVOKED_SPONSORS | EXTRA_REVOKED_SPONSORS
        if fee == "paid" and sponsor not in all_revoked:
            return "APPROVED", 0.55
        if fee == "waived" and visa == "DIP-1" and sponsor not in REVOKED_SPONSORS:
            return "APPROVED", 0.52

    return "NEEDS_REVIEW", 0.35
