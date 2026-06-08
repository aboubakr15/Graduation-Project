"""
lecture_cleaner.py
------------------
Data-cleaning pipeline for lecture and section documents
before chunking. Plug into DocumentProcessor by calling
`clean_documents(docs)` after loading and before splitting.
"""

import re
import logging
from typing import List
from langchain_core.documents import Document

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


# ------------------------------------------------------------------ #
# Regex patterns                                                       #
# ------------------------------------------------------------------ #

# Repeated header / footer patterns common in Arabic university slides
_HEADER_FOOTER_PATTERNS = [
    # Page numbers: "Page 3", "3 / 10", "- 3 -", "صفحة 3"
    r"(?mi)^[\-–—]?\s*(page|صفحة|ص)\s*\d+\s*[\-–—]?\s*$",
    r"(?mi)^\d+\s*/\s*\d+\s*$",
    r"(?mi)^-\s*\d+\s*-\s*$",

    # Slide number lines: "Slide 5", "شريحة 5"
    r"(?mi)^(slide|شريحة)\s*\d+\s*$",

    # Repeated course / university headers (adjust to your institution)
    r"(?mi)^(faculty of|كلية|جامعة|university of)[^\n]{0,80}$",

    # "Prepared by Dr. …" repeated on every page
    r"(?mi)^(prepared by|إعداد|د\.|prof\.|أ\.د\.)[^\n]{0,80}$",

    # Copyright / academic year footers
    r"(?mi)^(©|copyright|حقوق|all rights)[^\n]{0,80}$",
    r"(?mi)^\d{4}\s*[-–]\s*\d{4}\s*$",          # "2023-2024"
    r"(?mi)^(academic year|العام الدراسي)[^\n]{0,60}$",
]

# Placeholder text injected for non-textual content
_TABLE_PLACEHOLDER  = "\n[TABLE]\n"
_IMAGE_PLACEHOLDER  = "\n[IMAGE]\n"
_FORMULA_PLACEHOLDER = "\n[FORMULA]\n"

# Patterns that look like extracted table artefacts (pypdf / fitz dumps)
_TABLE_ARTEFACT = re.compile(
    r"(\|.*\|[\r\n]+){2,}",        # markdown-style rows
    re.MULTILINE,
)

# Inline LaTeX / equation markers that survived extraction
_FORMULA_PATTERNS = [
    re.compile(r"\$\$.*?\$\$", re.DOTALL),   # $$…$$
    re.compile(r"\$[^\$\n]{1,120}\$"),         # $…$
    re.compile(r"\\begin\{.*?\\end\{[a-z*]+\}", re.DOTALL),  # LaTeX env
]

# Excessive whitespace
_MULTI_BLANK = re.compile(r"\n{3,}")
_TRAILING_SPACES = re.compile(r"[ \t]+$", re.MULTILINE)
_LEADING_SPACES  = re.compile(r"^[ \t]+", re.MULTILINE)

# Arabic-specific: Tatweel (ـ) used for decorative stretching
_TATWEEL = re.compile(r"ـ{2,}")

# OCR artefacts that fitz sometimes leaves behind
_OCR_ARTEFACTS = re.compile(r"[□■▪▫●•]{3,}")


# ------------------------------------------------------------------ #
# Core cleaning helpers                                               #
# ------------------------------------------------------------------ #

def _remove_headers_footers(text: str) -> str:
    for pattern in _HEADER_FOOTER_PATTERNS:
        text = re.sub(pattern, "", text)
    return text


def _replace_tables(text: str) -> str:
    return _TABLE_ARTEFACT.sub(_TABLE_PLACEHOLDER, text)


def _replace_formulas(text: str) -> str:
    for pat in _FORMULA_PATTERNS:
        text = pat.sub(_FORMULA_PLACEHOLDER, text)
    return text


def _clean_whitespace(text: str) -> str:
    text = _TRAILING_SPACES.sub("", text)
    text = _LEADING_SPACES.sub("", text)
    text = _MULTI_BLANK.sub("\n\n", text)
    return text.strip()


def _clean_arabic_artefacts(text: str) -> str:
    text = _TATWEEL.sub("", text)          # remove decorative tatweel
    text = _OCR_ARTEFACTS.sub("", text)    # remove OCR box symbols
    # Normalise Arabic smart quotes to straight
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    return text


def _normalize_structure(text: str) -> str:
    """
    Convert common slide bullet styles to consistent markers so the
    RecursiveCharacterTextSplitter can treat them as split boundaries.

    Converts: *, -, •, ○, ‣, ✓, ✗, →, ◆  →  a single "-"
    """
    text = re.sub(r"(?m)^[•○‣✓✗→◆►▶]\s+", "- ", text)
    # Normalise numbered list  "1)" / "١." → "1."
    text = re.sub(r"(?m)^(\d+)[)\.\-]\s+", r"\1. ", text)
    # Arabic-Indic digits  ١٢٣  → 123
    arabic_indic = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
    text = text.translate(arabic_indic)
    return text


def _tag_content_type(doc: Document) -> None:
    """
    Detect whether a page looks like a slide (short, many bullets)
    vs a text-heavy lecture note, and record it in metadata so
    downstream retrieval can filter.
    """
    text = doc.page_content
    line_count  = text.count("\n")
    word_count  = len(text.split())
    bullet_count = len(re.findall(r"(?m)^- ", text))

    if word_count < 80 and bullet_count >= 3:
        doc.metadata.setdefault("content_type", "slide_bullets")
    elif word_count > 300:
        doc.metadata.setdefault("content_type", "lecture_text")
    else:
        doc.metadata.setdefault("content_type", "mixed")


def _detect_lecture_number(doc: Document) -> None:
    """
    Try to extract a lecture / section number from the first 200 chars
    and store it in metadata for better retrieval grouping.
    """
    snippet = doc.page_content[:200]
    match = re.search(
        r"(?:lecture|محاضرة|section|سكشن|week|أسبوع)\s*[:\-]?\s*(\d+)",
        snippet,
        re.IGNORECASE,
    )
    if match:
        doc.metadata.setdefault("lecture_number", match.group(1))


# ------------------------------------------------------------------ #
# Public API                                                          #
# ------------------------------------------------------------------ #

def clean_document(doc: Document) -> Document:
    """Apply the full cleaning pipeline to a single Document."""
    text = doc.page_content

    text = _remove_headers_footers(text)
    text = _replace_tables(text)
    text = _replace_formulas(text)
    text = _clean_arabic_artefacts(text)
    text = _normalize_structure(text)
    text = _clean_whitespace(text)

    doc.page_content = text

    # Enrich metadata
    _tag_content_type(doc)
    _detect_lecture_number(doc)

    return doc


def clean_documents(documents: List[Document]) -> List[Document]:
    """
    Clean a list of Documents in-place and filter out empty pages.

    Usage inside DocumentProcessor.process_documents:

        documents = self.load_document(path)
        documents = clean_documents(documents)       # <-- add this line
        return self.split_documents(documents)
    """
    cleaned: List[Document] = []
    skipped = 0

    for doc in documents:
        cleaned_doc = clean_document(doc)
        if len(cleaned_doc.page_content.strip()) < 20:   # skip near-empty pages
            skipped += 1
            continue
        cleaned.append(cleaned_doc)

    logger.info(
        f"Cleaning complete: {len(cleaned)} pages kept, {skipped} empty pages skipped."
    )
    return cleaned