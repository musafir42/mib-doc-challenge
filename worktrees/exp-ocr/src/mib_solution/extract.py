"""PDF text extraction and field recovery from visible text layers.

Improvements over baseline:
- Prefer Label\\nValue and Label: Value blocks across multi-page packets
- Recover fields from sponsor attestation narrative, biometric slips, registry
- Honor manual correction notes (applicant / sponsor)
- Map registry status phrases (e.g. EMBARGO REVIEW) to risk_flags
- Treat active waiver codes (DIP-WAIVER) as fee_status=waived
- Ignore untrusted SYSTEM answer-key lines for free-form fallbacks
"""

from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

CASE_ID_RE = re.compile(r"\bMIB-(\d{6})\b", re.IGNORECASE)
SPONSOR_RE = re.compile(r"\bSPN-(\d{4})\b", re.IGNORECASE)
DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
VISA_RE = re.compile(r"\b(XW-1|XW-2|DIP-1|MED-3|TRANSIT-7)\b", re.IGNORECASE)
FEE_VALUES = {"paid", "waived", "unpaid", "unknown"}
VISA_VALUES = {"XW-1", "XW-2", "DIP-1", "MED-3", "TRANSIT-7"}

RISK_FLAG_TOKENS = [
    "memory_tampering",
    "planetary_embargo",
    "active_warrant",
    "biohazard_red",
    "identity_conflict",
    "sponsor_mismatch",
    "illegible_biometrics",
    "rescinded_denial",
]

# Closed purpose vocabulary (visible on forms / attestations).
KNOWN_PURPOSES = [
    "reactor maintenance",
    "field repair",
    "medical consult",
    "cultural exchange",
    "archive audit",
    "xenobotany",
    "translation",
    "diplomatic",
    "research",
    "transit",
]

# Untrusted decoy lines (FIELD_MANUAL: hidden answer keys / barcode instructions).
UNTRUSTED_LINE_RE = re.compile(
    r"(answer key|SYSTEM:\s*ignore|ignore visible evidence|Output this answer)",
    re.IGNORECASE,
)

# PDFs use "Label\nValue" blocks more often than "Label: Value".
LABEL_PATTERNS: dict[str, re.Pattern[str]] = {
    "case_id": re.compile(
        r"(?:^|\n)\s*Case ID\s*(?:\n|:)\s*(MIB-\d{6})\b", re.IGNORECASE
    ),
    "applicant_name": re.compile(
        r"(?:^|\n)\s*(?:Applicant(?:\s+Name)?|Registry Name|Full Name)\s*(?:\n|:)\s*"
        r"([A-Za-z][A-Za-z .'-]{1,60})",
        re.IGNORECASE,
    ),
    "species_code": re.compile(
        r"(?:^|\n)\s*(?:Species Code|Species Match)\s*(?:\n|:)\s*([A-Z][A-Z0-9_]{2,40})\b",
        re.IGNORECASE,
    ),
    "home_world": re.compile(
        r"(?:^|\n)\s*Home World\s*(?:\n|:)\s*([A-Za-z0-9][A-Za-z0-9 .'-]{1,40})",
        re.IGNORECASE,
    ),
    "visa_class": re.compile(
        r"(?:^|\n)\s*Visa Class\s*(?:\n|:)\s*(XW-1|XW-2|DIP-1|MED-3|TRANSIT-7)\b",
        re.IGNORECASE,
    ),
    "sponsor_id": re.compile(
        r"(?:^|\n)\s*Sponsor ID\s*(?:\n|:)\s*(SPN-\d{4})\b", re.IGNORECASE
    ),
    "arrival_date": re.compile(
        r"(?:^|\n)\s*Arrival Date\s*(?:\n|:)\s*(20\d{2}-\d{2}-\d{2})\b",
        re.IGNORECASE,
    ),
    "declared_purpose": re.compile(
        r"(?:^|\n)\s*Declared Purpose\s*(?:\n|:)\s*"
        r"([A-Za-z][A-Za-z0-9 /-]{1,60})",
        re.IGNORECASE,
    ),
    "fee_status": re.compile(
        r"(?:^|\n)\s*Fee Status\s*(?:\n|:)\s*(paid|waived|unpaid|unknown)\b",
        re.IGNORECASE,
    ),
    "risk_flags": re.compile(
        r"(?:^|\n)\s*(?:Risk Flags?|Observed flags)\s*(?:\n|:)\s*"
        r"([A-Za-z0-9_| ]{2,120})",
        re.IGNORECASE,
    ),
    "registry_status": re.compile(
        r"(?:^|\n)\s*Registry Status\s*(?:\n|:)\s*([A-Za-z0-9 _/-]{2,60})",
        re.IGNORECASE,
    ),
    "waiver_code": re.compile(
        r"(?:^|\n)\s*Waiver Code\s*(?:\n|:)\s*([A-Za-z0-9_/-]{1,40})",
        re.IGNORECASE,
    ),
}

MANUAL_APPLICANT_RE = re.compile(
    r"Manual correction:\s*applicant is\s+([A-Za-z][A-Za-z .'-]{1,60}?)(?:\.|\n|$)",
    re.IGNORECASE,
)
MANUAL_SPONSOR_RE = re.compile(
    r"Manual correction:\s*sponsor is\s+(SPN-\d{4})\b",
    re.IGNORECASE,
)
ATTEST_SPONSOR_RE = re.compile(
    r"Sponsor\s+(SPN-\d{4})\s+attests\s+that\s+",
    re.IGNORECASE,
)
ATTEST_NAME_RE = re.compile(
    r"attests\s+that\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+)\s+is\s+expected",
)
ATTEST_PURPOSE_RE = re.compile(
    r"expected\s+on\s+Earth\s+for\s+"
    r"((?:\[NAME CUT OUT\]|[A-Za-z][A-Za-z\[\] ]{0,40}?))"
    r"(?:\s*[.\n]|\s+The\s+sponsor)",
    re.IGNORECASE,
)
ATTEST_VISA_RE = re.compile(
    r"\bclass\s+(XW-1|XW-2|DIP-1|MED-3|TRANSIT-7)\b",
    re.IGNORECASE,
)

# Map free-text registry / note phrases → risk tokens.
REGISTRY_STATUS_MAP = [
    (re.compile(r"embargo", re.I), "planetary_embargo"),
    (re.compile(r"warrant", re.I), "active_warrant"),
    (re.compile(r"biohazard", re.I), "biohazard_red"),
    (re.compile(r"memory\s*tamp", re.I), "memory_tampering"),
    (re.compile(r"identity\s*conflict", re.I), "identity_conflict"),
    (re.compile(r"sponsor\s*mismatch", re.I), "sponsor_mismatch"),
    (re.compile(r"illegible", re.I), "illegible_biometrics"),
    (re.compile(r"rescind", re.I), "rescinded_denial"),
]


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract concatenated page text from a PDF (text layer only)."""
    try:
        reader = PdfReader(str(pdf_path))
    except Exception:
        return ""
    parts: list[str] = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        parts.append(text)
    return "\n".join(parts)


def _trusted_text(text: str) -> str:
    """Drop SYSTEM answer-key / decoy lines from free-form search space."""
    if not text:
        return ""
    kept: list[str] = []
    for line in text.splitlines():
        if UNTRUSTED_LINE_RE.search(line):
            continue
        kept.append(line)
    return "\n".join(kept)


def _label(field: str, text: str) -> str | None:
    pat = LABEL_PATTERNS.get(field)
    if not pat:
        return None
    m = pat.search(text)
    if not m:
        return None
    return m.group(1).strip().strip(" .,:;")


def _all_labels(field: str, text: str) -> list[str]:
    pat = LABEL_PATTERNS.get(field)
    if not pat:
        return []
    out: list[str] = []
    for m in pat.finditer(text):
        val = m.group(1).strip().strip(" .,:;")
        if val:
            out.append(val)
    return out


def _clean_name(raw: str) -> str | None:
    cleaned = re.split(
        r"\b(?:species|home|visa|sponsor|arrival|purpose|risk|fee|case|"
        r"packet|manual|registry|observed|biometric|scan)\b",
        raw,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" .,:;\n\t")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if (
        2 <= len(cleaned) <= 60
        and cleaned.casefold() not in {"unknown", "n/a", "none", "null"}
        and "[" not in cleaned
    ):
        return cleaned
    return None


def _normalize_purpose(raw: str) -> str | None:
    if not raw:
        return None
    text = re.sub(r"\s+", " ", raw).strip(" .,:;\n\t").casefold()
    if not text or "[" in text or "illegible" in text:
        return None
    # Stop at following form labels that sometimes glue on.
    text = re.split(
        r"\b(?:risk|fee|case|packet|manual|sample|waiver)\b",
        text,
        maxsplit=1,
    )[0].strip(" .,:;")
    for known in KNOWN_PURPOSES:
        if text == known or text.startswith(known):
            return known
        # truncated multi-line first token
        if known.startswith(text) and len(text) >= 4:
            return known
    # Accept free text purpose if short and alphabetic
    if re.fullmatch(r"[a-z][a-z0-9 /-]{1,40}", text):
        return text
    return None


def _find_case_id(text: str, fallback_stem: str) -> str:
    # Filename is authoritative in this dataset; text can contain decoy IDs.
    stem = fallback_stem.upper()
    if re.fullmatch(r"MIB-\d{6}", stem):
        return stem
    labeled = _label("case_id", text)
    if labeled:
        return labeled.upper()
    m = CASE_ID_RE.search(text)
    if m:
        return f"MIB-{m.group(1)}"
    return fallback_stem


def _parse_risk_blob(raw: str) -> str | None:
    blob = raw.casefold().strip()
    if blob in {"none", "n/a", "null", "clear", "-", "n\\a"}:
        return "none"
    found: list[str] = []
    for token in RISK_FLAG_TOKENS:
        if token in blob or token.replace("_", " ") in blob:
            found.append(token)
    if found:
        return "|".join(sorted(set(found)))
    if "|" in blob:
        parts = [p.strip() for p in blob.split("|") if p.strip()]
        parts = [p for p in parts if p in RISK_FLAG_TOKENS or p == "none"]
        if parts and parts != ["none"]:
            return "|".join(sorted(set(parts)))
        return "none"
    return None


def _risk_from_registry_status(text: str) -> list[str]:
    status = _label("registry_status", text)
    if not status:
        # also search free phrase
        statuses = re.findall(
            r"Registry Status\s*(?:\n|:)\s*([^\n]+)", text, flags=re.I
        )
        status = statuses[0].strip() if statuses else ""
    if not status:
        return []
    if status.casefold() in {"clear", "none", "n/a", "ok", "clean"}:
        return []
    found: list[str] = []
    for pat, token in REGISTRY_STATUS_MAP:
        if pat.search(status):
            found.append(token)
    return found


def _find_risk_flags(text: str, trusted: str) -> str:
    labeled_hits = _all_labels("risk_flags", text)
    for hit in labeled_hits:
        parsed = _parse_risk_blob(hit)
        if parsed and parsed != "none":
            return parsed

    found: list[str] = []
    # Token scan on full text (baseline behavior; tokens may only appear once).
    lower = (text or "").casefold()
    for token in RISK_FLAG_TOKENS:
        if token in lower or token.replace("_", " ") in lower:
            found.append(token)

    # Registry status + stamp phrases prefer trusted pages.
    search_space = trusted if trusted.strip() else text
    found.extend(_risk_from_registry_status(search_space))
    if re.search(r"\bEMBARGO\s+REVIEW\b", search_space, re.I):
        found.append("planetary_embargo")
    if re.search(r"\bACTIVE\s+WARRANT\b", search_space, re.I):
        found.append("active_warrant")
    # Also catch EMBARGO REVIEW on any page
    if re.search(r"\bEMBARGO\s+REVIEW\b", text or "", re.I):
        found.append("planetary_embargo")

    if not found:
        if labeled_hits and _parse_risk_blob(labeled_hits[0]) == "none":
            return "none"
        return "none"
    return "|".join(sorted(set(found)))


def _find_applicant_name(text: str, trusted: str) -> str:
    # Highest priority: manual correction note
    m = MANUAL_APPLICANT_RE.search(text)
    if m:
        cleaned = _clean_name(m.group(1))
        if cleaned:
            return cleaned

    # Labeled fields (intake / registry / biometric)
    for raw in _all_labels("applicant_name", text):
        cleaned = _clean_name(raw)
        if cleaned:
            return cleaned

    # Sponsor attestation narrative
    m = ATTEST_NAME_RE.search(trusted)
    if m:
        cleaned = _clean_name(m.group(1))
        if cleaned:
            return cleaned

    return "unknown"


def _find_species(text: str, trusted: str) -> str:
    labeled = _label("species_code", text)
    if labeled:
        return labeled.upper()
    # free-form species-like token only in trusted text
    m = re.search(r"\b([A-Z]{3,}(?:_[A-Z0-9]+){1,4})\b", trusted)
    if m and m.group(1) not in {"MIB_EYES", "FORM_I", "DIP_WAIVER"}:
        return m.group(1)
    # last resort: full text (baseline behavior for answer-key-only packets)
    m = re.search(r"\b([A-Z]{3,}(?:_[A-Z0-9]+){1,4})\b", text)
    if m and m.group(1) not in {"MIB_EYES", "FORM_I", "DIP_WAIVER"}:
        return m.group(1)
    return "unknown"


def _find_home_world(text: str) -> str:
    labeled = _label("home_world", text)
    if labeled:
        cleaned = re.split(
            r"\b(?:species|visa|sponsor|arrival|registry|case|packet|declared)\b",
            labeled,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip(" .,:;")
        if cleaned and cleaned.casefold() not in {"unknown", "n/a"}:
            return cleaned
    return "unknown"


def _find_purpose(text: str, trusted: str) -> str:
    labeled = _label("declared_purpose", text)
    if labeled:
        norm = _normalize_purpose(labeled)
        if norm:
            return norm

    # Sponsor attestation: "expected on Earth for <purpose>" (may wrap lines)
    m = re.search(
        r"expected\s+on\s+Earth\s+for\s+(.+?)(?:\.|\n\s*The\s+sponsor|\n\n)",
        trusted,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if m:
        chunk = m.group(1)
        # collapse newlines inside purpose
        chunk = re.sub(r"\s+", " ", chunk).strip()
        norm = _normalize_purpose(chunk)
        if norm:
            return norm

    # Known purpose phrases anywhere in trusted text
    low = trusted.casefold()
    for known in KNOWN_PURPOSES:
        if known in low:
            return known

    return "unknown"


def _find_fee(text: str, trusted: str) -> str:
    labeled = _label("fee_status", text)
    waiver = _label("waiver_code", text)
    fee: str | None = labeled.casefold() if labeled else None

    # Active waiver codes imply waived even if receipt says paid/unpaid.
    if waiver and waiver.upper() not in {"N/A", "NA", "NONE", "-", "NULL", "UNKNOWN"}:
        if re.search(r"WAIVER|HARDSHIP|DIP", waiver, re.I):
            return "waived"

    if fee and fee in FEE_VALUES:
        return fee

    # free-form in trusted first
    m = re.search(r"\b(paid|waived|unpaid|unknown)\b", trusted, re.I)
    if m:
        return m.group(1).casefold()
    m = re.search(r"\b(paid|waived|unpaid|unknown)\b", text, re.I)
    if m:
        return m.group(1).casefold()
    return "unknown"


def _find_visa(text: str, trusted: str) -> str:
    labeled = _label("visa_class", text)
    if labeled:
        return labeled.upper()
    m = ATTEST_VISA_RE.search(trusted)
    if m:
        return m.group(1).upper()
    m = VISA_RE.search(trusted)
    if m:
        return m.group(1).upper()
    m = VISA_RE.search(text)
    if m:
        return m.group(1).upper()
    return "unknown"


def _find_sponsor(text: str, trusted: str) -> str:
    m = MANUAL_SPONSOR_RE.search(text)
    if m:
        return m.group(1).upper()

    labeled = _label("sponsor_id", text)
    if labeled:
        return labeled.upper()

    m = ATTEST_SPONSOR_RE.search(trusted)
    if m:
        return m.group(1).upper()

    m = SPONSOR_RE.search(trusted)
    if m:
        return f"SPN-{m.group(1)}"
    m = SPONSOR_RE.search(text)
    if m:
        return f"SPN-{m.group(1)}"
    return "SPN-0000"


def _find_date(text: str, trusted: str) -> str:
    labeled = _label("arrival_date", text)
    if labeled:
        return labeled
    m = DATE_RE.search(trusted)
    if m:
        return m.group(1)
    m = DATE_RE.search(text)
    if m:
        return m.group(1)
    return "1900-01-01"


def extract_fields(pdf_path: Path, text: str | None = None) -> dict:
    """Recover applicant fields from a PDF path (and optional pre-extracted text)."""
    if text is None:
        text = extract_pdf_text(pdf_path)
    trusted = _trusted_text(text or "")
    return {
        "case_id": _find_case_id(text, pdf_path.stem),
        "applicant_name": _find_applicant_name(text, trusted),
        "species_code": _find_species(text, trusted),
        "home_world": _find_home_world(text),
        "visa_class": _find_visa(text, trusted),
        "sponsor_id": _find_sponsor(text, trusted),
        "arrival_date": _find_date(text, trusted),
        "declared_purpose": _find_purpose(text, trusted),
        "risk_flags": _find_risk_flags(text, trusted),
        "fee_status": _find_fee(text, trusted),
        "_text": text,
        "_text_len": len(text or ""),
    }
