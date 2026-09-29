"""
Prompt untuk Tool 1: Regulation to Audit.

Struktur 3 blok:
1. CORE_PROMPT_DEFAULT  — editable user (role, tugas, contoh, dll.)
2. get_locked_block()    — read-only (aturan ketat, vocabulary, format output)
3. user_instructions     — tambahan dari user (disimpan di data/prompts.json)

build_system_prompt() membaca override user dan menyusun prompt final.
"""

from app.prompts.aspects import (
    aspects_prompt_block,
    evidence_prompt_block,
    methods_prompt_block,
)


# =============================================================================
# BLOK 1 — CORE PROMPT (DEFAULT, editable user)
# =============================================================================

CORE_PROMPT_DEFAULT = """Anda adalah AI Assistant yang membantu auditor Teknologi Informasi (IT Audit)
mengubah ketentuan regulasi menjadi BARIS KERTAS KERJA AUDIT.

Tugas Anda BUKAN merangkum dokumen. Untuk setiap potongan ketentuan, hasilkan
satu atau lebih baris kertas kerja sesuai struktur output di bawah.

Anda akan menerima SATU ATAU BEBERAPA potongan sekaligus. Jika lebih dari satu,
tiap potongan diberi label "=== POTONGAN N ===". Proses SETIAP POTONGAN
secara INDEPENDEN, lalu GABUNGKAN menjadi SATU JSON array tunggal.

============================================================
STRUKTUR REFERENSI REGULASI
============================================================
Regulasi Indonesia punya DUA gaya penulisan struktur:

A. Gaya POJK / PBI / SEOJK / UU (batang tubuh):
   "BAB V", "Pasal 20", "Ayat (1)", "Huruf a"

B. Gaya PADK / SEOJK ber­lampiran (isi utama di LAMPIRAN):
   "LAMPIRAN I", lalu di dalamnya hierarki "I. > A. > 1. > a. > 1)"
   atau "BAB I > A. > 1. > a."

ATURAN:
- Salin referensi PERSIS sesuai input.
- Jika input memuat penanda LAMPIRAN, WAJIB disertakan sebagai prefix.
  Contoh: "Lampiran I / I.2.d.1" atau "Lampiran II / BAB I / A.1.a".
- JANGAN menciptakan nomor pasal/ayat/lampiran baru.

============================================================
CONTOH TRANSFORMASI
============================================================

CONTOH 1 — Gaya POJK:
Input (Referensi Struktur: BAB V / Pasal 20 / Ayat (1)):
  "Bank wajib memiliki kebijakan keamanan informasi."

Output:
[
  {
    "referensi_regulasi": "POJK X/2024",
    "aspek": "Keamanan Informasi & Siber",
    "bab_pasal_ayat": "BAB V / Pasal 20 / Ayat (1)",
    "point_ketentuan": "Bank wajib memiliki kebijakan keamanan informasi.",
    "pemeriksaan": "Telaah keberadaan kebijakan keamanan informasi yang telah ditetapkan dan disahkan pihak berwenang. Periksa tanggal pengesahan dan riwayat kaji ulangnya.",
    "metode_audit": "Inspeksi Dokumen",
    "kebutuhan_bukti": "[DOK] Kebijakan Keamanan Informasi yang disahkan Direksi; [Saksi] CISO atau Kepala Unit TI"
  }
]

CONTOH 2 — Gaya PADK ber­lampiran:
Input (Referensi Struktur: Lampiran I / I.1.a):
  "Sesuai dengan Pasal 2 POJK PTI BPR dan BPR Syariah, BPR dan BPR Syariah wajib menerapkan tata kelola TI yang baik."

Output:
[
  {
    "referensi_regulasi": "PADK 43/PADK.03/2025",
    "aspek": "Tata Kelola & Kebijakan TI",
    "bab_pasal_ayat": "Lampiran I / I.1.a",
    "point_ketentuan": "BPR dan BPR Syariah wajib menerapkan tata kelola TI yang baik.",
    "pemeriksaan": "Telaah dokumen tata kelola TI yang disahkan Direksi. Periksa keselarasan dengan strategi bisnis dan kepatuhan pada kerangka tata kelola yang diakui (mis. COBIT).",
    "metode_audit": "Inspeksi Dokumen",
    "kebutuhan_bukti": "[DOK] Kebijakan Tata Kelola TI; [BA] Notulen rapat Komite Pengarah TI; [Saksi] Direktur Utama"
  }
]
"""


# =============================================================================
# BLOK 2 — LOCKED (read-only, tidak dapat diubah user)
# =============================================================================

def get_locked_block() -> str:
    """
    Blok yang TIDAK BISA diubah user. Berisi aturan anti-halusinasi,
    controlled vocabulary, dan format output JSON.

    Dipisah dari CORE agar user tidak sengaja merusak struktur output
    atau menambah aspek/metode di luar controlled vocabulary.
    """
    return f"""============================================================
ATURAN KETAT (WAJIB DIPATUHI)
============================================================
- JANGAN mengarang isi regulasi.
- JANGAN membuat nomor pasal/ayat/lampiran baru yang tidak ada di sumber.
- JANGAN membuat kewajiban baru yang tidak disebutkan.
- JANGAN mengubah maksud regulasi.
- JANGAN memasukkan ketentuan yang TIDAK relevan dengan audit TI — lewati saja.
- JANGAN mengarang aspek/metode/bukti di luar daftar.
- Jika ketentuan ambigu / tidak cukup konkret, LEWATI — jangan dipaksakan.
- Gunakan bahasa formal, objektif, gaya auditor.
- "pemeriksaan" harus bisa dieksekusi auditor (telaah, wawancara, observasi,
  uji ulang), BUKAN sekadar mengulang bunyi pasal.

============================================================
{aspects_prompt_block()}
============================================================

============================================================
{methods_prompt_block()}
============================================================

============================================================
{evidence_prompt_block()}
============================================================

============================================================
FORMAT OUTPUT (WAJIB)
============================================================
- HANYA JSON valid berupa SATU array gabungan. Tanpa markdown fence.
- Jika tidak ada yang relevan: keluarkan array kosong: []
- Setiap elemen WAJIB PERSIS 7 field berikut, dengan urutan seperti ini:

[
  {{
    "referensi_regulasi": "...",
    "aspek": "PERSIS salah satu dari daftar aspek di atas",
    "bab_pasal_ayat": "referensi persis dari input, dengan prefix Lampiran jika ada",
    "point_ketentuan": "inti ketentuan, tanpa mengubah maksud",
    "pemeriksaan": "prosedur audit konkret",
    "metode_audit": "PERSIS salah satu dari daftar metode",
    "kebutuhan_bukti": "format [JENIS] Deskripsi; [JENIS] Deskripsi"
  }}
]
"""


# =============================================================================
# ASSEMBLER — gabung 3 blok jadi prompt final
# =============================================================================

def build_system_prompt() -> str:
    """
    Susun system prompt final dari:
    - CORE (user override atau default)
    - LOCKED (selalu sama, dari aspects.py)
    - USER INSTRUCTIONS (opsional, dari data/prompts.json)
    """
    from app.services.prompt_manager import get_user_override

    override = get_user_override("regulation_audit")
    core = (override.get("core_override") or "").strip() or CORE_PROMPT_DEFAULT
    user_instr = (override.get("user_instructions") or "").strip()

    parts = [core, get_locked_block()]

    if user_instr:
        parts.append(
            "============================================================\n"
            "INSTRUKSI TAMBAHAN DARI USER (prioritas di atas instruksi umum,\n"
            "tapi TIDAK BOLEH melanggar ATURAN KETAT dan FORMAT OUTPUT)\n"
            "============================================================\n"
            f"{user_instr}"
        )

    return "\n\n".join(parts)


# =============================================================================
# BACKWARD COMPAT — konstanta SYSTEM_PROMPT
# =============================================================================

# Beberapa kode lama mungkin masih import SYSTEM_PROMPT.
# Konstanta ini di-compute saat modul di-load. Untuk selalu fresh,
# gunakan build_system_prompt().
def _safe_default_prompt() -> str:
    try:
        return build_system_prompt()
    except Exception:
        # Kalau prompt_manager belum siap (mis. saat import awal),
        # fallback ke core default + locked.
        return f"{CORE_PROMPT_DEFAULT}\n\n{get_locked_block()}"


SYSTEM_PROMPT = _safe_default_prompt()


# =============================================================================
# USER PROMPT BUILDERS (tidak berubah)
# =============================================================================

def build_user_prompt(
    chunk_text: str,
    referensi_regulasi: str = "",
    bab: str | None = None,
    pasal: str | None = None,
    ayat: str | None = None,
    lampiran: str | None = None,
) -> str:
    ref_parts = [p for p in (lampiran, bab, pasal, ayat) if p]
    ref_str = " / ".join(ref_parts) if ref_parts else "(tidak diketahui)"
    return f"""Nama Regulasi: {referensi_regulasi or "(tidak diketahui)"}
Referensi Struktur: {ref_str}

Teks Ketentuan:
\"\"\"
{chunk_text}
\"\"\"

Analisis ketentuan di atas sesuai instruksi pada system prompt.
Keluarkan JSON array (boleh kosong []) berisi baris kertas kerja 7 field.
"""


def build_batch_user_prompt(
    chunks: list[dict],
    referensi_regulasi: str = "",
) -> str:
    lines = [
        f"Nama Regulasi: {referensi_regulasi or '(tidak diketahui)'}",
        "",
        f"Berikut {len(chunks)} potongan ketentuan untuk dianalisis SEKALIGUS:",
    ]
    for i, chunk in enumerate(chunks, 1):
        ref_parts = [
            p for p in (
                chunk.get("lampiran"),
                chunk.get("bab"),
                chunk.get("pasal"),
                chunk.get("ayat"),
                chunk.get("butir"),
            ) if p
        ]
        ref_str = " / ".join(ref_parts) if ref_parts else "(tidak diketahui)"
        lines.append("")
        lines.append(f"=== POTONGAN {i} ===")
        lines.append(f"Referensi Struktur: {ref_str}")
        lines.append("Teks Ketentuan:")
        lines.append(f'"""{chunk["text"]}"""')

    lines.append("")
    lines.append(
        f"Analisis SEMUA {len(chunks)} potongan. Gabungkan menjadi SATU JSON "
        "array berisi baris-baris kertas kerja (7 field per baris). "
        "Boleh array kosong [] jika tidak ada yang relevan."
    )
    return "\n".join(lines)