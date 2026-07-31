"""Page-type routing and FIELD_MANUAL evidence precedence.

Page roles (goal set + biometric/manual/decoy for extraction):
  finding, form, biometric, sponsor, registry, fee, manual, decoy, empty, other

FIELD_MANUAL trusted evidence order (lower rank = preferred):
  1. adjudicator stamp / signed manual note (finding, manual correction)
  2. intake form fields
  3. biometric slip
  4. sponsor attestation
  5. registry extract
  6. fee receipt / free-form / machine-readable / OCR residual
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

# Ranks for conflict resolution (lower wins).
PAGE_RANK: dict[str, int] = {
    "finding": 1,
    "manual": 1,
    "form": 2,
    "biometric": 3,
    "sponsor": 4,
    "registry": 5,
    "fee": 5,
    "other": 6,
    "empty": 8,
    "decoy": 99,
}

# Field-specific preferred page types (ordered). Omitted types still considered
# via PAGE_RANK when present.
FIELD_PAGE_PREF: dict[str, tuple[str, ...]] = {
    "applicant_name": ("manual", "form", "biometric", "sponsor", "registry", "finding"),
    "species_code": ("form", "biometric", "registry"),
    "home_world": ("form", "registry"),
    "visa_class": ("form", "sponsor", "finding"),
    "sponsor_id": ("manual", "form", "sponsor"),
    "arrival_date": ("form", "registry", "finding"),
    "declared_purpose": ("form", "sponsor"),
    "fee_status": ("fee", "form", "finding"),
    "risk_flags": ("finding", "form", "biometric", "registry"),
    "waiver_code": ("fee", "form"),
    "registry_status": ("registry",),
}

UNTRUSTED_LINE_RE = re.compile(
    r"(answer key|SYSTEM:\s*ignore|ignore visible evidence|Output this answer)",
    re.IGNORECASE,
)
OCR_MARKER_RE = re.compile(r"^\s*---\s*(?:OCR_FALLBACK|PAGE\s+\d+)\s*---\s*$", re.I)
PAGE_SPLIT_RE = re.compile(r"(?m)^\s*---\s*PAGE\s+(\d+)\s*---\s*$")
OCR_SPLIT_RE = re.compile(r"\n\s*---\s*OCR_FALLBACK\s*---\s*\n", re.I)

# Document headers — order matters for multi-signal pages.
PAGE_CLASSIFIERS: list[tuple[str, re.Pattern[str]]] = [
    ("decoy", re.compile(r"answer key|SYSTEM:\s*ignore|Output this answer", re.I)),
    (
        "finding",
        re.compile(
            r"Manual Adjudicator Note|Finding:\s*(?:APPROVED|DENIED|NEEDS_REVIEW)\b",
            re.I,
        ),
    ),
    (
        "form",
        re.compile(
            r"FORM\s*I-?8090|Extraterrestrial Work Authorization Intake|Primary intake record",
            re.I,
        ),
    ),
    (
        "biometric",
        re.compile(r"FORM\s*B-?13|Biometric Scan Slip|Species Match\s*:", re.I),
    ),
    ("fee", re.compile(r"MIB Fee Receipt|\bFee Status\b|\bWaiver Code\b", re.I)),
    (
        "sponsor",
        re.compile(r"Sponsor Attestation Letter|attests that\s+", re.I),
    ),
    (
        "registry",
        re.compile(
            r"Planetary Registry Extract|\bRegistry Status\b|\bRegistry Name\b",
            re.I,
        ),
    ),
    ("manual", re.compile(r"Manual correction\s*:", re.I)),
]


@dataclass
class PageEvidence:
    """One classified page (text-layer or OCR)."""

    index: int
    source: str  # "text" | "ocr" | "merged"
    page_type: str
    text: str
    rank: int = 6
    tags: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.rank = PAGE_RANK.get(self.page_type, 6)
        if "manual" in self.tags and self.page_type != "manual":
            # Manual correction on a form page: keep form type but note manual tag.
            pass


@dataclass
class FieldCandidate:
    field: str
    value: str
    page_type: str
    source: str
    rank: int
    page_index: int = 0


def classify_page(text: str) -> tuple[str, set[str]]:
    """Return primary page_type and secondary tags."""
    raw = text or ""
    stripped = raw.strip()
    if len(stripped) < 30:
        return "empty", set()
    # Synthetic filler only
    if re.fullmatch(
        r"(?:Packet\s+MIB-\d{6}\s*/\s*page\s+\d+\s*Synthetic hiring challenge document\s*)+",
        stripped,
        flags=re.I,
    ):
        return "empty", set()

    tags: set[str] = set()
    primary: str | None = None
    for name, pat in PAGE_CLASSIFIERS:
        if pat.search(raw):
            if name == "manual":
                tags.add("manual")
                if primary is None:
                    primary = "manual"
                continue
            if name == "decoy":
                # decoy may coexist with real content; if *only* decoy-like, mark decoy
                if primary is None:
                    primary = "decoy"
                tags.add("decoy")
                continue
            if primary is None:
                primary = name
            tags.add(name)

    if primary is None:
        # short header-only synthetic
        if "Synthetic hiring challenge document" in raw and len(stripped) < 100:
            return "empty", tags
        return "other", tags
    return primary, tags


def strip_untrusted_lines(text: str) -> str:
    if not text:
        return ""
    kept: list[str] = []
    for line in text.splitlines():
        if UNTRUSTED_LINE_RE.search(line):
            continue
        if OCR_MARKER_RE.match(line):
            continue
        if re.search(r"\bOCR_FALLBACK\b", line, re.I) and "---" in line:
            continue
        kept.append(line)
    return "\n".join(kept)


def split_merged_text(text: str) -> tuple[str, str]:
    """Split pipeline merge into (text_layer, ocr_blob)."""
    if not text:
        return "", ""
    parts = OCR_SPLIT_RE.split(text, maxsplit=1)
    if len(parts) == 1:
        # Also allow marker without surrounding newlines
        if "--- OCR_FALLBACK ---" in text:
            i = text.index("--- OCR_FALLBACK ---")
            return text[:i], text[i + len("--- OCR_FALLBACK ---") :]
        return text, ""
    return parts[0], parts[1]


def split_ocr_pages(ocr_blob: str) -> list[str]:
    if not ocr_blob or not ocr_blob.strip():
        return []
    matches = list(PAGE_SPLIT_RE.finditer(ocr_blob))
    if not matches:
        return [ocr_blob.strip()] if ocr_blob.strip() else []
    pages: list[str] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(ocr_blob)
        chunk = ocr_blob[start:end].strip()
        if chunk:
            pages.append(chunk)
    return pages


def pages_from_pdf_reader(page_texts: Iterable[str], source: str = "text") -> list[PageEvidence]:
    out: list[PageEvidence] = []
    for i, raw in enumerate(page_texts):
        text = raw or ""
        ptype, tags = classify_page(text)
        # Decoy-only pages: if classifier said decoy and no other doc tag, keep decoy
        if "decoy" in tags and not (tags - {"decoy"}):
            ptype = "decoy"
        out.append(
            PageEvidence(
                index=i,
                source=source,
                page_type=ptype,
                text=text,
                tags=tags,
            )
        )
    return out


def build_evidence_bundle(
    text_pages: list[str],
    merged_text: str | None = None,
) -> list[PageEvidence]:
    """Combine text-layer pages with OCR pages from merged pipeline text."""
    pages = pages_from_pdf_reader(text_pages, source="text")
    if not merged_text:
        return pages
    _base, ocr_blob = split_merged_text(merged_text)
    ocr_pages = split_ocr_pages(ocr_blob)
    if ocr_pages:
        pages.extend(pages_from_pdf_reader(ocr_pages, source="ocr"))
    elif ocr_blob.strip():
        ptype, tags = classify_page(ocr_blob)
        pages.append(
            PageEvidence(
                index=len(pages),
                source="ocr",
                page_type=ptype,
                text=ocr_blob,
                tags=tags,
            )
        )
    return pages


def page_sort_key(field: str, page: PageEvidence) -> tuple[int, int, int]:
    """Lower is better. Prefer FIELD_PAGE_PREF, then PAGE_RANK, then text over ocr."""
    pref = FIELD_PAGE_PREF.get(field, ())
    if page.page_type in pref:
        pref_i = pref.index(page.page_type)
    elif "manual" in page.tags and field in {"applicant_name", "sponsor_id"}:
        pref_i = 0
    else:
        pref_i = 50 + page.rank
    source_pen = 0 if page.source == "text" else 1
    return (pref_i, source_pen, page.index)


def iter_pages_for_field(field: str, pages: list[PageEvidence]) -> list[PageEvidence]:
    """Pages ordered for a field, excluding pure decoy/empty unless nothing else."""
    usable = [
        p
        for p in pages
        if p.page_type not in {"decoy", "empty"} and len((p.text or "").strip()) >= 20
    ]
    if not usable:
        # image-only / answer-key-only packets: allow non-empty pages as last resort
        usable = [p for p in pages if len((p.text or "").strip()) >= 20]
    return sorted(usable, key=lambda p: page_sort_key(field, p))


def pick_candidate(cands: list[FieldCandidate]) -> str | None:
    if not cands:
        return None
    cands = sorted(cands, key=lambda c: (c.rank, 0 if c.source == "text" else 1, c.page_index))
    return cands[0].value


def trusted_corpus(pages: list[PageEvidence], include_ocr: bool = True) -> str:
    """Concat trusted page texts for free-form scans (no decoy, no pure empty)."""
    parts: list[str] = []
    for p in pages:
        if p.page_type in {"decoy", "empty"}:
            continue
        if not include_ocr and p.source == "ocr":
            continue
        cleaned = strip_untrusted_lines(p.text)
        if cleaned.strip():
            parts.append(cleaned)
    return "\n".join(parts)


def full_corpus(pages: list[PageEvidence]) -> str:
    return "\n".join(p.text for p in pages if p.text)
