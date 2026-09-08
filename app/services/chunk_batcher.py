"""
Chunk Batcher - Phase 11 (Optimasi Rate Limit).

Latar belakang: pada free tier Gemini API, limit RPD/RPM (jumlah request)
jauh lebih ketat daripada TPM (volume token). Arsitektur awal (1 chunk =
1 request AI) sangat boros dari sisi jumlah request untuk dokumen dengan
banyak Pasal/Ayat.

Modul ini mengelompokkan banyak chunk kecil menjadi beberapa batch
berdasarkan budget KARAKTER (bukan jumlah dokumen/chunk tetap), supaya:
- Jumlah request ke AI turun drastis (memperbaiki RPD/RPM).
- Satu batch tidak terlalu besar sehingga output AI tidak terpotong
  (tetap menjaga kualitas hasil).

Isi tiap chunk TIDAK PERNAH dipotong/diubah - hanya dikelompokkan.
"""

from typing import Any


def create_batches(
    chunks: list[dict[str, Any]], max_chars_per_batch: int = 6000
) -> list[list[dict[str, Any]]]:
    """
    Kelompokkan chunk menjadi batch berdasarkan budget karakter.

    Args:
        chunks: list chunk dari regulation_parser.parse_regulation_structure().
        max_chars_per_batch: target maksimum total karakter teks chunk
            (field "text") yang digabung dalam satu batch. Ini perkiraan
            kasar untuk budget token - cukup konservatif untuk menghindari
            output AI terpotong pada model dengan max_output_tokens terbatas.

    Returns:
        List of batch. Tiap batch adalah list of chunk dict (urutan asli
        dipertahankan). Chunk yang sendirian sudah melebihi
        max_chars_per_batch tetap dimasukkan sebagai batch tersendiri -
        TIDAK dipotong isinya, supaya konteks & referensi sumber tidak rusak.

    Catatan:
        Total chunk di semua batch gabungan selalu sama dengan jumlah
        chunk input - fungsi ini hanya mengelompokkan, tidak pernah
        membuang atau menggabungkan isi chunk.
    """
    if not chunks:
        return []

    batches: list[list[dict[str, Any]]] = []
    current_batch: list[dict[str, Any]] = []
    current_size = 0

    for chunk in chunks:
        chunk_size = len(chunk.get("text", ""))

        if current_batch and current_size + chunk_size > max_chars_per_batch:
            batches.append(current_batch)
            current_batch = []
            current_size = 0

        current_batch.append(chunk)
        current_size += chunk_size

    if current_batch:
        batches.append(current_batch)

    return batches
