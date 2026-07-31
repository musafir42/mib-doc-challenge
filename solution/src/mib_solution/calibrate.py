"""Honest uncertainty estimates for Brier calibration.

Scoring (evaluate.py): target = 1 if adjudication correct else 0;
calibration_score = 20 * max(0, 1 - 2 * mean_brier).

Confidence is high only when evidence is strong AND the decision is
Finding-backed or a clear structured deny. Low when the packet is thin,
OCR-dependent, or lands in the default NEEDS_REVIEW dump bin.

Does not change adjudication — confidence only.
"""

from __future__ import annotations

# Path priors from full-train OCR path accuracy (modal_full_ocr, n=1000),
# mildly shrunk away from 0/1. Residual stamp OCR can be slightly noisier
# on transit/unpaid, so those sit a bit under full-train rates.
PATH_CONF: dict[str, float] = {
    "short_text": 0.12,
    "finding_approved": 0.98,
    "finding_denied": 0.98,
    "finding_review": 0.96,
    "text_dq": 0.96,
    "flags_dq": 0.94,
    "transit7": 0.88,
    "unpaid": 0.88,
    "revoked": 0.92,
    "multi_review": 0.62,
    "extra_revoked": 0.95,
    "default_review": 0.28,  # refined by features below
}

FIELD_KEYS = (
    "applicant_name",
    "species_code",
    "home_world",
    "visa_class",
    "sponsor_id",
    "arrival_date",
    "declared_purpose",
    "risk_flags",
    "fee_status",
)

REVIEW_CONFLICT_FLAGS = (
    "identity_conflict",
    "sponsor_mismatch",
    "illegible_biometrics",
    "rescinded_denial",
)


def _present(value: str | None) -> bool:
    v = (value or "").strip()
    return bool(v) and v.casefold() not in {"unknown", "n/a", "null", "none", ""}


def _field_count(fields: dict) -> int:
    n = 0
    for key in FIELD_KEYS:
        val = fields.get(key)
        if key == "arrival_date":
            if _present(val) and str(val).strip() != "1900-01-01":
                n += 1
        elif key == "risk_flags":
            raw = (val or "").strip().casefold()
            if raw and raw not in {"none", "null", "unknown"}:
                n += 1
        elif key == "sponsor_id":
            s = (val or "").strip().upper()
            if s and s not in {"SPN-0000", "UNKNOWN"}:
                n += 1
        elif _present(val):
            n += 1
    return n


def _risk_present(fields: dict) -> bool:
    raw = (fields.get("risk_flags") or "").strip().casefold()
    return bool(raw) and raw not in {"", "none", "null", "unknown"}


def _unresolved_conflicts(fields: dict) -> bool:
    """Review-only conflict flags still present (unresolved identity/sponsor)."""
    raw = (fields.get("risk_flags") or "").strip().casefold()
    if not raw or raw in {"none", "null", "unknown"}:
        return False
    return any(flag in raw for flag in REVIEW_CONFLICT_FLAGS)


def _text_len(fields: dict) -> int:
    if fields.get("_text_len") is not None:
        try:
            return int(fields["_text_len"])
        except (TypeError, ValueError):
            pass
    return len(fields.get("_text") or "")


def _page_count(fields: dict) -> int:
    """Page-count proxy: explicit _page_count or coarse text-length buckets."""
    if fields.get("_page_count") is not None:
        try:
            return max(1, int(fields["_page_count"]))
        except (TypeError, ValueError):
            pass
    # ~1 page of form text is typically a few hundred chars
    tl = _text_len(fields)
    if tl < 400:
        return 1
    if tl < 1200:
        return 2
    return 3


def _is_thin(fields: dict, n_fields: int) -> bool:
    """Thin packet: few recovered fields, short text, or single short page."""
    tl = _text_len(fields)
    pages = _page_count(fields)
    return n_fields <= 4 or tl < 250 or (pages <= 1 and tl < 400)


def _clamp(value: float, lo: float = 0.05, hi: float = 0.99) -> float:
    return float(max(lo, min(hi, value)))


def _default_review_confidence(fields: dict) -> float:
    """NEEDS_REVIEW dump-bin confidence from packet features.

    Full-train default_review accuracy ~0.36 overall:
      - risk flags present → ~0.83 (often true review)
      - no risk, fee unknown → ~0.49
      - no risk, paid/waived → ~0.28–0.32
    Residual dump accuracy is lower (~0.22); keep no-risk conf modest so
    over-confidence on missed A/D does not burn Brier.
    """
    fee = (fields.get("fee_status") or "unknown").casefold()
    n_fields = _field_count(fields)
    text_len = _text_len(fields)
    ocr_used = bool(fields.get("_ocr_used"))
    risk = _risk_present(fields)
    conflict = _unresolved_conflicts(fields)
    thin = _is_thin(fields, n_fields)

    # Structured risk / unresolved conflicts → review more often correct
    if risk or conflict:
        conf = 0.58
        if conflict:
            conf += 0.04
        if fee == "unknown":
            conf += 0.05
        if n_fields >= 8:
            conf += 0.04
        if thin:
            conf -= 0.06
        return _clamp(conf, lo=0.05, hi=0.88)

    # No risk flags: dump bin is frequently a missed APPROVED/DENIED
    if fee == "unknown":
        conf = 0.34
    elif fee == "waived":
        conf = 0.20
    elif fee == "paid":
        conf = 0.22
    else:
        conf = 0.26

    if thin:
        conf = min(conf, 0.14)
    if n_fields >= 8:
        # Complete clean packet still in review → likely wrong A/D holdout
        conf -= 0.04
    if ocr_used and thin:
        # OCR-only thin packet: low signal
        conf -= 0.03
    if text_len < 200:
        conf -= 0.03
    elif text_len > 1200 and not ocr_used:
        conf += 0.02

    # Cap: never high-confidence on default review without risk evidence
    return _clamp(conf, lo=0.05, hi=0.50)


def _deny_confidence(fields: dict, path: str) -> float:
    """Confidence for non-Finding DENIED paths."""
    base = PATH_CONF.get(path, 0.75)
    n_fields = _field_count(fields)
    thin = _is_thin(fields, n_fields)
    risk = _risk_present(fields)
    ocr_used = bool(fields.get("_ocr_used"))

    if thin:
        base -= 0.10
    if path in ("transit7", "unpaid") and n_fields <= 6:
        base -= 0.04
    if path in ("flags_dq", "text_dq", "multi_review") and risk:
        base += 0.02
    # OCR-driven text_dq can false-fire stamps; mild haircut when OCR used
    if path == "text_dq" and ocr_used and n_fields <= 5:
        base -= 0.04

    return _clamp(base)


def calibrate(
    fields: dict,
    adjudication: str,
    reason: str | None = None,
) -> float:
    """Return confidence in [0, 1] for the given adjudication.

    Prefer fields["_adj_reason"] set by adjudicate(); otherwise use reason arg
    or fall back to adjudication-type priors.
    """
    path = (reason or fields.get("_adj_reason") or "").strip()
    adj = (adjudication or "NEEDS_REVIEW").strip().upper()

    if not path:
        if adj == "APPROVED":
            path = "finding_approved"
        elif adj == "DENIED":
            path = "flags_dq"
        else:
            path = "default_review"

    if path == "default_review":
        return _default_review_confidence(fields)

    if path == "short_text":
        return 0.10

    if path.startswith("finding"):
        # Finding-backed: strongest evidence; high only for this path family
        base = PATH_CONF.get(path, 0.96)
        if _is_thin(fields, _field_count(fields)):
            base -= 0.02
        return _clamp(base, lo=0.85, hi=0.99)

    if path in PATH_CONF:
        return _deny_confidence(fields, path)

    # Unknown path: mild prior by adjudication class
    if adj == "APPROVED":
        return 0.90
    if adj == "DENIED":
        return 0.85
    return 0.28
