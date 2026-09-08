# Regulation to IT Audit Assistant

MVP untuk membantu auditor Teknologi Informasi (IT Audit) membaca regulasi
dan mengubah ketentuan regulasi menjadi prosedur pemeriksaan audit — tanpa
perlu membaca dan memilah regulasi satu per satu secara manual.

```
REGULATORY REQUIREMENT  ->  AUDIT INTERPRETATION  ->  AUDIT PROCEDURE
```

Aplikasi ini **bukan** PDF summarizer. Setiap ketentuan regulasi yang relevan
dengan audit TI diterjemahkan menjadi langkah pemeriksaan yang bisa langsung
dijalankan auditor (dokumen, observasi, interview, atau evidence lain),
lengkap dengan referensi sumber (BAB/Pasal/Ayat) yang tetap terjaga.

---

## Daftar Isi

1. [Problem & Solusi](#problem--solusi)
2. [Arsitektur](#arsitektur)
3. [Instalasi](#instalasi)
4. [Environment Variable](#environment-variable)
5. [Cara Menjalankan](#cara-menjalankan)
6. [Cara Menggunakan](#cara-menggunakan)
7. [API Reference](#api-reference)
8. [Prompt Engineering AI](#prompt-engineering-ai)
9. [Keamanan](#keamanan)
10. [Keterbatasan](#keterbatasan)
11. [Struktur Proyek](#struktur-proyek)
12. [Testing](#testing)
13. [Rencana Pengembangan Selanjutnya](#rencana-pengembangan-selanjutnya)

---

## Problem & Solusi

**Masalah:** Auditor TI harus membaca regulasi (POJK/SEOJK/PBI/dll) satu per
satu secara manual, memilah ketentuan yang relevan dengan audit TI memakan
waktu lama, dan hasil interpretasi menjadi prosedur pemeriksaan bisa berbeda
antar auditor.

**Solusi:** Upload satu dokumen regulasi (PDF/TXT) → sistem otomatis
mengekstrak, mendeteksi struktur (BAB/Pasal/Ayat), mengidentifikasi ketentuan
yang relevan dengan audit TI, menafsirkannya menjadi prosedur pemeriksaan
via AI (Gemini), memvalidasi hasilnya, dan mengekspor ke Excel siap pakai.

## Arsitektur

```
USER -> WEB INTERFACE -> FILE UPLOAD -> TEXT EXTRACTION -> TEXT PREPROCESSING
     -> STRUCTURE DETECTION -> AI ANALYSIS -> JSON VALIDATION
     -> TABLE VIEW -> EXPORT EXCEL
```

| Tahap | Modul | Fase |
|---|---|---|
| Ekstraksi PDF | `app/services/pdf_parser.py` | 2 |
| Ekstraksi TXT & cleaning | `app/services/text_processor.py` | 2 |
| Deteksi struktur BAB/Pasal/Ayat/Huruf | `app/services/regulation_parser.py` | 3 |
| Abstraksi provider AI (Gemini) | `app/services/ai_service.py` | 4 |
| Prompt regulatory -> audit | `app/prompts/regulation_audit_prompt.py` | 5 |
| Penghubung prompt + AI | `app/services/audit_analyzer.py` | 5 |
| Validasi hasil & anti-hallucination | `app/services/validator.py` | 6 |
| API endpoint & orkestrasi | `app/api/routes.py` | 7 |
| Frontend upload & tabel hasil | `templates/index.html` | 7 |
| Export Excel | `app/services/excel_exporter.py` | 8 |
| **Batching chunk (hemat rate limit)** | `app/services/chunk_batcher.py` | **11** |

### Phase 11 — Batching untuk Rate Limit

Free tier Gemini API membatasi **jumlah request** (RPD/RPM) jauh lebih ketat
daripada volume token (TPM). Karena itu, sejak Phase 11, chunk-chunk kecil
hasil `regulation_parser` **dikelompokkan dulu** (`chunk_batcher.create_batches()`)
berdasarkan budget karakter (`MAX_CHARS_PER_BATCH`, default 6000) sebelum
dikirim ke AI — satu batch bisa berisi puluhan chunk sekaligus, dianalisis
dalam **satu** pemanggilan AI (`audit_analyzer.analyze_chunks_batch()`).

Efek nyata pada dokumen contoh (12 chunk): dari **12 request menjadi 1
request**. Isi tiap chunk tidak pernah dipotong — hanya dikelompokkan.
Chunk tunggal yang sendirian sudah melebihi budget tetap dikirim utuh
sebagai batch tersendiri.

Dua pengaman tambahan di `ai_service.py`:
- `GEMINI_MAX_OUTPUT_TOKENS` — mencegah response batch besar terpotong.
- `GEMINI_MIN_SECONDS_BETWEEN_REQUESTS` — jeda otomatis antar-request
  (default 4.5 detik) untuk menjaga batas RPM tidak terlampaui, walau
  banyak batch diproses berturutan dalam satu upload.

**Desain provider AI mudah diganti** (lihat `ai_service.py`):

```
AIProvider (abstract)
    └── GeminiProvider   <- aktif sekarang
```

Untuk ganti ke provider lain (OpenAI, Anthropic, dst), buat class baru yang
extend `AIProvider` dan ubah satu baris di fungsi `get_ai_provider()`.

## Instalasi

Prasyarat: Python 3.10+ dan API key Gemini ([dapatkan di sini](https://aistudio.google.com/app/apikey)).

```bash
# 1. Masuk ke folder project
cd regulation-audit-assistant

# 2. Buat virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install semua dependency
pip install -r requirements.txt

# 4. Siapkan file environment
cp .env.example .env
# lalu buka .env dan isi GEMINI_API_KEY dengan API key Anda
```

## Environment Variable

Semua konfigurasi dibaca dari file `.env` (lihat `.env.example`):

| Variable | Wajib | Keterangan |
|---|---|---|
| `GEMINI_API_KEY` | Ya | API key Gemini. **Jangan pernah** commit nilai asli ke git. |
| `GEMINI_MODEL` | Tidak | Default `gemini-2.5-flash`. Bisa diganti model Gemini lain. |
| `GEMINI_MAX_OUTPUT_TOKENS` | Tidak | Default `8192`. Naikkan jika batch besar sering menghasilkan JSON terpotong. |
| `GEMINI_MIN_SECONDS_BETWEEN_REQUESTS` | Tidak | Default `4.5`. Jeda antar-request ke Gemini untuk menjaga limit RPM. |
| `MAX_CHARS_PER_BATCH` | Tidak | Default `6000`. Budget karakter per batch chunk (Phase 11) — lebih besar = lebih sedikit request tapi risiko output terpotong lebih tinggi. |
| `APP_ENV` | Tidak | `development` / `production`. |
| `DEBUG` | Tidak | `true` / `false`. |
| `MAX_UPLOAD_SIZE_MB` | Tidak | Default `20`. Batas ukuran file upload. |

## Cara Menjalankan

```bash
uvicorn app.main:app --reload
```

Buka `http://127.0.0.1:8000/` di browser — halaman upload akan langsung tampil.

Endpoint tambahan:
- `http://127.0.0.1:8000/health` — health check (JSON)
- `http://127.0.0.1:8000/docs` — dokumentasi API otomatis (Swagger UI)

## Cara Menggunakan

1. Buka `http://127.0.0.1:8000/`.
2. Upload file regulasi (**PDF atau TXT, dokumen publik saja** — lihat [Keamanan](#keamanan)).
3. (Opsional) Isi "Nama Regulasi" agar kolom Referensi Regulasi di hasil lebih akurat, mis. `POJK 11/POJK.03/2022`. Jika dikosongkan, nama file dipakai sebagai fallback.
4. Klik **Analisis Regulasi**, tunggu proses selesai (bisa beberapa menit tergantung panjang dokumen — setiap potongan teks = 1 pemanggilan AI).
5. Hasil tampil sebagai tabel dengan status **Valid** / **Perlu Ditinjau**. Item yang di-flag disertai alasan (lihat [Prompt Engineering AI](#prompt-engineering-ai) bagian anti-hallucination).
6. Klik **Export Excel** untuk mengunduh `audit_checklist_<nama_regulasi>.xlsx` — siap dipakai auditor (header bold, freeze row, auto filter, baris yang perlu ditinjau di-highlight).

## API Reference

### `POST /api/analyze`

Upload dan analisis satu dokumen regulasi.

**Request:** `multipart/form-data`
| Field | Tipe | Wajib | Keterangan |
|---|---|---|---|
| `file` | file | Ya | File `.pdf` atau `.txt` |
| `nama_regulasi` | text | Tidak | Nama/nomor regulasi untuk kolom Referensi Regulasi |

```bash
curl -X POST http://127.0.0.1:8000/api/analyze \
  -F "file=@tests/sample_files/sample_regulation.txt" \
  -F "nama_regulasi=PERATURAN CONTOH 01/2026"
```

**Response `200 OK`:**
```json
{
  "result_id": "35975ea4892e42fea982b8fdd1839c9a",
  "filename": "sample_regulation.txt",
  "total_chunks": 12,
  "total_ketentuan": 5,
  "total_valid": 4,
  "total_flagged": 1,
  "results": [
    {
      "referensi_regulasi": "PERATURAN CONTOH 01/2026",
      "bab_pasal_ayat": "BAB V - Pasal 20 - (1)",
      "point_ketentuan": "Kewajiban kebijakan keamanan informasi",
      "pemeriksaan": "Periksa keberadaan kebijakan keamanan informasi yang telah ditetapkan dan disahkan oleh pihak berwenang.",
      "is_valid": true,
      "validation_notes": []
    }
  ],
  "chunk_errors": []
}
```

**Response error:**
| Status | Kondisi |
|---|---|
| `400` | Ekstensi file tidak didukung, file kosong, atau ukuran melebihi batas |
| `422` | Dokumen tidak bisa diekstrak/tidak ada teks yang bisa dianalisis |

### `GET /api/results/{result_id}`

Ambil ulang hasil analisis yang sudah pernah diproses (tanpa upload ulang).

```bash
curl http://127.0.0.1:8000/api/results/35975ea4892e42fea982b8fdd1839c9a
```
`404` jika `result_id` tidak ditemukan.

### `GET /api/export/{result_id}`

Unduh hasil analisis sebagai file Excel.

```bash
curl -OJ http://127.0.0.1:8000/api/export/35975ea4892e42fea982b8fdd1839c9a
```
`404` jika `result_id` tidak ditemukan, `422` jika tidak ada ketentuan untuk diekspor.

## Prompt Engineering AI

System prompt (`app/prompts/regulation_audit_prompt.py`) mewajibkan AI untuk:
- **Tidak mengarang** isi regulasi, nomor pasal/ayat, atau kewajiban baru.
- **Melewati** (bukan memaksakan) ketentuan yang tidak relevan dengan audit TI atau ambigu.
- Mengeluarkan **JSON array murni**, tanpa markdown, tanpa penjelasan tambahan.

Dua lapis pengaman tambahan di luar prompt:
1. **Retry otomatis** (`ai_service.py`) — untuk error jaringan transient dan response yang bukan JSON valid.
2. **Anti-hallucination check** (`validator.py`) — mencocokkan referensi BAB/Pasal/Ayat yang disebut AI terhadap teks sumber asli. Jika tidak ditemukan, item **tidak dibuang**, hanya diberi flag `is_valid: false` agar auditor menilai sendiri.

## Keamanan

- API key **tidak pernah** hardcode — selalu dibaca dari `.env` (lihat `app/config.py`), dan `.env` masuk `.gitignore`.
- **Hanya untuk regulasi publik** (POJK, SEOJK, PBI, PADG, dll). **Jangan upload** dokumen rahasia, data nasabah, hasil audit internal, konfigurasi sistem, atau data pribadi — catatan ini juga ditampilkan di UI.
- Tidak ada autentikasi/multi-user pada MVP ini — jangan deploy ke jaringan publik tanpa menambahkan lapisan keamanan (reverse proxy + auth) terlebih dahulu.
- File upload disimpan sementara di `uploads/` — folder ini di-gitignore, disarankan dibersihkan berkala di lingkungan produksi.

## Keterbatasan

- **Parser struktur regulasi bersifat heuristik** (regex berbasis pola BAB/Pasal/Ayat/Huruf umum) — andal untuk dokumen berformat rapi, kurang akurat untuk PDF hasil scan/OCR buruk atau format tidak baku.
- **Konsistensi AI tidak 100% terjamin** — walau prompt ketat dan `temperature=0`, model bisa sesekali berbeda hasil antar run. Validator (Phase 6) adalah jaring pengaman, bukan jaminan mutlak.
- **Trade-off batching (Phase 11):** menggabungkan chunk mengurangi jumlah request secara drastis, tapi kalau AI gagal (timeout/error) untuk satu batch, SELURUH chunk dalam batch itu gagal bersamaan (bukan hanya satu chunk seperti sebelumnya). `MAX_CHARS_PER_BATCH` yang lebih kecil mengurangi risiko ini dengan konsekuensi jumlah request lebih banyak.
- **Proses sinkron** — request `/api/analyze` menunggu semua batch selesai dianalisis sebelum merespons; dokumen sangat panjang bisa memakan waktu beberapa menit, ditambah jeda `GEMINI_MIN_SECONDS_BETWEEN_REQUESTS` antar-batch.
- **Penyimpanan hasil berbasis file JSON lokal** (`outputs/{id}.json`), bukan database — cukup untuk MVP single-user, tidak untuk multi-user/production scale.

## Struktur Proyek

```
regulation-audit-assistant/
├── app/
│   ├── main.py                          # Entry point FastAPI
│   ├── config.py                        # Konfigurasi (pydantic-settings)
│   ├── api/
│   │   └── routes.py                    # POST /api/analyze, GET /api/results, GET /api/export
│   ├── services/
│   │   ├── pdf_parser.py                # extract_pdf_text()
│   │   ├── text_processor.py            # extract_txt_text(), clean_text()
│   │   ├── regulation_parser.py         # parse_regulation_structure()
│   │   ├── chunk_batcher.py             # create_batches() - Phase 11
│   │   ├── ai_service.py                # AIProvider, GeminiProvider
│   │   ├── audit_analyzer.py            # analyze_chunk(), analyze_chunks_batch()
│   │   ├── validator.py                 # validate_results()
│   │   └── excel_exporter.py            # export_results_to_excel()
│   ├── models/
│   │   └── schemas.py                   # Pydantic response models
│   └── prompts/
│       └── regulation_audit_prompt.py   # SYSTEM_PROMPT, build_user_prompt()
├── templates/
│   └── index.html                       # Halaman upload (self-contained)
├── static/                              # (disiapkan untuk aset statis, belum dipakai)
├── uploads/                             # File upload sementara (gitignored)
├── outputs/                             # Hasil JSON & Excel (gitignored)
├── tests/
│   ├── conftest.py                      # Fixture pytest bersama
│   ├── sample_files/                    # Dokumen contoh (fiktif) untuk testing
│   ├── test_phase9_extraction.py        # pytest: ekstraksi & struktur (skenario 1-6)
│   ├── test_phase9_ai_errors.py         # pytest: error handling AI (skenario 7-9)
│   ├── test_phase9_relevance.py         # pytest: filtering non-TI (skenario 10)
│   ├── test_phase11_batching.py         # pytest: batching, prompt multi-chunk, rate limit pacing
│   ├── manual_test_phase2.py            # Script manual per fase (opsional, referensi)
│   ├── manual_test_phase3.py
│   ├── manual_test_phase4.py
│   ├── manual_test_phase7.py
│   ├── manual_test_phase8.py
│   ├── generate_sample_pdf.py           # Utility pembuat sample PDF
│   └── evaluate_phase5_prompt.py        # Evaluasi kualitas prompt dgn Gemini asli
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Testing

```bash
# Test otomatis (mocked, tidak perlu API key/network Gemini)
pytest tests/ -v

# Script manual per fase (referensi historis pengembangan, opsional dijalankan)
python tests/manual_test_phase2.py
python tests/manual_test_phase3.py
python tests/manual_test_phase4.py
python tests/manual_test_phase7.py
python tests/manual_test_phase8.py

# Evaluasi kualitas prompt AI dengan Gemini SUNGGUHAN (butuh GEMINI_API_KEY valid di .env)
python tests/evaluate_phase5_prompt.py
```

`pytest tests/ -v` mencakup 10 skenario wajib: PDF berbasis teks, TXT, PDF
panjang, PDF berstruktur BAB/Pasal, file kosong, file corrupt, AI timeout,
API error, invalid JSON, dan ketentuan non-relevan dengan audit TI.

## Rencana Pengembangan Selanjutnya

Di luar cakupan MVP ini (lihat juga bagian Keterbatasan):

- **Batching adaptif** — saat ini `MAX_CHARS_PER_BATCH` statis; bisa dikembangkan agar otomatis menyesuaikan ukuran batch berdasarkan tier/limit akun Gemini yang terdeteksi.
- **Pemrosesan asinkron** — jalankan analisis di background job (mis. Celery/RQ) dengan polling status, agar tidak menunggu di satu request HTTP.
- **Multi-dokumen & database** — dukungan analisis lintas regulasi, riwayat hasil tersimpan permanen (saat ini hanya file JSON lokal).
- **Autentikasi & multi-user** — diperlukan sebelum deploy ke luar lingkungan lokal/internal terbatas.
- **Parser struktur yang lebih robust** — menangani format regulasi tidak baku atau hasil OCR dengan lebih baik.
- **Provider AI alternatif** — abstraksi `AIProvider` sudah disiapkan; tinggal implementasi `OpenAIProvider`/`AnthropicProvider` bila diperlukan.
