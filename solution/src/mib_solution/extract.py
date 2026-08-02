"""PDF field recovery via page-type router + FIELD_MANUAL precedence.

Page roles: fee / registry / form / sponsor / finding (+ biometric / manual).
Conflicts resolve by FIELD_MANUAL order; fee prefers fee receipt, risk prefers
finding/form/biometric/registry, etc. No case-id answer tables.
"""

from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

from mib_solution.evidence import (
    FieldCandidate,
    PageEvidence,
    build_evidence_bundle,
    iter_pages_for_field,
    pick_candidate,
    strip_untrusted_lines,
    trusted_corpus,
)

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

# Closed vocabularies from public form/registry (not case-id tables).
KNOWN_HOME_WORLDS = [
    "Luyten-b",
    "Europa Station",
    "Titan Freeport",
    "Barnard-c",
    "Gliese-581g",
    "Mars Dome-7",
    "Kepler-186f",
    "Sirius Outpost",
    "Wolf-1061c",
    "Proxima-b",
    "Zeta Reticuli",
    "TRAPPIST-1e",
    "Eris Relay",
]

KNOWN_SPECIES = [
    "KAIJU_MICRO",
    "JOVIAN_GASFORM",
    "CENTAURI_SYNTH",
    "ARCTURIAN",
    "SIRIUS_AVIAN",
    "AQUARIAN_MANTIS",
    "LUNA_SECURID",
    "ANDROMEDAN",
    "VENUSIAN_MYCELIAL",
    "TRIANGULAN",
    "ALPHA_DRACONIAN",
    "ORION_GRAYS",
]

SPECIES_BLOCKLIST = {
    "OCR_FALLBACK",
    "MIB_EYES",
    "FORM_I",
    "DIP_WAIVER",
    "PAGE",
    "NEEDS_REVIEW",
    "REGISTRY_IMAGE",
    "PASSPORT_IMAGE",
    "SCAN_IMAGE",
    "PRIMARY_INTAKE",
    "MIB_FEE",
    "SPN",
    "APPROVED",
    "DENIED",
}

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
        r"(?:^|\n)\s*(?:Species Code|Species Match)\s*(?:\n|:)\s*"
        r"([A-Z][A-Z0-9_]{2,40})\b",
        re.IGNORECASE,
    ),
    "home_world": re.compile(
        r"(?:^|\n)\s*Home World\s*(?:\n|:)\s*"
        r"([A-Za-z0-9][A-Za-z0-9 .'-]{1,40})",
        re.IGNORECASE,
    ),
    "visa_class": re.compile(
        r"(?:^|\n)\s*Visa Class\s*(?:\n|:)\s*"
        r"(XW-1|XW-2|DIP-1|MED-3|TRANSIT-7)\b",
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
ATTEST_VISA_RE = re.compile(
    r"\bclass\s+(XW-1|XW-2|DIP-1|MED-3|TRANSIT-7)\b",
    re.IGNORECASE,
)

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

# OCR garbage often lands on markers / page chrome
GARBAGE_NAME_RE = re.compile(
    r"^(?:unknown|n/a|none|null|packet|page|form|mib|case|scan|registry|"
    r"applicant|sponsor|wane|name|cut\s*out|ocr|fallback)\b",
    re.I,
)


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract concatenated page text from a PDF (text layer only)."""
    return "\n".join(extract_pdf_pages(pdf_path))


def extract_pdf_pages(pdf_path: Path) -> list[str]:
    try:
        reader = PdfReader(str(pdf_path))
    except Exception:
        return []
    parts: list[str] = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        parts.append(text)
    return parts


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
        r"packet|manual|registry|observed|biometric|scan|finding|form|"
        r"passport|image|primary|intake)\b",
        raw,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" .,:;\n\t")
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"\b(?:PASSPORT|IMAGE|SCAN|REGISTRY)\b", "", cleaned, flags=re.I).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if (
        2 <= len(cleaned) <= 60
        and cleaned.casefold() not in {"unknown", "n/a", "none", "null"}
        and "[" not in cleaned
        and not GARBAGE_NAME_RE.search(cleaned)
        and not re.search(r"\d{3,}", cleaned)
        and not re.search(r"\b(?:image|passport|status|clear)\b", cleaned, re.I)
    ):
        # Prefer two-token alien names; still accept single token if long
        if " " in cleaned or len(cleaned) >= 5:
            return cleaned
    return None


def _normalize_purpose(raw: str) -> str | None:
    if not raw:
        return None
    text = re.sub(r"\s+", " ", raw).strip(" .,:;\n\t").casefold()
    if not text or "[" in text or "illegible" in text:
        return None
    text = re.split(
        r"\b(?:risk|fee|case|packet|manual|sample|waiver|finding)\b",
        text,
        maxsplit=1,
    )[0].strip(" .,:;")
    for known in KNOWN_PURPOSES:
        if text == known or text.startswith(known):
            return known
        if known.startswith(text) and len(text) >= 4:
            return known
        # OCR near-miss: xenchotany / xenabotany
        if _fuzzy_token(text.replace(" ", ""), known.replace(" ", ""), max_dist=1):
            return known
    if re.fullmatch(r"[a-z][a-z0-9 /-]{1,40}", text):
        return text
    return None


def _fuzzy_token(a: str, b: str, max_dist: int = 2) -> bool:
    """Simple Levenshtein with early exit; for short OCR fixes."""
    a, b = a.casefold(), b.casefold()
    if a == b:
        return True
    if abs(len(a) - len(b)) > max_dist:
        return False
    if len(a) < 4 or len(b) < 4:
        return False
    # classic DP truncated
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            ins = cur[j - 1] + 1
            delete = prev[j] + 1
            sub = prev[j - 1] + (0 if ca == cb else 1)
            cur.append(min(ins, delete, sub))
        prev = cur
        if min(prev) > max_dist:
            return False
    return prev[-1] <= max_dist


def _normalize_home_world(raw: str) -> str | None:
    if not raw:
        return None
    cleaned = re.split(
        r"\b(?:species|visa|sponsor|arrival|registry|case|packet|declared|"
        r"fee|risk|finding|form|scan|image)\b",
        raw,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" .,:;")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned or cleaned.casefold() in {"unknown", "n/a", "none"}:
        return None
    if re.search(r"\b(?:scan|tab|page|packet|status|clear|image|passport)\b", cleaned, re.I):
        return None
    # exact / casefold match
    for known in KNOWN_HOME_WORLDS:
        if cleaned.casefold() == known.casefold():
            return known
    # compact alnum compare for OCR: Woll-108 1c vs Wolf-1061c
    compact = re.sub(r"[^a-z0-9]", "", cleaned.casefold())
    if len(compact) < 4:
        return None
    best = None
    best_d = 99
    for known in KNOWN_HOME_WORLDS:
        kcomp = re.sub(r"[^a-z0-9]", "", known.casefold())
        if compact == kcomp:
            return known
        # prefix match for truncated OCR (Kepler vs Kepler-186f)
        if kcomp.startswith(compact) and len(compact) >= 5:
            return known
        if compact.startswith(kcomp) and len(kcomp) >= 5:
            return known
        if _fuzzy_token(compact, kcomp, max_dist=1):
            # track closest
            best = known
            best_d = 3
    if best is not None:
        return best
    # accept free text only if multi-token or hyphenated world-like
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9 .'-]{2,40}", cleaned) and (
        "-" in cleaned or " " in cleaned
    ):
        return cleaned
    return None


def _normalize_species(raw: str) -> str | None:
    if not raw:
        return None
    tok = raw.strip().upper().replace(" ", "_")
    tok = re.sub(r"[^A-Z0-9_]", "", tok)
    if not tok or tok in SPECIES_BLOCKLIST or tok.startswith("OCR"):
        return None
    for known in KNOWN_SPECIES:
        if tok == known:
            return known
        if known.startswith(tok) and len(tok) >= 5:
            return known
        if tok.startswith(known) and len(known) >= 5:
            return known
        if _fuzzy_token(tok, known, max_dist=1):
            return known
    # Allow species-like tokens with underscore segments
    if re.fullmatch(r"[A-Z]{3,}(?:_[A-Z0-9]+){0,4}", tok) and tok not in SPECIES_BLOCKLIST:
        if len(tok) >= 6 and "_" in tok:
            return tok
    return None


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


def _risk_from_status_text(status: str) -> list[str]:
    if not status:
        return []
    if status.casefold() in {"clear", "none", "n/a", "ok", "clean"}:
        return []
    found: list[str] = []
    for pat, token in REGISTRY_STATUS_MAP:
        if pat.search(status):
            found.append(token)
    return found


def _cand(
    field: str,
    value: str,
    page: PageEvidence,
    rank_boost: int = 0,
) -> FieldCandidate:
    return FieldCandidate(
        field=field,
        value=value,
        page_type=page.page_type,
        source=page.source,
        rank=page.rank + rank_boost,
        page_index=page.index,
    )


def _find_case_id(text: str, fallback_stem: str) -> str:
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


def _collect_applicant(pages: list[PageEvidence]) -> str:
    cands: list[FieldCandidate] = []
    for page in iter_pages_for_field("applicant_name", pages):
        text = strip_untrusted_lines(page.text)
        m = MANUAL_APPLICANT_RE.search(page.text)
        if m:
            cleaned = _clean_name(m.group(1))
            if cleaned:
                cands.append(_cand("applicant_name", cleaned, page, rank_boost=-1))
        for raw in _all_labels("applicant_name", text):
            cleaned = _clean_name(raw)
            if cleaned:
                cands.append(_cand("applicant_name", cleaned, page))
        if page.page_type == "sponsor" or "sponsor" in page.tags:
            m = ATTEST_NAME_RE.search(text)
            if m:
                cleaned = _clean_name(m.group(1))
                if cleaned:
                    cands.append(_cand("applicant_name", cleaned, page))
    return pick_candidate(cands) or "unknown"


def _collect_species(pages: list[PageEvidence]) -> str:
    cands: list[FieldCandidate] = []
    for page in iter_pages_for_field("species_code", pages):
        ptext = strip_untrusted_lines(page.text)
        for raw in _all_labels("species_code", ptext):
            norm = _normalize_species(raw)
            if norm:
                cands.append(_cand("species_code", norm, page))
        if page.page_type in {"form", "biometric", "registry", "other"}:
            upper = ptext.upper()
            for known in KNOWN_SPECIES:
                if known in upper:
                    cands.append(_cand("species_code", known, page, rank_boost=1))
                # OCR fragments near known codes
                for m in re.finditer(r"\b([A-Z]{4,}(?:_[A-Z0-9]+){0,4})\b", upper):
                    norm = _normalize_species(m.group(1))
                    if norm:
                        cands.append(_cand("species_code", norm, page, rank_boost=3))
    if cands:
        return pick_candidate(cands) or "unknown"
    # Trusted free-form fallback only (no decoy corpus).
    full = trusted_corpus(pages)
    for raw in _all_labels("species_code", full):
        norm = _normalize_species(raw)
        if norm:
            return norm
    upper = full.upper()
    for known in KNOWN_SPECIES:
        if known in upper:
            return known
    for m in re.finditer(r"\b([A-Z]{4,}(?:_[A-Z0-9]+){0,4})\b", upper):
        norm = _normalize_species(m.group(1))
        if norm:
            return norm
    return "unknown"


def _collect_home_world(pages: list[PageEvidence]) -> str:
    cands: list[FieldCandidate] = []
    for page in iter_pages_for_field("home_world", pages):
        ptext = strip_untrusted_lines(page.text)
        for raw in _all_labels("home_world", ptext):
            norm = _normalize_home_world(raw)
            if norm:
                cands.append(_cand("home_world", norm, page))
        if page.page_type in {"form", "registry", "other"}:
            for known in KNOWN_HOME_WORLDS:
                if known.casefold() in ptext.casefold():
                    cands.append(_cand("home_world", known, page, rank_boost=1))
    hit = pick_candidate(cands)
    if hit:
        return hit
    full = trusted_corpus(pages)
    for raw in _all_labels("home_world", full):
        norm = _normalize_home_world(raw)
        if norm:
            return norm
    for known in KNOWN_HOME_WORLDS:
        if known.casefold() in full.casefold():
            return known
    for m in re.finditer(r"([A-Za-z][A-Za-z0-9 .'-]{2,30})", full):
        norm = _normalize_home_world(m.group(1))
        if norm and norm in KNOWN_HOME_WORLDS:
            return norm
    return "unknown"


def _collect_visa(pages: list[PageEvidence]) -> str:
    cands: list[FieldCandidate] = []
    for page in iter_pages_for_field("visa_class", pages):
        ptext = strip_untrusted_lines(page.text)
        labeled = _label("visa_class", ptext)
        if labeled and labeled.upper() in VISA_VALUES:
            cands.append(_cand("visa_class", labeled.upper(), page))
        if page.page_type == "sponsor":
            m = ATTEST_VISA_RE.search(ptext)
            if m:
                cands.append(_cand("visa_class", m.group(1).upper(), page))
        if page.page_type in {"form", "sponsor"}:
            m = VISA_RE.search(ptext)
            if m:
                cands.append(_cand("visa_class", m.group(1).upper(), page, rank_boost=2))
        elif page.page_type not in {"decoy", "empty", "fee"}:
            m = VISA_RE.search(ptext)
            if m:
                cands.append(_cand("visa_class", m.group(1).upper(), page, rank_boost=4))
    if cands:
        return pick_candidate(cands) or "unknown"
    full = trusted_corpus(pages)
    labeled = _label("visa_class", full)
    if labeled and labeled.upper() in VISA_VALUES:
        return labeled.upper()
    m = ATTEST_VISA_RE.search(full)
    if m:
        return m.group(1).upper()
    m = VISA_RE.search(full)
    if m:
        return m.group(1).upper()
    return "unknown"


def _collect_sponsor(pages: list[PageEvidence]) -> str:
    cands: list[FieldCandidate] = []
    for page in iter_pages_for_field("sponsor_id", pages):
        ptext = strip_untrusted_lines(page.text)
        m = MANUAL_SPONSOR_RE.search(page.text)
        if m:
            cands.append(_cand("sponsor_id", m.group(1).upper(), page, rank_boost=-1))
        labeled = _label("sponsor_id", ptext)
        if labeled:
            cands.append(_cand("sponsor_id", labeled.upper(), page))
        if page.page_type in {"sponsor", "form"} or "sponsor" in page.tags:
            m = ATTEST_SPONSOR_RE.search(ptext)
            if m:
                cands.append(_cand("sponsor_id", m.group(1).upper(), page))
        # free SPN on non-decoy pages (OCR often drops labels)
        if page.page_type not in {"decoy", "empty", "fee"}:
            m = SPONSOR_RE.search(ptext)
            if m:
                boost = 0 if page.page_type in {"form", "sponsor", "manual"} else 3
                cands.append(_cand("sponsor_id", f"SPN-{m.group(1)}", page, rank_boost=boost))
    if cands:
        return pick_candidate(cands) or "SPN-0000"
    full = trusted_corpus(pages)
    labeled = _label("sponsor_id", full)
    if labeled:
        return labeled.upper()
    m = MANUAL_SPONSOR_RE.search(full)
    if m:
        return m.group(1).upper()
    m = ATTEST_SPONSOR_RE.search(full)
    if m:
        return m.group(1).upper()
    m = SPONSOR_RE.search(full)
    if m:
        return f"SPN-{m.group(1)}"
    return "SPN-0000"


def _plausible_date(d: str) -> bool:
    """Prefer challenge-era arrival dates; OCR often flips 6→8/0."""
    if not d or not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", d):
        return False
    year = int(d[:4])
    return 2024 <= year <= 2027


def _collect_date(pages: list[PageEvidence]) -> str:
    cands: list[FieldCandidate] = []
    for page in iter_pages_for_field("arrival_date", pages):
        ptext = strip_untrusted_lines(page.text)
        labeled = _label("arrival_date", ptext)
        if labeled and _plausible_date(labeled):
            cands.append(_cand("arrival_date", labeled, page))
        elif labeled:
            cands.append(_cand("arrival_date", labeled, page, rank_boost=5))
        if page.page_type in {"form", "registry"}:
            for m in DATE_RE.finditer(ptext):
                d = m.group(1)
                boost = 2 if _plausible_date(d) else 8
                cands.append(_cand("arrival_date", d, page, rank_boost=boost))
    if cands:
        # Prefer plausible years among top ranks
        cands_sorted = sorted(
            cands,
            key=lambda c: (
                0 if _plausible_date(c.value) else 1,
                c.rank,
                0 if c.source == "text" else 1,
                c.page_index,
            ),
        )
        return cands_sorted[0].value
    full = trusted_corpus(pages)
    dates = DATE_RE.findall(full)
    for d in dates:
        if _plausible_date(d):
            return d
    if dates:
        return dates[0]
    return "1900-01-01"


def _collect_purpose(pages: list[PageEvidence]) -> str:
    cands: list[FieldCandidate] = []
    for page in iter_pages_for_field("declared_purpose", pages):
        # Finding notes mention "Transit class..." — not declared purpose
        if page.page_type == "finding":
            continue
        ptext = strip_untrusted_lines(page.text)
        labeled = _label("declared_purpose", ptext)
        if labeled:
            norm = _normalize_purpose(labeled)
            if norm:
                cands.append(_cand("declared_purpose", norm, page))
        if page.page_type == "sponsor":
            m = re.search(
                r"expected\s+on\s+Earth\s+for\s+(.+?)(?:\.|\n\s*The\s+sponsor|\n\n)",
                ptext,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if m:
                chunk = re.sub(r"\s+", " ", m.group(1)).strip()
                norm = _normalize_purpose(chunk)
                if norm:
                    cands.append(_cand("declared_purpose", norm, page))
        low = ptext.casefold()
        if page.page_type in {"form", "sponsor"}:
            for known in KNOWN_PURPOSES:
                if known in low:
                    cands.append(_cand("declared_purpose", known, page, rank_boost=2))
    hit = pick_candidate(cands)
    if hit:
        return hit
    # Trusted pages except finding notes (often say "Transit class...").
    chunks = []
    for page in pages:
        if page.page_type in {"finding", "decoy", "empty"}:
            continue
        chunks.append(strip_untrusted_lines(page.text) or "")
    full = "\n".join(chunks).casefold()
    for known in KNOWN_PURPOSES:
        if known in full:
            return known
    return "unknown"


def _collect_fee(pages: list[PageEvidence]) -> str:
    cands: list[FieldCandidate] = []
    waiver_cands: list[FieldCandidate] = []
    for page in iter_pages_for_field("fee_status", pages):
        ptext = strip_untrusted_lines(page.text)
        labeled = _label("fee_status", ptext)
        if labeled and labeled.casefold() in FEE_VALUES:
            boost = -1 if page.page_type == "fee" else 0
            cands.append(_cand("fee_status", labeled.casefold(), page, rank_boost=boost))
        waiver = _label("waiver_code", ptext)
        if waiver:
            waiver_cands.append(
                _cand("waiver_code", waiver, page, rank_boost=-1 if page.page_type == "fee" else 0)
            )
        # any page with fee language
        if page.page_type == "fee" or re.search(r"fee\s+status|waiver\s+code|fee\s+receipt", ptext, re.I):
            m = re.search(r"\b(paid|waived|unpaid|unknown)\b", ptext, re.I)
            if m:
                cands.append(_cand("fee_status", m.group(1).casefold(), page, rank_boost=1))

    waiver_val = pick_candidate(waiver_cands)
    if waiver_val and waiver_val.upper() not in {"N/A", "NA", "NONE", "-", "NULL", "UNKNOWN"}:
        if re.search(r"WAIVER|HARDSHIP|DIP", waiver_val, re.I):
            return "waived"

    if cands:
        return pick_candidate(cands) or "unknown"

    full = trusted_corpus(pages)
    m = re.search(r"\bFee Status\s*(?:\n|:)\s*(paid|waived|unpaid|unknown)\b", full, re.I)
    if m:
        return m.group(1).casefold()
    m = re.search(r"\bWaiver Code\s*(?:\n|:)\s*([A-Za-z0-9_/-]+)", full, re.I)
    if m and m.group(1).upper() not in {"N/A", "NA", "NONE", "-", "NULL", "UNKNOWN"}:
        if re.search(r"WAIVER|HARDSHIP|DIP", m.group(1), re.I):
            return "waived"
    # Prefer labeled fee pages only for bare paid/waived/unpaid (not decoy free text)
    for page in pages:
        if page.page_type not in {"fee", "form", "finding"}:
            continue
        ptext = strip_untrusted_lines(page.text)
        m = re.search(r"\b(paid|waived|unpaid)\b", ptext, re.I)
        if m:
            return m.group(1).casefold()
    return "unknown"


def _collect_risk(pages: list[PageEvidence]) -> str:
    found: list[str] = []
    labeled_none = False

    for page in iter_pages_for_field("risk_flags", pages):
        ptext = strip_untrusted_lines(page.text)
        for hit in _all_labels("risk_flags", ptext):
            parsed = _parse_risk_blob(hit)
            if parsed == "none":
                labeled_none = True
            elif parsed:
                found.extend(parsed.split("|"))

        status = _label("registry_status", ptext)
        if status:
            found.extend(_risk_from_status_text(status))

        if page.page_type == "finding":
            low = ptext.casefold()
            for token in RISK_FLAG_TOKENS:
                if token in low or token.replace("_", " ") in low:
                    found.append(token)

        if page.page_type in {"registry", "finding", "form", "biometric"}:
            if re.search(r"\bEMBARGO\s+REVIEW\b", ptext, re.I):
                found.append("planetary_embargo")
            if re.search(r"\bACTIVE\s+WARRANT\b", ptext, re.I):
                found.append("active_warrant")

    # Trusted free-form scan only (OCR stamps on finding/form/registry pages).
    full = trusted_corpus(pages)
    low = full.casefold()
    for token in RISK_FLAG_TOKENS:
        if token in low or token.replace("_", " ") in low:
            found.append(token)
    if re.search(r"\bEMBARGO\s+REVIEW\b", full, re.I):
        found.append("planetary_embargo")
    if re.search(r"\bACTIVE\s+WARRANT\b", full, re.I):
        found.append("active_warrant")

    if not found:
        return "none" if not labeled_none else "none"
    return "|".join(sorted(set(found)))


def extract_fields(pdf_path: Path, text: str | None = None) -> dict:
    """Recover applicant fields using page-type routing + FIELD_MANUAL precedence."""
    text_pages = extract_pdf_pages(pdf_path)
    if text is None:
        text = "\n".join(text_pages)

    pages = build_evidence_bundle(text_pages, merged_text=text)
    # Full merged stream for case_id / length; trusted stream for policy.
    full_text = text if text else trusted_corpus(pages)
    trusted = trusted_corpus(pages)

    return {
        "case_id": _find_case_id(full_text, pdf_path.stem),
        "applicant_name": _collect_applicant(pages),
        "species_code": _collect_species(pages),
        "home_world": _collect_home_world(pages),
        "visa_class": _collect_visa(pages),
        "sponsor_id": _collect_sponsor(pages),
        "arrival_date": _collect_date(pages),
        "declared_purpose": _collect_purpose(pages),
        "risk_flags": _collect_risk(pages),
        "fee_status": _collect_fee(pages),
        "_text": full_text,
        "_trusted_text": trusted,
        "_text_len": len(trusted or full_text or ""),
        "_page_types": [f"{p.source}:{p.page_type}" for p in pages],
    }
