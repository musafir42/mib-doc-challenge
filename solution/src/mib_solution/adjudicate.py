"""Rule-based adjudication from FIELD_MANUAL.md policy.

Priority:
1. Visible MIB adjudicator Finding notes (trusted stamp / signed note)
   — OCR-tolerant variants of DENIED (DEMED/DENED/Deny, Fouing/Frdirg, …)
2. Clear disqualifiers from structured fields and secondary text phrases
3. Light OCR risk map: garbled biohazard/embargo/warrant/tamper tokens → DENIED
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

# Challenge packet receipt reference (dataset cut / public data version date).
PACKET_RECEIPT_DATE = date(2026, 7, 7)
STALE_DAYS = 180

# OCR-tolerant Finding line. Stamp OCR often drops the colon or mangles the
# keyword (Finding→Fouing/Frdirg/Finis) and DENIED→DEMED/DENED/Deny.
FINDING_RE = re.compile(
    r"(?:Finding|Findigg|Fouing|Fearg|Pearg|Frdirg|Feging|Findey|Findng|"
    r"Finis|Finsiege|F[il1]nd[il1]?[nhg]g?)"
    r"\s*[:.\-]?\s*"
    r"(APPROVED|DENIED|NEEDS_REVIEW|DENED|DEMED|DENIER|DENY)\b",
    re.IGNORECASE,
)

# Strict Finding APPROVED only (never promote OCR garbage to APPROVED)
FINDING_APPROVED_STRICT_RE = re.compile(
    r"Finding:\s*APPROVED\b",
    re.IGNORECASE,
)

MANUAL_SPONSOR_RE = re.compile(
    r"Manual correction:\s*sponsor is\s*(SPN-\d{4})",
    re.IGNORECASE,
)

# Clean text-layer secondary DQ phrases
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

# Adjudicator note reasons that are always NEEDS_REVIEW on train (text layer)
DAMAGED_PACKET_RE = re.compile(
    r"Packet contains damaged or contradictory|"
    r"damaged or contradictory visible evidence",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Light OCR risk map — garbled stamp / note tokens → DQ flag tokens
# Precision validated on train text layer (P(DENIED|hit) ≥ 0.97 for each).
# ---------------------------------------------------------------------------
OCR_RISK_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # planetary_embargo: planetery_embargo / plonetary embgmn / ctonetary embamen
    (
        re.compile(
            r"p[l1i][ao0]n[e3a]?t[e3a]?r[yi]?[\s_\-.]{0,3}emb[ao0er]{2,}",
            re.IGNORECASE,
        ),
        "planetary_embargo",
    ),
    # Heavy OCR garble: ntonetary enkgenn / oonetay enbgens / clensjery_emigenn
    (
        re.compile(
            r"\b[a-z]{0,4}n[toea]{1,4}t[aeor]{1,3}[yi]?[\s_\.]+"
            r"(?:emb|enb|enk|emig)[a-z]{0,8}\b",
            re.IGNORECASE,
        ),
        "planetary_embargo",
    ),
    (
        re.compile(
            r"[cp]l[aeo]n[a-z]{2,8}[\s_.]*(?:emb|emi|enb)",
            re.IGNORECASE,
        ),
        "planetary_embargo",
    ),
    # "risk fap/flap/sep: … emb*" adjudicator reason lines (OCR-tolerant)
    (
        re.compile(
            r"(?:risk|rick|isk|nek|deck)\s+"
            r"(?:flag|fap|flap|fing|fieg|fleg|fag|sep)[a-z]{0,4}"
            r"[\s:.\-]+[A-Za-z_\s]{0,24}"
            r"(?:emb|enb[g]?|enk[g]?|emig|ember|emiy)",
            re.IGNORECASE,
        ),
        "planetary_embargo",
    ),
    # "Embargo home world" registry line (and OCR "Embargo home word")
    (
        re.compile(r"\bEmbargo\s+home\s+wor", re.IGNORECASE),
        "planetary_embargo",
    ),
    (
        re.compile(r"\bEMBARGO\s+REVIEW\b", re.IGNORECASE),
        "planetary_embargo",
    ),
    # biohazard / bio hazard / biohazard_red
    (
        re.compile(
            r"\bb[il1]o[\s_\-.]{0,2}h[ae]z(?:ard)?(?:[\s_\-]*red)?\b|\bbiohazard_red\b",
            re.IGNORECASE,
        ),
        "biohazard_red",
    ),
    # active warrant
    (
        re.compile(r"\bact[il1]?ve?[\s_\-]*warr", re.IGNORECASE),
        "active_warrant",
    ),
    # memory tampering
    (
        re.compile(r"\bmem[oa]r[yi]?[\s_\-]*tamp", re.IGNORECASE),
        "memory_tampering",
    ),
]

# "Disqualifying risk flag: <token>" on Manual Adjudicator Notes (OCR-tolerant)
DISQUAL_RISK_LINE_RE = re.compile(
    r"(?:Disqual|Djscu|Djsou|Disquail|Disqually|Dpecug|Dpems|Djesu)[a-z]{0,14}\s+"
    r"(?:risk|rick|isk|nek|deck)\s+"
    r"(?:flag|fap|flap|fing|fieg|fleg|fag|sep)[a-z]{0,4}\s*[:.]\s*"
    r"([A-Za-z_\s\.]{3,48})",
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
    """Require several independent trusted fields before extra-revoke path."""
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
    """Map OCR Finding tokens to adjudication classes. APPROVED stays strict."""
    d = (raw or "").strip().upper()
    if d in {"DENIED", "DENED", "DEMED", "DENIER", "DENY"}:
        return "DENIED"
    if d == "NEEDS_REVIEW":
        return "NEEDS_REVIEW"
    if d == "APPROVED":
        # Only accept APPROVED when the strict "Finding: APPROVED" form also hits
        # (caller double-checks); bare OCR APPROVED is too easy to hallucinate.
        return "APPROVED"
    return None


def ocr_risk_flags(text: str) -> set[str]:
    """Light OCR risk map: scan full text (incl. OCR_FALLBACK) for DQ tokens.

    Returns structured disqualifying flag names. Safe to call on text-layer-only
    packets — patterns also match clean tokens.
    """
    if not text:
        return set()
    found: set[str] = set()
    for pat, token in OCR_RISK_PATTERNS:
        if pat.search(text):
            found.add(token)

    for m in DISQUAL_RISK_LINE_RE.finditer(text):
        blob = m.group(1).casefold()
        for pat, token in OCR_RISK_PATTERNS:
            if pat.search(blob):
                found.add(token)
        for token in DISQUALIFYING_FLAGS:
            if token in blob or token.replace("_", " ") in blob:
                found.add(token)
        # Ultra-short OCR fragments inside the disqual line
        if re.search(r"embarg|embergo|emhg|emiyern|embamen", blob):
            found.add("planetary_embargo")
        if re.search(r"bio\s*haz|biohaz", blob):
            found.add("biohazard_red")
        if "warr" in blob:
            found.add("active_warrant")
        if "tamp" in blob:
            found.add("memory_tampering")
    return found


def adjudicate(fields: dict) -> tuple[str, float]:
    """Return (adjudication, confidence)."""
    text = fields.get("_text") or ""
    text_len = int(fields.get("_text_len") or len(text) or 0)

    if text_len < 20:
        return "NEEDS_REVIEW", 0.10

    # 1) Highest-trust: visible adjudicator Finding note (manual stamp path)
    # Prefer strict APPROVED; OCR-tolerant DENIED / NEEDS_REVIEW.
    finding_denied = False
    finding_review = False
    if FINDING_APPROVED_STRICT_RE.search(text):
        return "APPROVED", 0.88

    for m in FINDING_RE.finditer(text):
        decision = _normalize_finding_decision(m.group(1))
        if decision == "DENIED":
            finding_denied = True
            break
        if decision == "NEEDS_REVIEW":
            finding_review = True
        # Ignore OCR "APPROVED" without strict form (already handled above)

    if finding_denied:
        return "DENIED", 0.90
    if finding_review:
        return "NEEDS_REVIEW", 0.75

    # Damaged/contradictory packet reason on adjudicator note → review.
    # Train text-layer: 8/8 NEEDS_REVIEW. Prevents OCR "unpaid" false denies.
    if DAMAGED_PACKET_RE.search(text):
        return "NEEDS_REVIEW", 0.55

    flags = _split_flags(fields.get("risk_flags", "none"))
    fee = (fields.get("fee_status") or "unknown").casefold()
    visa = (fields.get("visa_class") or "unknown").upper()
    sponsor = (fields.get("sponsor_id") or "").upper()
    arrival = _parse_arrival(fields.get("arrival_date"))

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

    # 3) Light OCR risk map (garbled stamp tokens)
    ocr_flags = ocr_risk_flags(text)
    if ocr_flags & DISQUALIFYING_FLAGS:
        return "DENIED", 0.76
    flags = flags | ocr_flags

    # 4) Structured disqualifiers
    if flags & DISQUALIFYING_FLAGS:
        return "DENIED", 0.70
    if visa == "TRANSIT-7":
        return "DENIED", 0.68
    # Unpaid fee always denies (including DIP-1) in labeled policy —
    # but skip when OCR fee contradicts a visible waiver token (waived↔unpaid).
    if fee == "unpaid":
        if re.search(r"\b(?:waived|DIP-WAIVER|hardship\s+waiver)\b", text, re.I):
            # Contradictory fee signals → review, not deny
            pass
        else:
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

    # 5) Stale arrival for non-DIP work visas (FIELD_MANUAL date rule)
    if _is_stale_non_dip(arrival, visa):
        return "DENIED", 0.66

    # No multi-field auto-APPROVED: image-only DQ stamps cause catastrophic FPs.
    return "NEEDS_REVIEW", 0.35
