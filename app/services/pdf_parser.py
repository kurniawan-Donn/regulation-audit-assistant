"""
PDF Parser Service.

Bertanggung jawab HANYA untuk mengekstrak teks mentah dari file PDF.
Tidak melakukan cleaning atau deteksi struktur regulasi (lihat
text_processor.py dan regulation_parser.py untuk tahap selanjutnya).
"""

import os

import fitz  # PyMuPDF


class PDFExtractionError(Exception):
    """Raised ketika file PDF tidak dapat dibaca atau tidak mengandung teks."""


def extract_pdf_text(file_path: str) -> str:
    """
    Ekstrak seluruh teks dari file PDF, halaman demi halaman.

    Args:
        file_path: Path menuju file PDF yang akan diekstrak.

    Returns:
        String berisi seluruh teks yang berhasil diekstrak,
        dengan setiap halaman dipisahkan oleh newline.

    Raises:
        FileNotFoundError: jika file tidak ditemukan di file_path.
        PDFExtractionError: jika file bukan PDF yang valid, rusak,
            atau tidak mengandung teks yang dapat diekstrak
            (misalnya PDF hasil scan tanpa OCR).
    """
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

        page_texts = [page.get_text() for page in document]
    finally:
        document.close()

    full_text = "\n".join(page_texts)

    if not full_text.strip():
        raise PDFExtractionError(
            "Tidak ada teks yang dapat diekstrak dari PDF ini. "
            "Kemungkinan PDF berupa hasil scan (image-based) tanpa lapisan teks/OCR."
        )

    return full_text
