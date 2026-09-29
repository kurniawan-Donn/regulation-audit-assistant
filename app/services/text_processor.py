"""
Text Processor Service.

- extract_txt_text: baca file .txt mentah.
- clean_text: rapikan whitespace + strip nomor halaman + skip DAFTAR ISI.

Perubahan Fase A:
- Strip baris nomor halaman "- 39 -".
- Skip blok "DAFTAR ISI" (dari judul sampai entri terakhir).
- Normalisasi non-breaking space (\xa0 -> spasi biasa).
- Preserve marker "@@PAGE_N@@" dan "@@H1/H2/H3@@".
"""

import os
import re

_ENCODINGS_TO_TRY = ["utf-8", "utf-8-sig", "latin-1"]

# Baris nomor halaman: "- 39 -", "– 39 –", "-39-", dsb.
_PAGE_NUMBER_LINE = re.compile(r"^\s*[-–]\s*\d+\s*[-–]\s*$")

# Judul daftar isi
_TOC_HEADER = re.compile(r"^\s*(DAFTAR\s+ISI|TABLE\s+OF\s+CONTENTS)\s*$", re.IGNORECASE)

# Baris entry daftar isi: teks + nomor halaman di akhir.
# Contoh: "I. TATA KELOLA TI BPR DAN BPR SYARIAH 3"
#         "V. PENGGUNAAN PPJTI DALAM PENYELENGGARAAN TI BPR DAN 8"
_TOC_ENTRY = re.compile(r"^.{1,200}\s+\d{1,3}\s*$")

# Marker — jangan di-strip oleh cleaning
_MARKER_PAGE = re.compile(r"^@@PAGE_(\d+)@@$")
_MARKER_HEADING = re.compile(r"^(@@H[123]@@)\s+(.*)$")


class TextExtractionError(Exception):
    """Raised ketika file TXT tidak dapat dibaca atau kosong."""


def extract_txt_text(file_path: str) -> str:
    """Baca file TXT dengan berbagai fallback encoding."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File TXT tidak ditemukan: {file_path}")

    last_error: Exception | None = None
    content: str | None = None

    for encoding in _ENCODINGS_TO_TRY:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                content = f.read()
            break
        except UnicodeDecodeError as exc:
            last_error = exc
            content = None
            continue

    if content is None:
        raise TextExtractionError(
            f"Gagal membaca file TXT dengan encoding yang didukung "
            f"({', '.join(_ENCODINGS_TO_TRY)}): {last_error}"
        )

    if not content.strip():
        raise TextExtractionError("File TXT kosong atau tidak memiliki konten.")

    return content


def _strip_page_numbers(lines: list[str]) -> list[str]:
    """Buang baris yang isinya cuma nomor halaman (- 39 -)."""
    return [l for l in lines if not _PAGE_NUMBER_LINE.match(l)]


def _skip_toc_block(lines: list[str]) -> list[str]:
    """
    Deteksi blok DAFTAR ISI dan skip sampai entri terakhir.

    Alur:
    1. Cari baris cocok _TOC_HEADER.
    2. Setelah itu, skip baris berturut-turut yang cocok _TOC_ENTRY
       (toleransi 1 baris kosong antar entry).
    3. Berhenti di baris pertama yang BUKAN entry (mis. konten aktual).
    """
    out: list[str] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        if not _TOC_HEADER.match(line):
            out.append(line)
            i += 1
            continue

        # Ketemu header DAFTAR ISI — mulai skip
        i += 1  # skip header itu sendiri
        entry_count = 0

        while i < n:
            candidate = lines[i]
            if not candidate.strip():
                # Baris kosong, look-ahead 1 baris
                if i + 1 < n and _TOC_ENTRY.match(lines[i + 1]):
                    i += 1
                    continue
                break
            if _TOC_ENTRY.match(candidate):
                entry_count += 1
                i += 1
                continue
            break

        # Kalau < 3 entry, kemungkinan bukan TOC sebenarnya — kembalikan
        # semua yang di-skip (defensive).
        # Untuk kesederhanaan, kita asumsikan kalau header "DAFTAR ISI" ketemu,
        # blok berikutnya memang TOC. Skip saja.

    return out


def clean_text(raw_text: str) -> str:
    """
    Rapikan teks hasil ekstraksi.

    Operasi:
    - Normalisasi non-breaking space.
    - Form feed (page break PDF) -> newline.
    - Spasi/tab berlebih dirapikan.
    - Baris kosong berlebih dirapikan.
    - Strip nomor halaman.
    - Skip blok DAFTAR ISI.
    - Preserve marker "@@PAGE_N@@" dan "@@H1/H2/H3@@".
    """
    if not raw_text:
        return ""

    text = raw_text.replace("\xa0", " ")     # non-breaking space
    text = text.replace("\x0c", "\n")         # form feed -> newline
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    lines = [line.strip() for line in text.split("\n")]

    # Strip nomor halaman dulu
    lines = _strip_page_numbers(lines)

    # Skip DAFTAR ISI
    lines = _skip_toc_block(lines)

    # Rapikan ulang baris kosong setelah filter
    joined = "\n".join(lines)
    joined = re.sub(r"\n{3,}", "\n\n", joined)

    return joined.strip()