"""
Text Processor Service.

Berisi dua tanggung jawab terpisah:
1. extract_txt_text  -> membaca file .txt mentah menjadi string.
2. clean_text         -> merapikan string (whitespace, artifact),
                         TANPA mengubah isi/makna kalimat regulasi.
"""

import os
import re

# Encoding dicoba berurutan karena regulasi publik (POJK/SEOJK/PBI dll.)
# sering diunggah dalam encoding yang bervariasi.
_ENCODINGS_TO_TRY = ["utf-8", "utf-8-sig", "latin-1"]


class TextExtractionError(Exception):
    """Raised ketika file TXT tidak dapat dibaca atau kosong."""


def extract_txt_text(file_path: str) -> str:
    """
    Membaca isi file TXT dengan penanganan encoding yang aman.

    Args:
        file_path: Path menuju file TXT yang akan dibaca.

    Returns:
        String berisi seluruh isi file.

    Raises:
        FileNotFoundError: jika file tidak ditemukan.
        TextExtractionError: jika file kosong atau gagal dibaca
            dengan semua encoding yang dicoba.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File TXT tidak ditemukan: {file_path}")

    last_error: Exception | None = None

    for encoding in _ENCODINGS_TO_TRY:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                content = f.read()
            break
        except UnicodeDecodeError as exc:
            last_error = exc
            content = None
            continue
    else:
        raise TextExtractionError(
            f"Gagal membaca file TXT dengan encoding yang didukung "
            f"({', '.join(_ENCODINGS_TO_TRY)}): {last_error}"
        )

    if content is None or not content.strip():
        raise TextExtractionError("File TXT kosong atau tidak memiliki konten.")

    return content


def clean_text(raw_text: str) -> str:
    """
    Merapikan teks hasil ekstraksi (PDF maupun TXT).

    Operasi yang dilakukan (tidak mengubah makna, hanya kerapian):
    - Form feed (page break dari PDF) diubah menjadi newline.
    - Spasi/tab berlebih dirapikan menjadi satu spasi.
    - Baris kosong berlebih (3+ newline) dirapikan menjadi maksimal 1 baris kosong.
    - Setiap baris di-trim dari spasi di awal/akhir.

    Args:
        raw_text: Teks mentah hasil ekstraksi.

    Returns:
        Teks yang sudah dirapikan. Mengembalikan string kosong jika input kosong.
    """
    if not raw_text:
        return ""

    text = raw_text.replace("\x0c", "\n")  # form feed -> newline
    text = re.sub(r"[ \t]+", " ", text)  # rapikan spasi/tab berlebih
    text = re.sub(r"\n{3,}", "\n\n", text)  # rapikan baris kosong berlebih
    text = "\n".join(line.strip() for line in text.split("\n"))  # trim tiap baris

    return text.strip()
