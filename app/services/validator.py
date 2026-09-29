"""
Result Validator.
Fase 12: validasi 7 field AI + controlled vocab + normalisasi + anti-halusinasi
(mendukung referensi gaya POJK & PADK).
"""

import re
from typing import Any, TypedDict

from app.prompts.aspects import (
    STATUS_KEPATUHAN_DEFAULT,
    find_aspect_insensitive,
    find_method_insensitive,
    is_valid_status_kepatuhan,
)

REQUIRED_FIELDS = [
    "referensi_regulasi",
    "aspek",
    "bab_pasal_ayat",
    "point_ketentuan",
    "pemeriksaan",
    "metode_audit",
    "kebutuhan_bukti",
]

_OPTIONAL_EMPTY_FIELDS = {"referensi_regulasi"}

_AUDITOR_FIELDS = {
    "status_kepatuhan": STATUS_KEPATUHAN_DEFAULT,
    "catatan_temuan": "",
}

# Token referensi: dukung POJK + PADK
_REFERENCE_TOKEN_PATTERN = re.compile(
    r"("
    r"Lampiran\s+[IVXLCDM]+"
    r"|BAB\s+[IVXLCDM]+"
    r"|Pasal\s+\d+[A-Za-z]?"
    r"|Ayat\s*\(\d+[a-zA-Z]?\)"
    r"|\(\d+[a-zA-Z]?\)"
    r"|\b[IVXLCDM]{1,4}\."
    r"|\b[A-Z]\."
    r"|\b\d+[a-z]?\)"
    r")"
)


class ValidatedItem(TypedDict):
    referensi_regulasi: str
    aspek: str
    bab_pasal_ayat: str
    point_ketentuan: str
    pemeriksaan: str
    metode_audit: str
    kebutuhan_bukti: str
    status_kepatuhan: str
    catatan_temuan: str
    is_valid: bool
    validation_notes: list[str]


def validate_item_structure(item: Any) -> tuple[dict[str, str], list[str]]:
    if not isinstance(item, dict):
        return {}, [f"Item bukan JSON object, tapi: {type(item).__name__}"]

    notes: list[str] = []
    normalized: dict[str, str] = {}

    for field in REQUIRED_FIELDS:
        if field not in item:
            notes.append(f"Field wajib '{field}' tidak ada")
            normalized[field] = ""
            continue
        value = item[field]
        if not isinstance(value, str):
            notes.append(f"Field '{field}' harus teks, bukan {type(value).__name__}")
            normalized[field] = str(value)
            continue
        if not value.strip() and field not in _OPTIONAL_EMPTY_FIELDS:
            notes.append(f"Field '{field}' kosong")
        normalized[field] = value.strip()
    return normalized, notes


def validate_controlled_vocab(fields: dict[str, str]) -> list[str]:
    notes: list[str] = []
    aspek = fields.get("aspek", "")
    if aspek and find_aspect_insensitive(aspek) is None:
        notes.append(f"Aspek '{aspek}' tidak ada di daftar aspek resmi — perlu ditinjau")
    metode = fields.get("metode_audit", "")
    if metode and find_method_insensitive(metode) is None:
        notes.append(f"Metode audit '{metode}' tidak ada di daftar metode resmi — perlu ditinjau")
    return notes


def normalize_controlled_vocab(fields: dict[str, str]) -> None:
    aspek = fields.get("aspek", "")
    if aspek:
        canonical = find_aspect_insensitive(aspek)
        if canonical:
            fields["aspek"] = canonical
    metode = fields.get("metode_audit", "")
    if metode:
        canonical = find_method_insensitive(metode)
        if canonical:
            fields["metode_audit"] = canonical


def check_reference_in_source(bab_pasal_ayat: str, source_text: str) -> bool:
    if not bab_pasal_ayat or not source_text:
        return True
    tokens = _REFERENCE_TOKEN_PATTERN.findall(bab_pasal_ayat)
    if not tokens:
        return True
    source_lower = source_text.lower()
    return all(token.lower() in source_lower for token in tokens)


def find_duplicate_indices(items: list[Any]) -> set[int]:
    seen: dict[tuple[str, str], int] = {}
    dup: set[int] = set()
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        key = (
            str(item.get("bab_pasal_ayat", "")).strip().lower(),
            str(item.get("point_ketentuan", "")).strip().lower(),
        )
        if key == ("", ""):
            continue
        if key in seen:
            dup.add(i)
        else:
            seen[key] = i
    return dup


def validate_results(raw_items: list[Any], source_text: str = "") -> list[ValidatedItem]:
    duplicate_indices = find_duplicate_indices(raw_items)
    results: list[ValidatedItem] = []

    for i, item in enumerate(raw_items):
        fields, notes = validate_item_structure(item)

        for field, default_value in _AUDITOR_FIELDS.items():
            raw_value = item.get(field, default_value) if isinstance(item, dict) else default_value
            if not isinstance(raw_value, str):
                raw_value = default_value
            fields[field] = raw_value

        if not notes:
            notes.extend(validate_controlled_vocab(fields))

        normalize_controlled_vocab(fields)

        if not notes:
            if i in duplicate_indices:
                notes.append("Kemungkinan duplikat dari item lain dalam hasil analisis ini")
            if source_text and not check_reference_in_source(
                fields.get("bab_pasal_ayat", ""), source_text
            ):
                notes.append(
                    "Referensi BAB/Pasal/Ayat/Lampiran tidak ditemukan persis "
                    "di teks sumber — perlu ditinjau manual"
                )

        if fields.get("status_kepatuhan") and not is_valid_status_kepatuhan(fields["status_kepatuhan"]):
            notes.append(
                f"Status kepatuhan '{fields['status_kepatuhan']}' tidak dikenali"
            )

        results.append(
            ValidatedItem(
                referensi_regulasi=fields.get("referensi_regulasi", ""),
                aspek=fields.get("aspek", ""),
                bab_pasal_ayat=fields.get("bab_pasal_ayat", ""),
                point_ketentuan=fields.get("point_ketentuan", ""),
                pemeriksaan=fields.get("pemeriksaan", ""),
                metode_audit=fields.get("metode_audit", ""),
                kebutuhan_bukti=fields.get("kebutuhan_bukti", ""),
                status_kepatuhan=fields.get("status_kepatuhan", STATUS_KEPATUHAN_DEFAULT),
                catatan_temuan=fields.get("catatan_temuan", ""),
                is_valid=(len(notes) == 0),
                validation_notes=notes,
            )
        )
    return results