"""
PDF Parser Service (revisi).

Output: teks dengan 2 jenis marker:
    @@PAGE_N@@     -> awal halaman
    @@H@@ <teks>   -> baris yang dianggap heading (bold dan/atau uppercase
                      dan/atau font lebih besar). KLASIFIKASI LEVEL
                      (BAB/Bagian/Pasal) DILAKUKAN DI regulation_parser.

Kenapa marker disederhanakan jadi satu jenis saja?
Karena PDF PADK memakai ukuran font yang tidak konsisten antara
"BAB I" dan "PENERAPAN TATA KELOLA TI". Deteksi level di sini rawan salah.
Lebih baik kirim sinyal "ini heading" apa adanya, biarkan regulation_parser
memutuskan.
"""

import os
import re
import statistics

import fitz  # PyMuPDF

PAGE_MARKER_PREFIX = "@@PAGE_"
PAGE_MARKER_SUFFIX = "@@"

_MAX_HEADING_LEN = 200


class PDFExtractionError(Exception):
    """Raised ketika file PDF tidak dapat dibaca atau tidak mengandung teks."""


def _is_bold(span: dict) -> bool:
    """Flag bit 4 (16) di PyMuPDF = bold."""
    return bool(span.get("flags", 0) & 16)


def _classify_line(span_list: list[dict], median_size: float) -> str:
    """
    Return "@@H@@ " kalau baris dianggap heading, atau "" kalau body.
    Kriteria (salah satu cukup):
      - Ukuran font >= median + 1.0
      - Bold dan panjang <= 200 char
      - Uppercase (semua alpha kapital) dan panjang <= 120 char
    """
    if not span_list:
        return ""

    text = "".join(s.get("text", "") for s in span_list).strip()
    if not text:
        return ""

    line_len = len(text)
    if line_len > _MAX_HEADING_LEN:
        return ""

    max_size = max(s.get("size", 0) for s in span_list)
    delta = max_size - median_size
    any_bold = any(_is_bold(s) for s in span_list)
    has_alpha = any(c.isalpha() for c in text)
    is_upper = has_alpha and text.isupper()

    # Kriteria 1: font jelas lebih besar
    if delta >= 1.5:
        return "@@H@@ "

    # Kriteria 2: bold dan pendek
    if any_bold and line_len <= _MAX_HEADING_LEN:
        return "@@H@@ "

    # Kriteria 3: uppercase dan pendek (untuk PDF yang tidak encode bold)
    if is_upper and line_len <= 120:
        return "@@H@@ "

    return ""


def _collect_lines(document: fitz.Document) -> list[dict]:
    """Iterasi seluruh halaman, ekstrak per-baris dengan metadata."""
    lines_out: list[dict] = []
    for page_num, page in enumerate(document, start=1):
        page_dict = page.get_text("dict")
        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                text = "".join(s.get("text", "") for s in spans).rstrip()
                if not text.strip():
                    continue
                lines_out.append({
                    "page": page_num,
                    "text": text,
                    "spans": spans,
                })
    return lines_out


def extract_pdf_text(file_path: str) -> str:
    """Ekstrak teks PDF + marker page + heading."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File PDF tidak ditemukan: {file_path}")

    try:
        document = fitz.open(file_path)
    except Exception as exc:
        raise PDFExtractionError(
            f"Gagal membuka file PDF. File mungkin rusak atau bukan PDF valid: {exc}"
        ) from exc

    try:
        if document.page_count == 0:
            raise PDFExtractionError("File PDF tidak memiliki halaman.")
        lines = _collect_lines(document)
    finally:
        document.close()

    joined = "\n".join(l["text"] for l in lines)
    if not joined.strip():
        raise PDFExtractionError(
            "Tidak ada teks yang dapat diekstrak dari PDF ini. "
            "Kemungkinan PDF berupa hasil scan (image-based) tanpa lapisan teks/OCR."
        )

    # Hitung median font size
    all_sizes: list[float] = []
    for l in lines:
        for s in l["spans"]:
            sz = s.get("size", 0)
            if sz > 0:
                all_sizes.append(sz)

    if not all_sizes:
        median_size = 0.0
    else:
        median_size = statistics.median(all_sizes)

    # Bangun output dengan marker
    out_lines: list[str] = []
    current_page = None
    for l in lines:
        if l["page"] != current_page:
            out_lines.append(f"{PAGE_MARKER_PREFIX}{l['page']}{PAGE_MARKER_SUFFIX}")
            current_page = l["page"]

        marker = _classify_line(l["spans"], median_size)
        out_lines.append(f"{marker}{l['text']}")

    return "\n".join(out_lines)