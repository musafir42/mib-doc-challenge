"""PDF text extraction and field recovery from visible text layers."""

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
        r"(?:^|\n)\s*Species Code\s*(?:\n|:)\s*([A-Z][A-Z0-9_]{2,40})\b",
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
        r"(?:^|\n)\s*Declared Purpose\s*(?:\n|:)\s*([A-Za-z][A-Za-z0-9 /-]{1,60})",
        re.IGNORECASE,
    ),
    "fee_status": re.compile(
        r"(?:^|\n)\s*Fee Status\s*(?:\n|:)\s*(paid|waived|unpaid|unknown)\b",
        re.IGNORECASE,
    ),
    "risk_flags": re.compile(
        r"(?:^|\n)\s*Risk Flags?\s*(?:\n|:)\s*([A-Za-z0-9_| ]{2,120})",
        re.IGNORECASE,
    ),
}


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


def _label(field: str, text: str) -> str | None:
    pat = LABEL_PATTERNS.get(field)
    if not pat:
        return None
    m = pat.search(text)
    if not m:
        return None
    return m.group(1).strip().strip(" .,:;")


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


def _find_risk_flags(text: str) -> str:
    labeled = _label("risk_flags", text)
    if labeled:
        raw = labeled.casefold().strip()
        if raw in {"none", "n/a", "null", "clear", "-"}:
            return "none"
        # Keep known tokens only if free text
        found = []
        for token in RISK_FLAG_TOKENS:
            if token in raw or token.replace("_", " ") in raw:
                found.append(token)
        if found:
            return "|".join(sorted(set(found)))
        # pipe-delimited already
        if "|" in raw:
            parts = [p.strip() for p in raw.split("|") if p.strip()]
            parts = [p for p in parts if p in RISK_FLAG_TOKENS or p == "none"]
            if parts and parts != ["none"]:
                return "|".join(sorted(set(parts)))
            return "none"

    lower = text.casefold()
    found = [token for token in RISK_FLAG_TOKENS if token in lower or token.replace("_", " ") in lower]
    if not found:
        return "none"
    return "|".join(sorted(set(found)))


def _find_applicant_name(text: str) -> str:
    labeled = _label("applicant_name", text)
    if labeled:
        cleaned = re.split(
            r"\b(?:species|home|visa|sponsor|arrival|purpose|risk|fee|case)\b",
            labeled,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip(" .,:;\n\t")
        if 2 <= len(cleaned) <= 60 and cleaned.casefold() not in {"unknown", "n/a"}:
            return cleaned
    return "unknown"


def _find_species(text: str) -> str:
    labeled = _label("species_code", text)
    if labeled:
        return labeled.upper()
    m = re.search(r"\b([A-Z]{3,}(?:_[A-Z0-9]+){1,4})\b", text)
    if m and m.group(1) not in {"MIB_EYES", "FORM_I"}:
        return m.group(1)
    return "unknown"


def _find_home_world(text: str) -> str:
    labeled = _label("home_world", text)
    if labeled:
        return labeled
    return "unknown"


def _find_purpose(text: str) -> str:
    labeled = _label("declared_purpose", text)
    if labeled:
        return labeled.casefold()
    return "unknown"


def _find_fee(text: str) -> str:
    labeled = _label("fee_status", text)
    if labeled and labeled.casefold() in FEE_VALUES:
        return labeled.casefold()
    m = re.search(r"\b(paid|waived|unpaid|unknown)\b", text, re.I)
    if m:
        return m.group(1).casefold()
    return "unknown"


def _find_visa(text: str) -> str:
    labeled = _label("visa_class", text)
    if labeled:
        return labeled.upper()
    m = VISA_RE.search(text)
    if m:
        return m.group(1).upper()
    return "unknown"


def _find_sponsor(text: str) -> str:
    labeled = _label("sponsor_id", text)
    if labeled:
        return labeled.upper()
    m = SPONSOR_RE.search(text)
    if m:
        return f"SPN-{m.group(1)}"
    return "SPN-0000"


def _find_date(text: str) -> str:
    labeled = _label("arrival_date", text)
    if labeled:
        return labeled
    m = DATE_RE.search(text)
    if m:
        return m.group(1)
    return "1900-01-01"


def extract_fields(pdf_path: Path, text: str | None = None) -> dict:
    """Recover applicant fields from a PDF path (and optional pre-extracted text)."""
    if text is None:
        text = extract_pdf_text(pdf_path)
    return {
        "case_id": _find_case_id(text, pdf_path.stem),
        "applicant_name": _find_applicant_name(text),
        "species_code": _find_species(text),
        "home_world": _find_home_world(text),
        "visa_class": _find_visa(text),
        "sponsor_id": _find_sponsor(text),
        "arrival_date": _find_date(text),
        "declared_purpose": _find_purpose(text),
        "risk_flags": _find_risk_flags(text),
        "fee_status": _find_fee(text),
        "_text": text,
        "_text_len": len(text or ""),
    }
