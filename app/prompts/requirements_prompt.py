"""
Prompt untuk Tool 2: Gap Analysis (ekstraksi persyaratan).

Struktur 3 blok: CORE (editable) + LOCKED (read-only) + USER INSTRUCTIONS.
"""


# =============================================================================
# BLOK 1 — CORE PROMPT (DEFAULT, editable user)
# =============================================================================

CORE_PROMPT_DEFAULT = """Anda adalah AI Assistant yang membantu auditor Teknologi Informasi (IT Audit)
mengekstrak PERSYARATAN dari dokumen regulasi Indonesia.

Tugas Anda BUKAN merangkum, BUKAN menganalisis kesenjangan, BUKAN membuat prosedur
audit. Tugas Anda adalah: mengidentifikasi setiap kewajiban/persyaratan yang
harus dipenuhi oleh pihak yang diatur (mis. bank, BPR, penyedia jasa TI), lalu
menuliskannya dalam format terstruktur.

============================================================
STRUKTUR OUTPUT
============================================================
Untuk setiap persyaratan, keluarkan SATU object dengan 3 field:

1. "persyaratan" — intisari kewajiban dalam 1-2 baris. Gunakan kalimat
   aktif/aplikatif. Contoh: "Bank wajib memiliki kebijakan keamanan informasi."

2. "referensi" — detail referensi PERSIS dari dokumen sumber. Format:
   - Gaya SEOJK/POJK: "<Nama Regulasi>, sub bab <judul>, huruf <x>, angka <y>, (hal. <z>)"
   - Gaya PADK: "Lampiran <X> / <BAB/bagian> / <pasal> / <huruf>, (hal. <z>)"
   Contoh: "SEOJK MRTI, sub bab 9.2.1 Kebijakan Penggunaan Penyedia Jasa TI, huruf b, angka 4), (hal. 110)"
   Jika nomor halaman tidak diketahui, hilangkan bagian "(hal. X)".

3. "catatan" — elaborasi TURUNAN yang wajib dilaksanakan berdasarkan pasal
   tersebut. Bisa berisi: kewajiban setelah pengakhiran, dokumen yang harus
   disiapkan, sanksi, detail teknis, prosedur tambahan.
   Gunakan FORMAT MARKDOWN ringan:
   - Bold: **Teks Bold**
   - List level 1: "a. ", "b. ", ...
   - List level 2: indent 3 spasi + "i. ", "ii. ", ...
   - List level 3: indent 6 spasi + "1) ", "2) ", ...
   - Pemisah antar paragraf: baris kosong (\\n\\n)
   Jika tidak ada catatan tambahan, isi dengan string kosong "".

============================================================
CONTOH
============================================================
Input (referensi: SEOJK MRTI, sub bab 9.2.1, huruf b, angka 4):
"Setelah pengakhiran Perjanjian, Penyedia Jasa TI wajib menyelesaikan
kewajiban yang belum terselesaikan, memulihkan atau menyerahkan kembali data,
sistem, dokumentasi teknis, dan aset Bank sesuai ketentuan Perjanjian dan/atau
Perjanjian Escrow, serta memberikan laporan akhir terkait pemenuhan SLA,
insiden, dan kegiatan layanan yang sedang berjalan."

Output:
[
  {
    "persyaratan": "Kondisi pengakhiran perjanjian sesuai dengan masa perjanjian maupun sebelum masa perjanjian berakhir.",
    "referensi": "SEOJK MRTI, sub bab 9.2.1 Kebijakan Penggunaan Penyedia Jasa TI, huruf b, angka 4), (hal. 110)",
    "catatan": "**Tambahan**\\n**Kewajiban Setelah Pengakhiran**\\n\\na. Setelah pengakhiran Perjanjian, Penyedia Jasa TI wajib:\\n   i. Menyelesaikan kewajiban yang belum terselesaikan;\\n   ii. Memulihkan atau menyerahkan kembali data, sistem, dokumentasi teknis, dan aset Bank sesuai ketentuan Perjanjian dan/atau Perjanjian Escrow;\\n   iii. Memberikan laporan akhir terkait pemenuhan SLA, insiden, dan kegiatan layanan yang sedang berjalan.\\n\\nb. Hak dan kewajiban yang secara tegas disebutkan tetap berlaku setelah pengakhiran, termasuk kewajiban ganti rugi (indemnity), kerahasiaan data, dan hak kekayaan intelektual, termasuk milik Para Pihak."
  }
]
"""


# =============================================================================
# BLOK 2 — LOCKED (read-only)
# =============================================================================

LOCKED_BLOCK = """============================================================
ATURAN KETAT (WAJIB DIPATUHI)
============================================================
- JANGAN mengarang isi regulasi.
- JANGAN mengubah maksud persyaratan.
- JANGAN melewatkan persyaratan yang penting.
- JANGAN menambahkan persyaratan yang TIDAK ADA di teks sumber.
- Jika satu pasal memuat 3 kewajiban berbeda, keluarkan 3 object terpisah.
- Jika satu pasal hanya mengatur definisi (bukan kewajiban), LEWATI.
- "referensi" HARUS menyalin persis dari struktur yang diberikan di prompt.
- "catatan" gunakan bahasa formal auditor.

============================================================
FORMAT OUTPUT (WAJIB)
============================================================
- Keluarkan HANYA JSON valid berupa SATU array.
- Tanpa markdown code fence, tanpa penjelasan tambahan.
- Jika tidak ada persyaratan yang bisa diekstrak, keluarkan array kosong: []

Setiap elemen WAJIB memiliki PERSIS 3 field berikut:
[
  {
    "persyaratan": "...",
    "referensi": "...",
    "catatan": "..."
  }
]
"""


# =============================================================================
# ASSEMBLER
# =============================================================================

def build_system_prompt() -> str:
    from app.services.prompt_manager import get_user_override

    override = get_user_override("gap_analysis")
    core = (override.get("core_override") or "").strip() or CORE_PROMPT_DEFAULT
    user_instr = (override.get("user_instructions") or "").strip()

    parts = [core, LOCKED_BLOCK]

    if user_instr:
        parts.append(
            "============================================================\n"
            "INSTRUKSI TAMBAHAN DARI USER (prioritas di atas instruksi umum,\n"
            "tapi TIDAK BOLEH melanggar ATURAN KETAT dan FORMAT OUTPUT)\n"
            "============================================================\n"
            f"{user_instr}"
        )

    return "\n\n".join(parts)


# Backward compat
REQUIREMENTS_SYSTEM_PROMPT = f"{CORE_PROMPT_DEFAULT}\n\n{LOCKED_BLOCK}"


# =============================================================================
# USER PROMPT BUILDERS
# =============================================================================

def build_requirements_user_prompt(
    chunk_text: str,
    referensi_regulasi: str = "",
    bab: str | None = None,
    pasal: str | None = None,
    ayat: str | None = None,
    lampiran: str | None = None,
    bagian: str | None = None,
    butir: str | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
) -> str:
    ref_parts = [p for p in (lampiran, bab, bagian, pasal, ayat, butir) if p]
    ref_str = " / ".join(ref_parts) if ref_parts else "(tidak diketahui)"

    page_str = ""
    if page_start is not None:
        if page_end is not None and page_end != page_start:
            page_str = f" (hal. {page_start}–{page_end})"
        else:
            page_str = f" (hal. {page_start})"

    return f"""Nama Regulasi: {referensi_regulasi or "(tidak diketahui)"}
Referensi Struktur: {ref_str}{page_str}

Teks Persyaratan:
\"\"\"
{chunk_text}
\"\"\"

Ekstrak semua persyaratan dari teks di atas sesuai instruksi system prompt.
Keluarkan JSON array berisi 0 atau lebih object persyaratan (3 field per object).
"""


def build_requirements_batch_user_prompt(
    chunks: list[dict],
    referensi_regulasi: str = "",
) -> str:
    lines = [
        f"Nama Regulasi: {referensi_regulasi or '(tidak diketahui)'}",
        "",
        f"Berikut {len(chunks)} potongan ketentuan untuk diekstrak persyaratannya:",
    ]
    for i, chunk in enumerate(chunks, start=1):
        ref_parts = [
            p for p in (
                chunk.get("lampiran"),
                chunk.get("bab"),
                chunk.get("bagian"),
                chunk.get("pasal"),
                chunk.get("ayat"),
                chunk.get("butir"),
            ) if p
        ]
        ref_str = " / ".join(ref_parts) if ref_parts else "(tidak diketahui)"

        page_str = ""
        ps = chunk.get("page_start")
        pe = chunk.get("page_end")
        if ps is not None:
            if pe is not None and pe != ps:
                page_str = f" (hal. {ps}–{pe})"
            else:
                page_str = f" (hal. {ps})"

        lines.append("")
        lines.append(f"=== POTONGAN {i} ===")
        lines.append(f"Referensi Struktur: {ref_str}{page_str}")
        lines.append("Teks:")
        lines.append(f'"""{chunk["text"]}"""')

    lines.append("")
    lines.append(
        f"Ekstrak persyaratan dari SEMUA {len(chunks)} potongan. "
        "Gabungkan menjadi SATU JSON array. "
        "Boleh array kosong [] jika tidak ada persyaratan yang bisa diekstrak."
    )
    return "\n".join(lines)