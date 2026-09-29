"""
PDF Exporter Service.

Generate kertas kerja audit dalam format PDF A4 landscape.
10 kolom konsisten dengan Excel agar auditor familiar.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# =============================================================================
# KONFIGURASI
# =============================================================================

PAGE_WIDTH, PAGE_HEIGHT = landscape(A4)  # 29.7cm × 21cm
MARGIN_LEFT = 1.0 * cm
MARGIN_RIGHT = 1.0 * cm
MARGIN_TOP = 1.5 * cm
MARGIN_BOTTOM = 1.5 * cm

# Warna tema
COLOR_PRIMARY = colors.HexColor("#1E2761")
COLOR_PRIMARY_LIGHT = colors.HexColor("#E8EFFC")
COLOR_TEXT = colors.HexColor("#2B2E3A")
COLOR_MUTED = colors.HexColor("#64748B")
COLOR_BORDER = colors.HexColor("#D9E0F0")
COLOR_FLAGGED_BG = colors.HexColor("#FBEAE8")
COLOR_STATUS_BG = colors.HexColor("#FFF8E1")

# Lebar kolom (dalam cm) — total harus <= 27.7cm (lebar halaman - margin)
COL_WIDTHS_CM = [
    0.9,   # No
    2.4,   # Referensi Regulasi
    2.6,   # Aspek / Domain
    2.4,   # BAB / Pasal / Ayat
    4.0,   # Ketentuan
    4.5,   # Prosedur Pemeriksaan
    2.4,   # Metode Audit
    3.2,   # Kebutuhan Bukti
    2.1,   # Status Kepatuhan
    3.2,   # Catatan / Temuan
]
COL_WIDTHS = [w * cm for w in COL_WIDTHS_CM]

HEADERS = [
    "No",
    "Referensi Regulasi",
    "Aspek / Domain",
    "BAB / Pasal / Ayat",
    "Ketentuan / Poin Regulasi",
    "Prosedur Pemeriksaan",
    "Metode Audit",
    "Kebutuhan Bukti",
    "Status Kepatuhan",
    "Catatan / Temuan",
]


# =============================================================================
# HELPERS
# =============================================================================

def _safe_filename_component(text: str) -> str:
    text = (text or "").strip() or "regulasi"
    text = re.sub(r"[^\w\-.]+", "_", text)
    return text.strip("_")[:80] or "regulasi"


def build_pdf_filename(referensi_regulasi: str) -> str:
    return f"kertas_kerja_{_safe_filename_component(referensi_regulasi)}.pdf"


def _escape_xml(text: str) -> str:
    """Escape karakter XML untuk Paragraph reportlab."""
    if text is None:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _format_page_range(result: dict, idx: int) -> str:
    """Placeholder — kalau nanti ada page info di result."""
    return ""


# =============================================================================
# STYLES
# =============================================================================

def _build_styles():
    base = getSampleStyleSheet()

    styles = {
        "title": ParagraphStyle(
            "title",
            parent=base["Title"],
            fontSize=16,
            leading=20,
            textColor=COLOR_PRIMARY,
            alignment=TA_CENTER,
            spaceAfter=4,
            fontName="Helvetica-Bold",
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=base["Normal"],
            fontSize=9,
            leading=12,
            textColor=COLOR_MUTED,
            alignment=TA_CENTER,
            spaceAfter=12,
        ),
        "meta_label": ParagraphStyle(
            "meta_label",
            parent=base["Normal"],
            fontSize=8,
            leading=11,
            textColor=COLOR_MUTED,
            fontName="Helvetica-Bold",
        ),
        "meta_value": ParagraphStyle(
            "meta_value",
            parent=base["Normal"],
            fontSize=9,
            leading=11,
            textColor=COLOR_TEXT,
        ),
        "cell": ParagraphStyle(
            "cell",
            parent=base["Normal"],
            fontSize=6.5,
            leading=8.5,
            textColor=COLOR_TEXT,
            wordWrap="CJK",
        ),
        "cell_muted": ParagraphStyle(
            "cell_muted",
            parent=base["Normal"],
            fontSize=6,
            leading=8,
            textColor=COLOR_MUTED,
            wordWrap="CJK",
        ),
        "cell_center": ParagraphStyle(
            "cell_center",
            parent=base["Normal"],
            fontSize=6.5,
            leading=8.5,
            textColor=COLOR_TEXT,
            alignment=TA_CENTER,
        ),
        "header": ParagraphStyle(
            "header",
            parent=base["Normal"],
            fontSize=6.5,
            leading=8.5,
            textColor=colors.white,
            fontName="Helvetica-Bold",
            alignment=TA_CENTER,
        ),
        "footer": ParagraphStyle(
            "footer",
            parent=base["Normal"],
            fontSize=7,
            leading=9,
            textColor=COLOR_MUTED,
            alignment=TA_CENTER,
        ),
    }
    return styles


# =============================================================================
# KOMPONEN
# =============================================================================

def _build_header_flowables(referensi_regulasi: str, filename: str, summary: dict, styles: dict) -> list:
    """Bangun header halaman (judul + info)."""
    flowables = []

    flowables.append(Paragraph(
        "KERTAS KERJA AUDIT TEKNOLOGI INFORMASI",
        styles["title"],
    ))
    flowables.append(Paragraph(
        f"Berdasarkan: {_escape_xml(referensi_regulasi or filename)}",
        styles["subtitle"],
    ))

    # Baris metadata (2 kolom: label | value)
    now_str = datetime.now().strftime("%d %B %Y, %H:%M")
    meta_data = [
        [
            Paragraph("Tanggal Cetak", styles["meta_label"]),
            Paragraph(_escape_xml(now_str), styles["meta_value"]),
            Paragraph("Total Ketentuan", styles["meta_label"]),
            Paragraph(str(summary.get("total_ketentuan", 0)), styles["meta_value"]),
        ],
        [
            Paragraph("Sumber Dokumen", styles["meta_label"]),
            Paragraph(_escape_xml(filename or "-"), styles["meta_value"]),
            Paragraph("Valid / Perlu Ditinjau", styles["meta_label"]),
            Paragraph(
                f"{summary.get('total_valid', 0)} / {summary.get('total_flagged', 0)}",
                styles["meta_value"],
            ),
        ],
    ]
    meta_table = Table(
        meta_data,
        colWidths=[3.0 * cm, 8.0 * cm, 3.8 * cm, 4.0 * cm],
        hAlign="LEFT",
    )
    meta_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("LINEBELOW", (0, 0), (-1, 0), 0.3, COLOR_BORDER),
        ("LINEBELOW", (0, 1), (-1, 1), 0.3, COLOR_BORDER),
    ]))
    flowables.append(meta_table)
    flowables.append(Spacer(1, 6 * mm))
    return flowables


def _build_result_table(results: list[dict], styles: dict) -> Table:
    """Bangun tabel hasil (10 kolom)."""
    # Header
    header_row = [Paragraph(h, styles["header"]) for h in HEADERS]
    data = [header_row]

    # Baris data
    for i, item in enumerate(results, start=1):
        row = [
            Paragraph(str(i), styles["cell_center"]),
            Paragraph(_escape_xml(item.get("referensi_regulasi", "") or "-"), styles["cell"]),
            Paragraph(_escape_xml(item.get("aspek", "") or "-"), styles["cell"]),
            Paragraph(_escape_xml(item.get("bab_pasal_ayat", "") or "-"), styles["cell_muted"]),
            Paragraph(_escape_xml(item.get("point_ketentuan", "")), styles["cell"]),
            Paragraph(_escape_xml(item.get("pemeriksaan", "")), styles["cell"]),
            Paragraph(_escape_xml(item.get("metode_audit", "") or "-"), styles["cell"]),
            Paragraph(_escape_xml(item.get("kebutuhan_bukti", "") or "-"), styles["cell_muted"]),
            Paragraph(_escape_xml(item.get("status_kepatuhan", "Belum Diaudit")), styles["cell_center"]),
            Paragraph(_escape_xml(item.get("catatan_temuan", "") or "-"), styles["cell_muted"]),
        ]
        data.append(row)

    table = Table(
        data,
        colWidths=COL_WIDTHS,
        repeatRows=1,  # header muncul di setiap halaman
    )

    # Base style
    style_commands = [
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 6.5),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        # Body
        ("VALIGN", (0, 1), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 1), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        # Grid
        ("GRID", (0, 0), (-1, -1), 0.25, COLOR_BORDER),
        # Alternate row color
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]

    # Highlight flagged rows + status column
    for i, item in enumerate(results, start=1):
        row_idx = i  # header = 0

        if not item.get("is_valid", True):
            style_commands.append(
                ("BACKGROUND", (0, row_idx), (-1, row_idx), COLOR_FLAGGED_BG)
            )

        # Status column background
        status = item.get("status_kepatuhan", "")
        if status and status != "Belum Diaudit":
            style_commands.append(
                ("BACKGROUND", (8, row_idx), (8, row_idx), COLOR_STATUS_BG)
            )

    table.setStyle(TableStyle(style_commands))
    return table


def _draw_page_footer(canvas, doc):
    """Gambar footer di setiap halaman."""
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(COLOR_MUTED)
    page_num = canvas.getPageNumber()
    footer_text = (
        f"Regulation to IT Audit Assistant  |  Halaman {page_num}  |  "
        f"Dicetak: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )
    canvas.drawCentredString(PAGE_WIDTH / 2, 0.8 * cm, footer_text)
    canvas.restoreState()


# =============================================================================
# ENTRY POINT
# =============================================================================

def export_results_to_pdf(
    results: list[dict[str, Any]],
    output_path: str,
    referensi_regulasi: str = "",
    filename: str = "",
) -> str:
    """
    Tulis hasil audit ke file PDF.

    Args:
        results: list of dict hasil analisis
        output_path: path file PDF tujuan
        referensi_regulasi: nama regulasi untuk header
        filename: nama file sumber

    Returns:
        output_path
    """
    styles = _build_styles()

    # Summary
    summary = {
        "total_ketentuan": len(results),
        "total_valid": sum(1 for r in results if r.get("is_valid", True)),
    }
    summary["total_flagged"] = summary["total_ketentuan"] - summary["total_valid"]

    doc = SimpleDocTemplate(
        output_path,
        pagesize=landscape(A4),
        leftMargin=MARGIN_LEFT,
        rightMargin=MARGIN_RIGHT,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
        title=f"Kertas Kerja Audit — {referensi_regulasi or filename}",
        author="Regulation to IT Audit Assistant",
        subject="Kertas Kerja Audit TI",
    )

    flowables: list = []
    flowables.extend(
        _build_header_flowables(referensi_regulasi, filename, summary, styles)
    )

    if results:
        flowables.append(_build_result_table(results, styles))
    else:
        flowables.append(Paragraph(
            "Tidak ada ketentuan untuk ditampilkan.",
            styles["subtitle"],
        ))

    doc.build(flowables, onFirstPage=_draw_page_footer, onLaterPages=_draw_page_footer)

    return output_path