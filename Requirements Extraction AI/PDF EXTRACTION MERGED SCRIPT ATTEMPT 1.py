import os
import json
import re
from pathlib import Path
from typing import Dict, Any

# For PDF summarization
import PyPDF2
from transformers import pipeline

# ============================================================
#                    DATE PATTERN (MONTH + YEAR)
# ============================================================

MONTH_WORDS = (
    "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|"
    "January|February|March|April|May|June|July|August|September|October|November|December|"
    "JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC|"
    "JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER"
)

DATE_PATTERN = re.compile(
    rf"(\b\d{{1,2}}\s+(?:{MONTH_WORDS})\s+\d{{4}}\b|\b(?:{MONTH_WORDS})\s+\d{{4}}\b)"
)

NAVADMIN_DATE_2DIGIT = re.compile(
    r"\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+\d{2}\b"
)

# ============================================================
#                CLASSIFICATION LINE FILTER
# ============================================================

def is_classification_line(line: str) -> bool:
    u = line.upper()
    return (
        u.startswith("CLASSIFICATION")
        or u.startswith("UNCLASSIFIED")
        or u.startswith("CONFIDENTIAL")
        or u.startswith("SECRET")
    )

# ============================================================
#      MULTI-LINE NTSP / TRAINING PLAN TITLES ("FOR THE")
# ============================================================

NTSP_ID_INLINE_PATTERN = re.compile(r"N\d{2}-NTSP-[A-Z0-9\-]+/[A-Z]", re.I)
A_CODE_INLINE_PATTERN = re.compile(r"A-\d{2}-\d{4}[A-Z]?/[A-Z]", re.I)

def extract_multiline_title_with_for_the(lines):
    idx = None
    for i, line in enumerate(lines):
        if "FOR THE" in line.upper():
            idx = i
            break

    if idx is None:
        return None

    window = []
    start = max(0, idx - 2)
    end = min(len(lines), idx + 3)

    for j in range(start, end):
        l = lines[j].strip()
        if not l:
            continue

        u = l.upper()

        if u.startswith("[PAGE"):
            continue
        if NTSP_ID_INLINE_PATTERN.search(u) or A_CODE_INLINE_PATTERN.search(u):
            continue

        if any(c.isalpha() for c in l) and u == u.upper() and len(l) > 3:
            window.append(l)

    if window:
        return " ".join(window)

    return None

# ============================================================
#                  NAVADMIN DETECTION
# ============================================================

NAVADMIN_PATTERN = re.compile(r"NAVADMIN\s+\d+/\d{2}", re.I)

def extract_navadmin(text: str, file_name: str):
    first_page = text.split("[PAGE 2]", 1)[0]
    raw_lines = [l.strip() for l in first_page.splitlines() if l.strip()]

    m = NAVADMIN_PATTERN.search(first_page)
    if not m:
        return None

    doc_number = m.group(0)
    doc_type = "NAVADMIN"

    title = None
    subj_idx = None
    for i, l in enumerate(raw_lines):
        if l.upper().startswith("SUBJ/"):
            subj_idx = i
            break

    if subj_idx is not None:
        parts = []
        parts.append(raw_lines[subj_idx].split("/", 1)[1].strip(" /"))

        for j in range(subj_idx + 1, min(subj_idx + 5, len(raw_lines))):
            nxt = raw_lines[j].strip()
            up = nxt.upper()
            if not nxt:
                break
            if up.startswith(("REF/", "RMKS/", "MSGID/")):
                break
            if is_classification_line(nxt):
                continue
            parts.append(nxt.strip(" /"))

        title = " ".join(parts) if parts else None

    publication_date = None
    two_d = NAVADMIN_DATE_2DIGIT.search(first_page)
    if two_d:
        publication_date = two_d.group(0)
    else:
        dm = DATE_PATTERN.search(first_page)
        if dm:
            publication_date = dm.group(1)

    return {
        "doc_id": file_name.replace(".txt", ""),
        "doc_type": doc_type,
        "doc_number": doc_number,
        "title": title,
        "publication_date": publication_date,
    }

# ============================================================
#    OPNAVINST / SECNAVINST / NTSP (SECOND PRIORITY)
# ============================================================

NAVY_DOC_PATTERNS = [
    ("SECNAVINST", r"SECNAVINST\s+[\d\.A-Z/]+"),
    ("OPNAVINST", r"OPNAVINST\s+[\d\.A-Z/]+"),
    ("NTSP", r"NTSP\s+[A-Z0-9\-]+"),
]

def extract_navy_instruction(text: str, file_name: str):
    first_page = text.split("[PAGE 2]", 1)[0]
    raw_lines = [l.strip() for l in first_page.splitlines() if l.strip()]
    lines = [l for l in raw_lines if not is_classification_line(l)]

    doc_type = None
    doc_number = None

    for dtype, pattern in NAVY_DOC_PATTERNS:
        m = re.search(pattern, first_page)
        if m:
            doc_type = dtype
            doc_number = m.group(0)
            break

    if not doc_number:
        return None

    title = None
    subj_line = next((l for l in lines if l.upper().startswith("SUBJ:")), None)
    if subj_line:
        title = subj_line.split(":", 1)[1].strip()

    if not title:
        title = extract_multiline_title_with_for_the(lines)

    if not title:
        caps = [l for l in lines if l.isupper() and len(l) > 5 and doc_number not in l]
        if caps:
            title = caps[0]

    publication_date = None
    dm = DATE_PATTERN.search(first_page)
    if dm:
        publication_date = dm.group(1)

    return {
        "doc_id": file_name.replace(".txt", ""),
        "doc_type": doc_type,
        "doc_number": doc_number,
        "title": title,
        "publication_date": publication_date,
    }

# ============================================================
#           TECH MANUALS / NTSP TRAINING DOCS
# ============================================================

NTSP_ID_PATTERN = re.compile(r"\bN\d{2}-NTSP-[A-Z0-9\-]+/[A-Z]\b", re.I)
A_CODE_PATTERN = re.compile(r"\bA-\d{2}-\d{4}[A-Z]?/[A-Z]\b", re.I)

TECH_DOC_PATTERNS = [
    ("AIM", r"AIM[-\s]?\d+[A-Z]?"),
    ("NAVAIR", r"NAVAIR\s+[\dA-Z\-]+"),
    ("TECH_MANUAL", r"(TECHNICAL\s+MANUAL|TECH\s+MANUAL|TM\s+\d[\d\-A-Z]+)"),
]

def extract_technical_manual(text: str, file_name: str):
    first_page = text.split("[PAGE 2]", 1)[0]
    raw_lines = [l.strip() for l in first_page.splitlines() if l.strip()]
    lines = [l for l in raw_lines if not is_classification_line(l)]

    doc_type = None
    doc_number = None

    ntsp_match = NTSP_ID_PATTERN.search(first_page)
    if ntsp_match:
        doc_number = ntsp_match.group(0)
        doc_type = "NTSP"
    else:
        a_match = A_CODE_PATTERN.search(first_page)
        if a_match:
            doc_number = a_match.group(0)
            doc_type = "NTSP"
        else:
            for dtype, pattern in TECH_DOC_PATTERNS:
                m = re.search(pattern, first_page, re.I)
                if m:
                    doc_type = dtype
                    doc_number = m.group(0).strip()
                    break

    if not doc_number:
        return None

    title = extract_multiline_title_with_for_the(lines)

    if not title:
        caps = [l for l in lines if l.isupper() and len(l) > 5]
        if caps:
            title = " ".join(caps[:2])

    publication_date = None
    dm = DATE_PATTERN.search(first_page)
    if dm:
        publication_date = dm.group(1)

    doc_id = doc_number

    return {
        "doc_id": doc_id,
        "doc_type": doc_type,
        "doc_number": doc_number,
        "title": title,
        "publication_date": publication_date,
    }

# ============================================================
#                   GENERIC FALLBACK
# ============================================================

def extract_generic(text: str, file_name: str):
    first_page = text.split("[PAGE 2]", 1)[0]
    raw = [l.strip() for l in first_page.splitlines() if l.strip()]
    lines = [l for l in raw if not is_classification_line(l)]

    title = extract_multiline_title_with_for_the(lines)

    if not title:
        for l in lines:
            if any(c.isalpha() for c in l) and len(l) > 5:
                title = l
                break

    publication_date = None
    dm = DATE_PATTERN.search(first_page)
    if dm:
        publication_date = dm.group(1)
    else:
        year_m = re.search(r"(19|20)\d{2}", first_page)
        if year_m:
            publication_date = year_m.group(0)

    return {
        "doc_id": file_name.replace(".txt", ""),
        "doc_type": "UNKNOWN",
        "doc_number": None,
        "title": title,
        "publication_date": publication_date,
    }

# ============================================================
#              MASTER DISPATCHER
# ============================================================

def extract_metadata_from_text(text: str, file_name: str) -> Dict[str, Any]:
    navadmin = extract_navadmin(text, file_name)
    if navadmin:
        return navadmin

    navy = extract_navy_instruction(text, file_name)
    if navy:
        return navy

    tech = extract_technical_manual(text, file_name)
    if tech:
        return tech

    return extract_generic(text, file_name)

# ============================================================
#           SIMPLE TXT SUMMARIZATION (extractive)
# ============================================================

from collections import Counter

def summarize_text(text: str, max_sentences: int = 3) -> str:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    lines = [l for l in lines if not is_classification_line(l)]
    cleaned = " ".join(lines)

    sentences = re.split(r'(?<=[\.\!\?])\s+', cleaned)
    sentences = [s.strip() for s in sentences if len(s.split()) > 3]

    if not sentences:
        return ""

    words = re.findall(r"\b[A-Za-z]{3,}\b", cleaned.lower())
    freq = Counter(words)
    maxf = max(freq.values()) if freq else 1
    for k in freq:
        freq[k] /= maxf

    scores = {}
    for s in sentences:
        s_words = re.findall(r"[A-Za-z]{3,}", s.lower())
        if s_words:
            scores[s] = sum(freq[w] for w in s_words) / len(s_words)

    ranked = sorted(scores, key=scores.get, reverse=True)[:max_sentences]
    ranked = sorted(ranked, key=lambda s: sentences.index(s))
    return " ".join(ranked)

# ============================================================
#                TXT BATCH DRIVER
# ============================================================

def batch_extract_metadata(parsed_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    for txt_file in parsed_dir.glob("*.txt"):
        text = txt_file.read_text(encoding="utf-8")

        meta = extract_metadata_from_text(text, txt_file.name)

        meta_path = output_dir / (txt_file.stem + "_metadata.json")
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        summary = summarize_text(text)
        summary_path = output_dir / (txt_file.stem + "_summary.txt")
        summary_path.write_text(summary, encoding="utf-8")

        print(f"Processed TXT: {txt_file.name}")

# ============================================================
#            PDF METADATA + SUMMARIZATION
# ============================================================

def extract_pdf_metadata(pdf_path):
    metadata_info = {}
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        metadata = reader.metadata

        if metadata:
            for key, value in metadata.items():
                clean_key = key.lstrip("/")
                metadata_info[clean_key] = str(value)
    return metadata_info

def extract_text_from_pdf(pdf_path):
    text = ""
    with open(pdf_path, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        for page in reader.pages:
            text += (page.extract_text() or "") + "\n"
    return text

def chunk_text(text, max_chars=2000):
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end])
        start = end
    return chunks

def summarize_pdf_text(text, summarizer):
    parts = chunk_text(text)
    results = []
    for p in parts:
        if p.strip():
            r = summarizer(p, max_length=130, min_length=40, do_sample=False)
            results.append(r[0]["summary_text"])
    return "\n\n".join(results)

def summarize_pdfs_in_folder(pdf_dir: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

    for file in pdf_dir.glob("*.pdf"):
        print(f"Processing PDF: {file.name}")

        # Extract metadata
        meta = extract_pdf_metadata(file)
        meta_path = output_dir / (file.stem + "_pdf_metadata.json")
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        # Extract text
        text = extract_text_from_pdf(file)

        # Summarize
        summary = summarize_pdf_text(text, summarizer)
        summary_path = output_dir / (file.stem + "_pdf_summary.txt")
        summary_path.write_text(summary, encoding="utf-8")

# ============================================================
#                      MAIN EXECUTION
# ============================================================

if __name__ == "__main__":
    parsed_txt_dir = Path("parsed_text")
    metadata_out_dir = Path("metadata")

    pdf_dir = Path("pdfs")
    pdf_out_dir = Path("pdf_metadata")

    batch_extract_metadata(parsed_txt_dir, metadata_out_dir)
    summarize_pdfs_in_folder(pdf_dir, pdf_out_dir)

    print("All TXT + PDF processing completed.")

