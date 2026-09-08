"""
Regulation Structure Parser.

Mendeteksi struktur dokumen regulasi Indonesia (BAB, Bagian, Pasal,
Ayat, Huruf) menggunakan pendekatan berbasis regex per baris.

PRINSIP:
- Parser ini TIDAK HARUS SEMPURNA. Tujuannya hanya memastikan setiap
  potongan teks (chunk) tetap membawa konteks referensi (BAB berapa,
  Pasal berapa, Ayat berapa) sehingga tidak hilang saat dikirim ke AI.
- Parser tidak pernah mengubah isi teks asli. Teks disalin apa adanya
  ke dalam field "text" pada setiap chunk (hanya di-strip whitespace).
- Baris yang tidak cocok dengan pola BAB/Bagian/Pasal/Ayat dianggap
  sebagai konten biasa (termasuk butir Huruf a/b/c yang tetap
  dipertahankan sebagai bagian dari teks, bukan dipecah menjadi chunk
  tersendiri, agar konteksnya tidak hilang).
"""

import re
from typing import Optional, TypedDict

# BAB I, BAB II, BAB V, dst. (angka romawi)
_BAB_PATTERN = re.compile(r"^BAB\s+([IVXLCDM]+)\b", re.IGNORECASE)

# Bagian Kesatu, Bagian Kedua, dst.
_BAGIAN_PATTERN = re.compile(r"^Bagian\s+\S+", re.IGNORECASE)

# Pasal 1, Pasal 20, Pasal 20A, dst.
_PASAL_PATTERN = re.compile(r"^Pasal\s+(\d+[A-Za-z]?)\b", re.IGNORECASE)

# Menangkap dua gaya penulisan ayat:
#   "Ayat (1)"                -> marker di baris sendiri
#   "(1) Lembaga wajib ..."   -> marker diikuti isi di baris yang sama
_AYAT_PATTERN = re.compile(r"^(?:Ayat\s*)?\((\d+[a-zA-Z]?)\)\s*(.*)$", re.IGNORECASE)

# Butir huruf: "a. ...", "b. ...", dst. Hanya dipakai untuk mencatat
# huruf apa saja yang muncul dalam satu chunk, bukan untuk memecah chunk.
_HURUF_LINE_PATTERN = re.compile(r"^([a-z])\.\s+", re.MULTILINE)


class RegulationChunk(TypedDict):
    bab: Optional[str]
    bagian: Optional[str]
    pasal: Optional[str]
    ayat: Optional[str]
    huruf: list[str]
    text: str


def parse_regulation_structure(text: str) -> list[RegulationChunk]:
    """
    Memecah teks regulasi menjadi list of chunks berdasarkan struktur
    BAB/Bagian/Pasal/Ayat yang terdeteksi, sambil mempertahankan Huruf
    sebagai bagian dari teks.

    Args:
        text: Teks regulasi yang sudah dibersihkan (hasil clean_text()).

    Returns:
        List of dict dengan field: bab, bagian, pasal, ayat, huruf, text.
        Urutan chunk mengikuti urutan kemunculan dalam dokumen.
        Jika dokumen tidak memiliki struktur BAB/Pasal sama sekali,
        seluruh teks dikembalikan sebagai satu chunk dengan
        bab/bagian/pasal/ayat bernilai None.
    """
    current_bab: Optional[str] = None
    current_bagian: Optional[str] = None
    current_pasal: Optional[str] = None
    current_ayat: Optional[str] = None

    buffer: list[str] = []
    chunks: list[RegulationChunk] = []

    def flush() -> None:
        content = "\n".join(buffer).strip()
        buffer.clear()
        if not content:
            return
        chunks.append(
            RegulationChunk(
                bab=current_bab,
                bagian=current_bagian,
                pasal=current_pasal,
                ayat=current_ayat,
                huruf=_HURUF_LINE_PATTERN.findall(content),
                text=content,
            )
        )

    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue

        bab_match = _BAB_PATTERN.match(line)
        if bab_match:
            flush()
            current_bab = line
            current_bagian = None
            current_pasal = None
            current_ayat = None
            continue

        bagian_match = _BAGIAN_PATTERN.match(line)
        if bagian_match:
            flush()
            current_bagian = line
            current_pasal = None
            current_ayat = None
            continue

        pasal_match = _PASAL_PATTERN.match(line)
        if pasal_match:
            flush()
            current_pasal = line
            current_ayat = None
            continue

        ayat_match = _AYAT_PATTERN.match(line)
        if ayat_match:
            flush()
            current_ayat = f"({ayat_match.group(1)})"
            remainder = ayat_match.group(2).strip()
            if remainder:
                buffer.append(remainder)
            continue

        # Baris konten biasa, termasuk butir huruf (a., b., c., ...)
        buffer.append(line)

    flush()  # jangan lupa chunk terakhir

    return chunks
