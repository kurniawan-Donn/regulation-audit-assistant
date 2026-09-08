"""
Result Validator.

Lapisan terakhir sebelum hasil AI ditampilkan/diekspor. Tugasnya:
1. Memastikan struktur tiap item punya field wajib & tidak kosong.
2. Mendeteksi kemungkinan duplikat antar item.
3. Anti-hallucination check sederhana: apakah referensi BAB/Pasal/Ayat
   yang disebut AI benar-benar muncul di teks sumber.

PRINSIP (sesuai section 13 brief):
"Prefer flag for validation daripada diam-diam mengubah hasil."

Artinya: validator ini TIDAK PERNAH membuang atau mengubah isi hasil AI
secara diam-diam. Item yang bermasalah tetap dikembalikan, hanya diberi
flag `is_valid: False` beserta alasan di `validation_notes`, supaya
auditor sendiri yang memutuskan apakah item itu dipakai atau tidak.
"""

import re
from typing import Any, TypedDict

REQUIRED_FIELDS = ["referensi_regulasi", "bab_pasal_ayat", "point_ketentuan", "pemeriksaan"]

# Field yang boleh kosong sesuai spec ("atau string kosong")
_OPTIONAL_EMPTY_FIELDS = {"referensi_regulasi"}

# Pola untuk mengekstrak token referensi struktur, mis. "BAB V", "Pasal 20", "(1)"
_REFERENCE_TOKEN_PATTERN = re.compile(
    r"(BAB\s+[IVXLCDM]+|Pasal\s+\d+[A-Za-z]?|\(\d+[a-zA-Z]?\))", re.IGNORECASE
)


class ValidatedItem(TypedDict):
    referensi_regulasi: str
    bab_pasal_ayat: str
    point_ketentuan: str
    pemeriksaan: str
    is_valid: bool
    validation_notes: list[str]


def validate_item_structure(item: Any) -> list[str]:
    """
    Cek field wajib ada, bertipe string, dan tidak kosong (kecuali
    referensi_regulasi yang boleh kosong).

    Returns:
        List pesan error. List kosong berarti struktur valid.
    """
    if not isinstance(item, dict):
        return [f"Item bukan JSON object, tapi: {type(item).__name__}"]

    notes: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in item:
            notes.append(f"Field wajib '{field}' tidak ada")
            continue
        value = item[field]
        if not isinstance(value, str):
            notes.append(f"Field '{field}' harus berupa teks, tapi bertipe {type(value).__name__}")
            continue
        if not value.strip() and field not in _OPTIONAL_EMPTY_FIELDS:
            notes.append(f"Field '{field}' kosong")
    return notes


def check_reference_in_source(bab_pasal_ayat: str, source_text: str) -> bool:
    """
    Cek longgar apakah token referensi (mis. 'Pasal 20', 'BAB V', '(1)')
    yang disebutkan AI benar-benar muncul di teks sumber.

    Ini BUKAN pengecekan sempurna - hanya jaring pengaman untuk menangkap
    kasus AI mengarang nomor pasal/ayat yang tidak ada sama sekali.

    Returns:
        True jika semua token ditemukan di source_text, ATAU jika
        pengecekan tidak bisa dilakukan (referensi kosong / source kosong /
        format referensi tidak dikenali) - dalam kasus ini kita TIDAK
        menyalahkan AI tanpa bukti yang jelas.
    """
    if not bab_pasal_ayat or not source_text:
        return True

    tokens = _REFERENCE_TOKEN_PATTERN.findall(bab_pasal_ayat)
    if not tokens:
        return True

    source_lower = source_text.lower()
    return all(token.lower() in source_lower for token in tokens)


def find_duplicate_indices(items: list[Any]) -> set[int]:
    """
    Tandai index item yang kemunculannya duplikat, berdasarkan kombinasi
    (bab_pasal_ayat, point_ketentuan) case-insensitive. Kemunculan PERTAMA
    tidak dianggap duplikat, hanya kemunculan kedua dst.
    """
    seen: dict[tuple[str, str], int] = {}
    duplicate_indices: set[int] = set()

    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        key = (
            str(item.get("bab_pasal_ayat", "")).strip().lower(),
            str(item.get("point_ketentuan", "")).strip().lower(),
        )
        if key == ("", ""):
            continue  # tidak cukup informasi untuk dianggap duplikat
        if key in seen:
            duplicate_indices.add(i)
        else:
            seen[key] = i

    return duplicate_indices


def validate_results(raw_items: list[Any], source_text: str = "") -> list[ValidatedItem]:
    """
    Validasi list hasil AI (biasanya dari audit_analyzer.analyze_chunk,
    atau gabungan hasil dari banyak chunk).

    Args:
        raw_items: list hasil mentah dari AI (list of dict).
        source_text: teks sumber untuk anti-hallucination check referensi.
            Boleh dikosongkan (reference check otomatis dilewati, tidak
            menghasilkan false-positive).

    Returns:
        List dengan JUMLAH SAMA seperti input (tidak ada yang dibuang).
        Tiap item dijamin punya 4 field wajib (default string kosong jika
        field asli hilang/rusak) ditambah `is_valid` dan `validation_notes`.
    """
    duplicate_indices = find_duplicate_indices(raw_items)
    results: list[ValidatedItem] = []

    for i, item in enumerate(raw_items):
        notes = validate_item_structure(item)
        is_dict = isinstance(item, dict)

        if not notes:
            # Hanya lakukan pengecekan lanjutan kalau struktur dasar sudah valid,
            # supaya pesan error tidak numpuk membingungkan.
            if i in duplicate_indices:
                notes.append("Kemungkinan duplikat dari item lain dalam hasil analisis ini")
            if source_text and not check_reference_in_source(item.get("bab_pasal_ayat", ""), source_text):
                notes.append(
                    "Referensi BAB/Pasal/Ayat tidak ditemukan persis di teks sumber - perlu ditinjau manual"
                )

        results.append(
            ValidatedItem(
                referensi_regulasi=str(item.get("referensi_regulasi", "")) if is_dict else "",
                bab_pasal_ayat=str(item.get("bab_pasal_ayat", "")) if is_dict else "",
                point_ketentuan=str(item.get("point_ketentuan", "")) if is_dict else "",
                pemeriksaan=str(item.get("pemeriksaan", "")) if is_dict else "",
                is_valid=(len(notes) == 0),
                validation_notes=notes,
            )
        )

    return results
