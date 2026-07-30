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
RISK_FLAG_SET = set(RISK_FLAG_TOKENS)

# Prompt-injection style lines are not trusted evidence (FIELD_MANUAL).
INJECTION_LINE_RE = re.compile(
    r"^\s*SYSTEM\s*:.*$|ignore visible evidence|answer key only",
    re.IGNORECASE | re.MULTILINE,
)

# Trusted registry / biometric / adjudicator phrasing → risk tokens.
REGISTRY_STATUS_RE = re.compile(
    r"(?:^|\n)\s*Registry Status\s*(?:\n|:)\s*([^\n]+)",
    re.IGNORECASE,
)
OBSERVED_FLAGS_RE = re.compile(
    r"(?:^|\n)\s*Observed flags\s*(?:\n|:)\s*([^\n]+)",
    re.IGNORECASE,
)
DQ_FLAG_PHRASE_RE = re.compile(
    r"Disqualifying risk flag\s*:\s*([a-z_]+)",
    re.IGNORECASE,
)
EMBARGO_HOME_WORLD_RE = re.compile(r"\bEmbargo home world\b", re.IGNORECASE)
# Manual adjudicator stamp is highest-precedence trusted evidence.
ADJUDICATOR_FINDING_RE = re.compile(
    r"Finding\s*:\s*(DENIED|APPROVED|NEEDS_REVIEW|REVIEW)\b",
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
        r"(?:^|\n)\s*Risk Flags?\s*(?:\n|:)\s*([A-Za-z0-9_| ,]{2,120})",
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


def _trusted_text(text: str) -> str:
    """Drop prompt-injection / answer-key lines before signal search."""
    if not text:
        return ""
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        if INJECTION_LINE_RE.search(line):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def _label(field: str, text: str) -> str | None:
    pat = LABEL_PATTERNS.get(field)
    if not pat:
        return None
    m = pat.search(text)
    if not m:
        return None
    return m.group(1).strip().strip(" .,:;")


def _tokens_from_blob(raw: str) -> set[str]:
    """Parse known risk tokens from free text (pipe/comma/space separated)."""
    raw = (raw or "").casefold().strip()
    if raw in {"", "none", "n/a", "null", "clear", "-", "[risk panel missing]"}:
        return set()
    found: set[str] = set()
    for token in RISK_FLAG_TOKENS:
        if token in raw or token.replace("_", " ") in raw:
            found.add(token)
    # Explicit split forms: a|b or a, b
    for part in re.split(r"[|,;/]+", raw):
        p = part.strip().replace(" ", "_")
        if p in RISK_FLAG_SET:
            found.add(p)
    return found


def _registry_status_flags(text: str) -> set[str]:
    """Map Planetary Registry Status phrases to risk_flags tokens."""
    found: set[str] = set()
    for m in REGISTRY_STATUS_RE.finditer(text):
        val = re.sub(r"\s+", " ", m.group(1)).strip().casefold()
        # EMBARGO REVIEW (and close variants) → planetary_embargo
        if "embargo" in val:
            found.add("planetary_embargo")
        if "warrant" in val:
            found.add("active_warrant")
        if "biohazard" in val or re.search(r"\bred\b", val):
            found.add("biohazard_red")
        if "tamper" in val or "memory" in val:
            found.add("memory_tampering")
    return found


def _find_adjudicator_finding(text: str) -> str | None:
    """Return trusted Manual Adjudicator Finding class, if present."""
    m = ADJUDICATOR_FINDING_RE.search(text)
    if not m:
        return None
    val = m.group(1).upper()
    if val == "REVIEW":
        return "NEEDS_REVIEW"
    return val


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
    """Recover risk_flags from labels, registry status, biometric notes, phrases."""
    trusted = _trusted_text(text)
    found: set[str] = set()

    # 1) Explicit Risk Flags field
    labeled = _label("risk_flags", trusted)
    if labeled:
        found |= _tokens_from_blob(labeled)

    # 2) Biometric slip "Observed flags:" (comma-separated tokens)
    for m in OBSERVED_FLAGS_RE.finditer(trusted):
        found |= _tokens_from_blob(m.group(1))

    # 3) Adjudicator reason: "Disqualifying risk flag: planetary_embargo."
    for m in DQ_FLAG_PHRASE_RE.finditer(trusted):
        tok = m.group(1).casefold().strip()
        if tok in RISK_FLAG_SET:
            found.add(tok)

    # 4) Planetary Registry Status language (EMBARGO REVIEW, etc.)
    found |= _registry_status_flags(trusted)

    # 5) "Embargo home world: ..." reason text
    if EMBARGO_HOME_WORLD_RE.search(trusted):
        found.add("planetary_embargo")

    # 6) Free-token scan on trusted text only (ignore injection answer keys)
    lower = trusted.casefold()
    for token in RISK_FLAG_TOKENS:
        if token in lower or token.replace("_", " ") in lower:
            found.add(token)

    if not found:
        return "none"
    return "|".join(sorted(found))


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
    # Manual correction notes override form Sponsor ID when present.
    m_corr = re.search(
        r"Manual correction:\s*sponsor is\s*(SPN-\d{4})",
        text,
        re.IGNORECASE,
    )
    if m_corr:
        return m_corr.group(1).upper()
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
    trusted = _trusted_text(text)
    finding = _find_adjudicator_finding(trusted)
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
        "_adjudicator_finding": finding,
    }
