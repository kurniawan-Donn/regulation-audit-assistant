"""
Utility script (bukan bagian dari aplikasi utama) untuk membuat
tests/sample_files/sample_regulation.pdf dari sample_regulation.txt.

Dijalankan sekali saat development untuk menyediakan file PDF contoh
yang dipakai pada manual_test_phase2.py. Tidak dipanggil oleh aplikasi.

Cara pakai:
    python tests/generate_sample_pdf.py
"""

import os

import fitz  # PyMuPDF

BASE_DIR = os.path.dirname(__file__)
TXT_PATH = os.path.join(BASE_DIR, "sample_files", "sample_regulation.txt")
PDF_PATH = os.path.join(BASE_DIR, "sample_files", "sample_regulation.pdf")


def generate_sample_pdf() -> None:
    with open(TXT_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    doc = fitz.open()
    page_width, page_height = 595, 842  # ukuran A4 dalam points
    margin = 50
    font_size = 10
    line_height = font_size * 1.4
    max_lines_per_page = int((page_height - 2 * margin) / line_height)

    lines = content.split("\n")
    chunks = [
        lines[i : i + max_lines_per_page]
        for i in range(0, len(lines), max_lines_per_page)
    ]

    for chunk in chunks:
        page = doc.new_page(width=page_width, height=page_height)
        text_block = "\n".join(chunk)
        page.insert_textbox(
            fitz.Rect(margin, margin, page_width - margin, page_height - margin),
            text_block,
            fontsize=font_size,
            fontname="helv",
        )

    doc.save(PDF_PATH)
    doc.close()
    print(f"Sample PDF berhasil dibuat: {PDF_PATH}")


if __name__ == "__main__":
    generate_sample_pdf()
