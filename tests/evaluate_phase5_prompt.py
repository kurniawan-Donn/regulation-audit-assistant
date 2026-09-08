"""
Evaluasi Phase 5 - Audit prompt engineering.

BEDA dengan manual_test_phase4.py: script ini MEMANGGIL GEMINI API SUNGGUHAN
(pakai API key asli dari .env), karena tujuannya justru mengevaluasi KUALITAS
hasil AI (bukan cuma mekanisme kode). Pastikan GEMINI_API_KEY di .env sudah diisi.

8 contoh ketentuan di bawah sengaja dibuat FIKTIF (bukan kutipan regulasi asli
manapun) dan sengaja mencampur:
- ketentuan yang jelas relevan dengan audit TI
- ketentuan yang JELAS TIDAK relevan (harus di-skip AI, hasil = [])
- satu ketentuan yang agak ambigu (untuk melihat apakah AI memaksakan interpretasi)

Untuk tiap contoh, evaluasi manual dengan 4 pertanyaan dari brief Anda:
1. Apakah AI menemukan requirement TI dengan tepat (tidak under/over-inclusive)?
2. Apakah referensi (bab_pasal_ayat) sama persis dengan yang diberikan?
3. Apakah "pemeriksaan" benar-benar prosedur audit (bukan cuma mengulang bunyi pasal)?
4. Apakah AI mengarang sesuatu yang tidak ada di teks sumber?

Cara pakai:
    python tests/evaluate_phase5_prompt.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.ai_service import get_ai_provider
from app.services.audit_analyzer import analyze_chunk

# ---------------------------------------------------------------------------
# 8 contoh ketentuan FIKTIF untuk evaluasi kualitas prompt.
# ---------------------------------------------------------------------------
SAMPLE_CHUNKS = [
    {
        # Jelas relevan - kebijakan keamanan informasi
        "bab": "BAB V",
        "pasal": "Pasal 20",
        "ayat": "(1)",
        "text": (
            "Lembaga wajib memiliki kebijakan keamanan informasi tertulis yang "
            "mencakup aspek sumber daya manusia, fisik, logis, operasional "
            "teknologi informasi, jaringan, dan penanganan insiden."
        ),
    },
    {
        # Jelas relevan - manajemen akses dengan huruf a-d
        "bab": "BAB V",
        "pasal": "Pasal 21",
        "ayat": "(2)",
        "text": (
            "Pengendalian akses sebagaimana dimaksud pada ayat (1) paling sedikit "
            "mencakup:\na. otentikasi pengguna;\nb. otorisasi berdasarkan peran "
            "(role-based access control);\nc. pencatatan (logging) atas seluruh "
            "aktivitas akses; dan\nd. tinjauan berkala terhadap hak akses pengguna."
        ),
    },
    {
        # Jelas relevan - incident management
        "bab": "BAB V",
        "pasal": "Pasal 22",
        "ayat": "(1)",
        "text": (
            "Lembaga wajib memiliki prosedur pengelolaan insiden keamanan "
            "informasi yang mencakup deteksi, penanganan, dan pelaporan insiden."
        ),
    },
    {
        # JELAS TIDAK relevan - administrasi keuangan non-TI
        "bab": "BAB VI",
        "pasal": "Pasal 30",
        "ayat": None,
        "text": (
            "Lembaga wajib menyampaikan laporan tahunan kepada pengawas terkait "
            "kegiatan operasional non-teknologi informasi paling lambat tanggal "
            "31 Maret setiap tahun."
        ),
    },
    {
        # JELAS TIDAK relevan - cuti pegawai
        "bab": "BAB VII",
        "pasal": "Pasal 35",
        "ayat": "(1)",
        "text": "Pegawai berhak atas cuti tahunan paling sedikit 12 (dua belas) hari kerja.",
    },
    {
        # Relevan - business continuity / disaster recovery
        "bab": "BAB VIII",
        "pasal": "Pasal 40",
        "ayat": "(1)",
        "text": (
            "Lembaga wajib memiliki rencana keberlangsungan bisnis (business "
            "continuity plan) yang diuji secara berkala paling sedikit 1 (satu) "
            "kali dalam setahun untuk memastikan kesiapan pemulihan sistem "
            "teknologi informasi kritikal."
        ),
    },
    {
        # Ambigu - menyebut "teknologi" tapi tidak jelas kewajiban konkretnya
        "bab": "BAB IX",
        "pasal": "Pasal 45",
        "ayat": None,
        "text": (
            "Lembaga didorong untuk terus mengikuti perkembangan teknologi "
            "informasi guna meningkatkan daya saing."
        ),
    },
    {
        # Relevan - vendor/third party management
        "bab": "BAB X",
        "pasal": "Pasal 50",
        "ayat": "(1)",
        "text": (
            "Dalam hal Lembaga menggunakan pihak ketiga (vendor) untuk mendukung "
            "operasional teknologi informasi, Lembaga wajib memastikan pihak "
            "ketiga tersebut memenuhi standar keamanan informasi yang setara "
            "dengan standar internal Lembaga."
        ),
    },
]


def main() -> None:
    provider = get_ai_provider()

    print(f"Mengevaluasi {len(SAMPLE_CHUNKS)} contoh ketentuan...\n")

    for i, chunk in enumerate(SAMPLE_CHUNKS, start=1):
        print("=" * 70)
        print(f"CONTOH {i}")
        print(f"Referensi: {chunk['bab']} - {chunk['pasal']} - {chunk['ayat']}")
        print(f"Teks: {chunk['text'][:100]}...")
        print("-" * 70)

        try:
            result = analyze_chunk(chunk, provider, referensi_regulasi="PERATURAN CONTOH 01/2026")
        except Exception as exc:
            print(f"ERROR: {type(exc).__name__}: {exc}")
            continue

        if not result:
            print("Hasil: [] (AI menilai TIDAK relevan dengan audit TI)")
        else:
            for item in result:
                print(json.dumps(item, indent=2, ensure_ascii=False))
        print()

    print("=" * 70)
    print("SELESAI. Silakan evaluasi manual tiap hasil di atas dengan 4 pertanyaan:")
    print("1. Apakah AI menemukan requirement TI dengan tepat?")
    print("2. Apakah referensi bab_pasal_ayat sama persis?")
    print("3. Apakah 'pemeriksaan' benar-benar prosedur audit, bukan mengulang pasal?")
    print("4. Apakah AI mengarang sesuatu yang tidak ada di teks sumber?")
    print()
    print("Ekspektasi: contoh 4 & 5 -> hasil [] (tidak relevan).")
    print("Contoh 7 (ambigu) -> idealnya [] juga, atau interpretasi yang sangat hati-hati.")


if __name__ == "__main__":
    main()
