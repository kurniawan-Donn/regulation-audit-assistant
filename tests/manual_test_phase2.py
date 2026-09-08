"""
Manual test untuk Phase 2 - PDF/TXT extraction.

Ini BUKAN pytest formal (formal testing ada di Phase 9). Script ini
hanya untuk memverifikasi secara cepat bahwa fungsi ekstraksi
menghasilkan plain text yang benar dari dokumen sample.

Cara pakai:
    python tests/manual_test_phase2.py
"""

import os
import sys

# Agar bisa import "app.services..." saat dijalankan langsung dari root project.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.pdf_parser import extract_pdf_text
from app.services.text_processor import clean_text, extract_txt_text

BASE_DIR = os.path.dirname(__file__)
SAMPLE_TXT = os.path.join(BASE_DIR, "sample_files", "sample_regulation.txt")
SAMPLE_PDF = os.path.join(BASE_DIR, "sample_files", "sample_regulation.pdf")


def print_section(title: str) -> None:
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def test_txt_extraction() -> None:
    print_section("TEST 1: extract_txt_text()")
    raw = extract_txt_text(SAMPLE_TXT)
    print(f"Panjang teks mentah: {len(raw)} karakter")
    assert "Pasal 20" in raw, "Pasal 20 harus ditemukan di teks mentah"
    print("OK - Pasal 20 ditemukan di hasil ekstraksi TXT")

    cleaned = clean_text(raw)
    print(f"Panjang teks setelah clean_text: {len(cleaned)} karakter")
    assert "Pasal 20" in cleaned, "Pasal 20 harus tetap ada setelah cleaning"
    print("OK - Pasal 20 tetap ada setelah clean_text")
    print("\n--- Cuplikan hasil (300 karakter pertama) ---")
    print(cleaned[:300])


def test_pdf_extraction() -> None:
    print_section("TEST 2: extract_pdf_text()")
    if not os.path.exists(SAMPLE_PDF):
        print(
            f"[DILEWATI] {SAMPLE_PDF} belum ada. "
            f"Jalankan dulu: python tests/generate_sample_pdf.py"
        )
        return

    raw = extract_pdf_text(SAMPLE_PDF)
    print(f"Panjang teks mentah dari PDF: {len(raw)} karakter")
    assert "Pasal 21" in raw, "Pasal 21 harus ditemukan di teks hasil ekstraksi PDF"
    print("OK - Pasal 21 ditemukan di hasil ekstraksi PDF")

    cleaned = clean_text(raw)
    print("\n--- Cuplikan hasil (300 karakter pertama) ---")
    print(cleaned[:300])


def test_error_handling() -> None:
    print_section("TEST 3: Error handling (file tidak ada)")
    try:
        extract_txt_text("file_yang_tidak_ada.txt")
        print("GAGAL - seharusnya raise FileNotFoundError")
    except FileNotFoundError:
        print("OK - FileNotFoundError ter-raise dengan benar untuk TXT")

    try:
        extract_pdf_text("file_yang_tidak_ada.pdf")
        print("GAGAL - seharusnya raise FileNotFoundError")
    except FileNotFoundError:
        print("OK - FileNotFoundError ter-raise dengan benar untuk PDF")


if __name__ == "__main__":
    test_txt_extraction()
    test_pdf_extraction()
    test_error_handling()
    print_section("SEMUA TEST PHASE 2 SELESAI")
