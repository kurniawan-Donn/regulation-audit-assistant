"""
Controlled vocabulary — SINGLE SOURCE OF TRUTH.

Kontrak:
- ASPECTS           → 12 aspek (kolom 3 Excel) — diisi AI
- AUDIT_METHODS     → 7 metode audit (kolom 7) — diisi AI
- EVIDENCE_TYPES    → 8 jenis bukti (kolom 8) — dipakai AI untuk format
- STATUS_KEPATUHAN  → 5 status (kolom 9) — diisi auditor

Mengubah vocabulary = mengubah kontrak. Wajib update:
- prompt (regulation_audit_prompt.py)
- validator (validator.py)
- excel exporter (excel_exporter.py — dropdown)
"""

from typing import Final

ASPECTS: Final[tuple[str, ...]] = (
    "Tata Kelola & Kebijakan TI",
    "Manajemen Risiko TI",
    "Keamanan Informasi & Siber",
    "Manajemen Akses & Identitas",
    "Infrastruktur & Jaringan",
    "Pengembangan & Perubahan Sistem",
    "Operasional TI",
    "Kontinuitas & Pemulihan Bencana",
    "Pengelolaan Data & Privasi",
    "Pihak Ketiga (PPJTI/Vendor)",
    "Audit & Kepatuhan TI",
    "SDM & Awareness TI",
)

AUDIT_METHODS: Final[tuple[str, ...]] = (
    "Inspeksi Dokumen",
    "Wawancara",
    "Observasi",
    "Uji Ulang (Re-performance)",
    "Analisis Data",
    "Konfirmasi",
    "Penelusuran (Tracing/Vouching)",
)

EVIDENCE_TYPES: Final[dict[str, str]] = {
    "DOK": "Dokumen (kebijakan, SOP, prosedur, dll.)",
    "LOG": "Log / rekaman sistem atau aktivitas",
    "BA": "Berita Acara (UAT, serah terima, dll.)",
    "Saksi": "Wawancara dengan personel tertentu",
    "SShot": "Screenshot / tangkapan layar konfigurasi",
    "Kontrak": "Kontrak / perjanjian kerja sama",
    "Laporan": "Laporan formal (audit, pentest, dsb.)",
    "Hasil Uji": "Hasil pengujian teknis (restore, pentest, dsb.)",
}

STATUS_KEPATUHAN: Final[tuple[str, ...]] = (
    "Patuh",
    "Sebagian Patuh",
    "Tidak Patuh",
    "N/A",
    "Belum Diaudit",
)

STATUS_KEPATUHAN_DEFAULT: Final[str] = "Belum Diaudit"


# ---------------------------------------------------------------------------
# Validasi
# ---------------------------------------------------------------------------

def is_valid_aspect(value: str) -> bool:
    return value in ASPECTS


def is_valid_audit_method(value: str) -> bool:
    return value in AUDIT_METHODS


def is_valid_status_kepatuhan(value: str) -> bool:
    return value in STATUS_KEPATUHAN


def find_aspect_insensitive(value: str) -> str | None:
    """Cocokkan case-insensitive. Untuk memaafkan output AI huruf kecil."""
    if not value:
        return None
    needle = value.strip().casefold()
    for aspect in ASPECTS:
        if aspect.casefold() == needle:
            return aspect
    return None


def find_method_insensitive(value: str) -> str | None:
    if not value:
        return None
    needle = value.strip().casefold()
    for method in AUDIT_METHODS:
        if method.casefold() == needle:
            return method
    return None


# ---------------------------------------------------------------------------
# Blok teks untuk SYSTEM_PROMPT
# ---------------------------------------------------------------------------

def aspects_prompt_block() -> str:
    lines = ["DAFTAR ASPEK/DOMAIN (WAJIB pilih PERSIS SATU):"]
    for i, aspect in enumerate(ASPECTS, 1):
        lines.append(f"{i}. {aspect}")
    lines.append("")
    lines.append("Jika tidak ada yang cocok persis, pilih yang paling dekat. "
                 "JANGAN mengarang aspek baru.")
    return "\n".join(lines)


def methods_prompt_block() -> str:
    lines = ["DAFTAR METODE AUDIT (WAJIB pilih PERSIS SATU):"]
    for i, method in enumerate(AUDIT_METHODS, 1):
        lines.append(f"{i}. {method}")
    lines.append("")
    lines.append("Pilih metode PALING relevan. JANGAN mengarang metode baru.")
    return "\n".join(lines)


def evidence_prompt_block() -> str:
    lines = ["JENIS BUKTI YANG DIIZINKAN (pakai kode dalam [kurung siku]):"]
    for code, desc in EVIDENCE_TYPES.items():
        lines.append(f"- [{code}] = {desc}")
    lines.append("")
    lines.append("FORMAT KEBUTUHAN BUKTI (WAJIB): setiap butir diawali kode "
                 "jenis bukti dalam [kurung siku], lalu deskripsi singkat. "
                 "Pisahkan dengan titik koma (;) jika butuh lebih dari 1 bukti.")
    lines.append("")
    lines.append("CONTOH BENAR:")
    lines.append('  "[DOK] Kebijakan Keamanan Informasi yang disahkan Direksi; '
                 '[Saksi] CISO atau Kepala Unit TI"')
    lines.append("CONTOH SALAH:")
    lines.append('  "Kebijakan keamanan informasi"')
    return "\n".join(lines)