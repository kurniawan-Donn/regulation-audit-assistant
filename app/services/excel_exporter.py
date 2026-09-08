"""
Excel Exporter Service.

Mengekspor hasil audit ke file .xlsx sesuai format pada section 15 brief:
- Worksheet "Audit Checklist"
- Header bold dengan warna, freeze baris pertama, auto filter
- Wrap text untuk kolom panjang, lebar kolom disesuaikan, alignment sesuai
- Nomor urut otomatis

Ditambah dua kolom di luar minimum spec (Status & Catatan Validasi) supaya
auditor bisa langsung melihat item mana yang perlu ditinjau manual - hasil
dari validator.py di Phase 6, bukan cuma daftar hasil AI mentah.
"""

import re
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

HEADER_FILL = PatternFill(start_color="1E2761", end_color="1E2761", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True)
FLAGGED_FILL = PatternFill(start_color="FBEAE8", end_color="FBEAE8", fill_type="solid")

# (nama kolom, lebar kolom)
COLUMNS: list[tuple[str, int]] = [
    ("No", 5),
    ("Referensi Regulasi", 24),
    ("BAB/Pasal/Ayat", 20),
    ("Point/Ketentuan", 45),
    ("Pemeriksaan", 55),
    ("Status", 15),
    ("Catatan Validasi", 40),
]


def _safe_filename_component(text: str) -> str:
    """Bersihkan teks agar aman dipakai sebagai bagian nama file di semua OS."""
    text = (text or "").strip() or "regulasi"
    text = re.sub(r"[^\w\-.]+", "_", text)
    return text.strip("_")[:80] or "regulasi"


def build_export_filename(referensi_regulasi: str) -> str:
    """Contoh hasil: audit_checklist_POJK_11_2022.xlsx"""
    return f"audit_checklist_{_safe_filename_component(referensi_regulasi)}.xlsx"


def export_results_to_excel(
    results: list[dict[str, Any]],
    output_path: str,
) -> str:
    """
    Tulis hasil audit ke file .xlsx siap pakai auditor.

    Args:
        results: list of dict, tiap item minimal punya field
            referensi_regulasi, bab_pasal_ayat, point_ketentuan, pemeriksaan.
            Field is_valid & validation_notes bersifat opsional
            (jika tidak ada, item dianggap valid tanpa catatan).
        output_path: path lengkap file .xlsx tujuan (folder induk akan
            dibuat otomatis jika belum ada).

    Returns:
        output_path, untuk kenyamanan pemanggil.
    """
    wb = Workbook()
    ws: Worksheet = wb.active
    ws.title = "Audit Checklist"

    # --- Header ---
    for col_idx, (header, width) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(col_idx)].width = width
    ws.row_dimensions[1].height = 22

    # --- Baris data ---
    for i, item in enumerate(results, start=1):
        is_valid = item.get("is_valid", True)
        status_text = "Valid" if is_valid else "Perlu Ditinjau"
        notes_text = "; ".join(item.get("validation_notes") or [])

        row_values = [
            i,
            item.get("referensi_regulasi", ""),
            item.get("bab_pasal_ayat", ""),
            item.get("point_ketentuan", ""),
            item.get("pemeriksaan", ""),
            status_text,
            notes_text,
        ]

        row_idx = i + 1
        for col_idx, value in enumerate(row_values, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            if col_idx in (1, 6):  # No & Status -> center
                cell.alignment = Alignment(horizontal="center", vertical="top")
            else:  # kolom teks panjang -> wrap text, rata kiri atas
                cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
            if not is_valid:
                cell.fill = FLAGGED_FILL

    # --- Freeze header row & auto filter ---
    ws.freeze_panes = "A2"
    last_col_letter = get_column_letter(len(COLUMNS))
    last_row = len(results) + 1
    ws.auto_filter.ref = f"A1:{last_col_letter}{last_row}"

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    return output_path
