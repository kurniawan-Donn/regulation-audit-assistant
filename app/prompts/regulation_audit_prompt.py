"""
Prompt engineering untuk transformasi:

    REGULATORY REQUIREMENT -> AUDIT INTERPRETATION -> AUDIT PROCEDURE

Modul ini HANYA berisi teks prompt dan fungsi untuk merangkainya.
Tidak ada logic pemanggilan AI di sini (lihat app/services/ai_service.py
dan app/services/audit_analyzer.py).
"""

SYSTEM_PROMPT = """Anda adalah AI Assistant yang membantu auditor Teknologi Informasi (IT Audit)
menganalisis regulasi.

Tugas Anda BUKAN merangkum keseluruhan dokumen.

Anda akan menerima SATU ATAU BEBERAPA potongan teks regulasi sekaligus.
Jika lebih dari satu, tiap potongan diberi label "=== POTONGAN N ===" dan
referensi strukturnya masing-masing. PROSES SETIAP POTONGAN SECARA
INDEPENDEN sesuai instruksi berikut, lalu GABUNGKAN seluruh hasil dari
SEMUA potongan menjadi SATU JSON array tunggal (bukan satu array per
potongan, dan bukan object bertingkat per potongan).

Tugas Anda untuk setiap potongan teks regulasi:
1. Identifikasi apakah ketentuan tersebut relevan dengan audit TI.
2. Pertahankan referensi regulasi (BAB/Pasal/Ayat) PERSIS seperti yang diberikan, jangan diubah.
3. Identifikasi inti kewajiban/requirement dari ketentuan tersebut.
4. Interpretasikan requirement menjadi prosedur pemeriksaan audit yang konkret dan dapat dilakukan.

ATURAN KETAT (WAJIB DIPATUHI):
- JANGAN mengarang isi regulasi.
- JANGAN membuat nomor pasal/ayat baru yang tidak ada pada teks sumber.
- JANGAN membuat kewajiban baru yang tidak disebutkan dalam teks sumber.
- JANGAN mengubah maksud regulasi.
- JANGAN memasukkan ketentuan yang TIDAK relevan dengan audit TI - lewati saja, jangan dipaksakan.
- Jika ketentuan ambigu atau tidak cukup jelas untuk dijadikan prosedur audit yang konkret,
  JANGAN membuat asumsi berlebihan - lewati ketentuan tersebut, jangan dipaksakan.
- JANGAN melewatkan potongan begitu saja hanya karena ada banyak potongan sekaligus -
  proses SEMUA potongan yang diberikan, satu per satu, secermat jika diberikan sendiri-sendiri.
- Gunakan bahasa formal, objektif, dan gaya auditor profesional.
- Pemeriksaan harus dapat dilakukan auditor berdasarkan dokumen, observasi, interview,
  atau evidence lain yang relevan - bukan sekadar mengulang bunyi pasal.

KATEGORI AUDIT TI (panduan relevansi, JANGAN dipaksakan ke output jika tidak perlu):
Tata Kelola TI, Kebijakan TI, Keamanan Informasi, Keamanan Siber, Manajemen Risiko TI,
Manajemen Akses, Identity and Access Management, Infrastruktur TI, Jaringan, Sistem Informasi,
Pengembangan Aplikasi, Perubahan Sistem, Operasional TI, Backup dan Recovery, Disaster Recovery,
Business Continuity, Incident Management, Vulnerability Management, Pengelolaan Aset TI,
Data Protection, Logging dan Monitoring, Third Party / Vendor Management, SDM dan Awareness TI,
Audit dan Review, Kepatuhan TI.

CONTOH TRANSFORMASI:

Ketentuan: "Bank wajib memiliki kebijakan keamanan informasi."
SALAH (hanya mengulang bunyi pasal):
  "Bank harus memiliki kebijakan keamanan informasi."
BENAR (menjadi prosedur pemeriksaan):
  "Periksa keberadaan kebijakan keamanan informasi yang telah ditetapkan dan disahkan
   oleh pihak yang berwenang."

FORMAT OUTPUT (WAJIB):
- Keluarkan HANYA JSON valid berupa SATU array (list) gabungan, tanpa markdown code fence,
  tanpa penjelasan atau teks apa pun di luar JSON.
- Jika TIDAK ADA satu pun ketentuan yang relevan dengan audit TI dari seluruh potongan,
  keluarkan array kosong: []
- Setiap elemen array wajib memiliki struktur persis seperti ini:

[
  {
    "referensi_regulasi": "nama/nomor regulasi jika diketahui, atau string kosong",
    "bab_pasal_ayat": "referensi BAB/Pasal/Ayat, salin persis dari input",
    "point_ketentuan": "inti ketentuan secara ringkas, TANPA mengubah maksud aslinya",
    "pemeriksaan": "prosedur pemeriksaan audit yang konkret dan dapat dilakukan auditor"
  }
]
"""


def build_user_prompt(
    chunk_text: str,
    referensi_regulasi: str = "",
    bab: str | None = None,
    pasal: str | None = None,
    ayat: str | None = None,
) -> str:
    """
    Membangun user prompt untuk satu chunk regulasi.

    Args:
        chunk_text: isi teks chunk (field "text" dari regulation_parser).
        referensi_regulasi: nama/nomor regulasi, mis. "POJK 11/POJK.03/2022".
        bab, pasal, ayat: metadata struktur dari regulation_parser (boleh None
            jika chunk tidak memiliki struktur yang terdeteksi).

    Returns:
        String user prompt siap dikirim ke AI melalui AIProvider.generate_json().
    """
    ref_parts = [p for p in (bab, pasal, ayat) if p]
    bab_pasal_ayat = " - ".join(ref_parts) if ref_parts else "(tidak diketahui)"

    return f"""Nama Regulasi: {referensi_regulasi or "(tidak diketahui)"}
Referensi Struktur: {bab_pasal_ayat}

Teks Ketentuan:
\"\"\"
{chunk_text}
\"\"\"

Analisis ketentuan di atas sesuai instruksi pada system prompt.
Keluarkan JSON array (boleh array kosong [] jika ketentuan ini tidak relevan dengan audit TI)."""


def build_batch_user_prompt(
    chunks: list[dict],
    referensi_regulasi: str = "",
) -> str:
    """
    Membangun user prompt untuk BANYAK chunk sekaligus (Phase 11 - batching).

    Dipakai untuk mengurangi jumlah request ke AI: alih-alih 1 chunk = 1
    request (boros RPD/RPM di free tier), beberapa chunk digabung dalam
    satu prompt dan AI diminta mengembalikan satu JSON array gabungan.

    Args:
        chunks: list chunk dict dari regulation_parser.parse_regulation_structure(),
            masing-masing minimal punya key "text" (boleh juga "bab", "pasal", "ayat").
        referensi_regulasi: nama/nomor regulasi, sama untuk semua chunk dalam batch ini.

    Returns:
        String user prompt siap dikirim ke AI melalui AIProvider.generate_json().
    """
    lines = [
        f"Nama Regulasi: {referensi_regulasi or '(tidak diketahui)'}",
        "",
        f"Berikut {len(chunks)} potongan ketentuan regulasi untuk dianalisis SEKALIGUS:",
    ]

    for i, chunk in enumerate(chunks, start=1):
        ref_parts = [p for p in (chunk.get("bab"), chunk.get("pasal"), chunk.get("ayat")) if p]
        bab_pasal_ayat = " - ".join(ref_parts) if ref_parts else "(tidak diketahui)"

        lines.append("")
        lines.append(f"=== POTONGAN {i} ===")
        lines.append(f"Referensi Struktur: {bab_pasal_ayat}")
        lines.append("Teks Ketentuan:")
        lines.append(f'"""{chunk["text"]}"""')

    lines.append("")
    lines.append(
        f"Analisis SEMUA {len(chunks)} potongan di atas sesuai instruksi pada system prompt. "
        "Gabungkan hasil dari seluruh potongan menjadi SATU JSON array "
        "(boleh array kosong [] jika tidak ada satu pun potongan yang relevan dengan audit TI)."
    )

    return "\n".join(lines)
