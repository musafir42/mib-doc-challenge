"""Rule-based adjudication from FIELD_MANUAL.md policy.

Priority (general policy — no train-mined SPN extras or OCR typo forests):
1. Visible Finding line (strict APPROVED; clean DENIED / NEEDS_REVIEW)
2. Clean disqualifying phrases and structured risk flags
3. Manual-backed rules: TRANSIT-7, unpaid fee, public revoked sponsors, multi review flags
4. Stale arrival (non-DIP-1) when arrival is >180 days before packet receipt
5. Otherwise NEEDS_REVIEW

Prefer NEEDS_REVIEW over wrong APPROVED — catastrophic false approval is heavily penalized.
No multi-field auto-APPROVED: image-only DQ stamps are invisible to text extract.
"""

from __future__ import annotations

import re
from datetime import date, datetime

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

# Public FIELD_MANUAL revoked sponsors only (no train-mined extras).
REVOKED_SPONSORS = {
    "SPN-0007",
    "SPN-0139",
    "SPN-4040",
}

# Challenge packet receipt reference (dataset cut / public data version date).
PACKET_RECEIPT_DATE = date(2026, 7, 7)
STALE_DAYS = 180

# Clean Finding line — no OCR typo banks (Fouing/DEMED/…). Rely on FT rec + geometry.
FINDING_RE = re.compile(
    r"Finding\s*:\s*(APPROVED|DENIED|NEEDS_REVIEW)\b",
    re.IGNORECASE,
)

FINDING_APPROVED_STRICT_RE = re.compile(
    r"Finding:\s*APPROVED\b",
    re.IGNORECASE,
)

MANUAL_SPONSOR_RE = re.compile(
    r"Manual correction:\s*sponsor is\s*(SPN-\d{4})",
    re.IGNORECASE,
)

# Clean text-layer / OCR secondary DQ phrases (readable English, not garble maps).
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

# Explicit damaged-evidence reason → review (not deny via conflicting fee OCR).
DAMAGED_PACKET_RE = re.compile(
    r"damaged or contradictory visible evidence|"
    r"Packet contains damaged or contradictory",
    re.IGNORECASE,
)

# Clean "Disqualifying risk flag: <token>" lines only.
DISQUAL_RISK_LINE_RE = re.compile(
    r"Disqualifying\s+risk\s+flag\s*:\s*([A-Za-z_\s]{3,48})",
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


def _parse_arrival(value: str | None) -> date | None:
    raw = (value or "").strip()
    if not raw or raw == "1900-01-01":
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _is_stale_non_dip(arrival: date | None, visa: str) -> bool:
    """True when non-DIP-1 arrival is more than STALE_DAYS before packet receipt."""
    if arrival is None:
        return False
    if visa not in {"XW-1", "XW-2", "MED-3", "TRANSIT-7"}:
        return False
    age = (PACKET_RECEIPT_DATE - arrival).days
    return age > STALE_DAYS


def _multi_field_clean(fields: dict, visa: str, sponsor: str, text_len: int) -> bool:
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


def _normalize_finding_decision(raw: str) -> str | None:
    d = (raw or "").strip().upper()
    if d == "DENIED":
        return "DENIED"
    if d == "NEEDS_REVIEW":
        return "NEEDS_REVIEW"
    if d == "APPROVED":
        return "APPROVED"
    return None


def clean_risk_flags_from_text(text: str) -> set[str]:
    """Map clean DQ language in text to structured flag tokens (no garble bank)."""
    if not text:
        return set()
    found: set[str] = set()
    if EMBARGO_TEXT_RE.search(text):
        found.add("planetary_embargo")
    if BIOHAZARD_TEXT_RE.search(text):
        found.add("biohazard_red")
    if WARRANT_TEXT_RE.search(text):
        found.add("active_warrant")
    if MEMORY_TEXT_RE.search(text):
        found.add("memory_tampering")
    for m in DISQUAL_RISK_LINE_RE.finditer(text):
        blob = m.group(1).casefold().replace(" ", "_")
        for token in DISQUALIFYING_FLAGS | REVIEW_ONLY_FLAGS:
            if token in blob or token.replace("_", " ") in m.group(1).casefold():
                found.add(token)
    return found


# Back-compat alias for any external callers
def ocr_risk_flags(text: str) -> set[str]:
    return clean_risk_flags_from_text(text)


def adjudicate(fields: dict) -> tuple[str, float, str]:
    """Return (adjudication, legacy_conf, reason_code for calibrate)."""
    text = fields.get("_text") or ""
    text_len = int(fields.get("_text_len") or len(text) or 0)

    if text_len < 20:
        return "NEEDS_REVIEW", 0.10, "thin_text"

    # 1) Finding stamp / note (clean form only)
    if FINDING_APPROVED_STRICT_RE.search(text):
        return "APPROVED", 0.88, "finding_approved"

    finding_denied = False
    finding_review = False
    for m in FINDING_RE.finditer(text):
        decision = _normalize_finding_decision(m.group(1))
        if decision == "DENIED":
            finding_denied = True
            break
        if decision == "NEEDS_REVIEW":
            finding_review = True

    if finding_denied:
        return "DENIED", 0.90, "finding_denied"
    if finding_review:
        return "NEEDS_REVIEW", 0.75, "finding_review"

    if DAMAGED_PACKET_RE.search(text):
        return "NEEDS_REVIEW", 0.55, "damaged_packet"

    flags = _split_flags(fields.get("risk_flags", "none"))
    fee = (fields.get("fee_status") or "unknown").casefold()
    visa = (fields.get("visa_class") or "unknown").upper()
    sponsor = (fields.get("sponsor_id") or "").upper()
    arrival = _parse_arrival(fields.get("arrival_date"))

    manual_sponsor = MANUAL_SPONSOR_RE.search(text)
    if manual_sponsor:
        sponsor = manual_sponsor.group(1).upper()

    # 2) Clean DQ phrases → deny
    if EMBARGO_TEXT_RE.search(text):
        return "DENIED", 0.78, "text_dq"
    if BIOHAZARD_TEXT_RE.search(text):
        return "DENIED", 0.78, "text_dq"
    if WARRANT_TEXT_RE.search(text):
        return "DENIED", 0.78, "text_dq"
    if MEMORY_TEXT_RE.search(text):
        return "DENIED", 0.78, "text_dq"

    # 3) Structured + clean-text risk flags
    flags = flags | clean_risk_flags_from_text(text)
    if flags & DISQUALIFYING_FLAGS:
        return "DENIED", 0.70, "flags_dq"

    # 4) Manual-backed structured rules
    if visa == "TRANSIT-7":
        return "DENIED", 0.68, "transit7"
    if fee == "unpaid":
        if re.search(r"\b(?:waived|DIP-WAIVER|hardship\s+waiver)\b", text, re.I):
            pass  # contradictory → fall through to review
        else:
            return "DENIED", 0.72, "unpaid"
    if sponsor in REVOKED_SPONSORS and visa != "DIP-1":
        return "DENIED", 0.62, "revoked_sponsor"
    if len(flags & REVIEW_ONLY_FLAGS) >= 2:
        return "DENIED", 0.60, "multi_review"

    # 5) Stale arrival (FIELD_MANUAL date rule)
    if _is_stale_non_dip(arrival, visa):
        return "DENIED", 0.66, "stale_arrival"

    return "NEEDS_REVIEW", 0.35, "default_review"
