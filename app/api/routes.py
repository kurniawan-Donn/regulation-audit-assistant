"""
API Routes.

Endpoint:
- POST /api/analyze          -> upload file (PDF/TXT), proses penuh, kembalikan hasil.
- GET  /api/results/{id}     -> ambil ulang hasil yang sudah pernah diproses.

PRINSIP ERROR HANDLING:
Satu chunk yang gagal dianalisis AI TIDAK BOLEH menggagalkan seluruh
request. Error per chunk dicatat di field `chunk_errors` pada response,
sementara chunk lain yang berhasil tetap ditampilkan.
"""

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import settings
from app.models.schemas import AnalyzeResponse, AuditResultItem, ChunkError
from app.services.ai_service import AIProviderError, AIResponseParsingError, get_ai_provider
from app.services.audit_analyzer import AuditAnalysisError, analyze_chunks_batch
from app.services.chunk_batcher import create_batches
from app.services.excel_exporter import build_export_filename, export_results_to_excel
from app.services.pdf_parser import PDFExtractionError, extract_pdf_text
from app.services.regulation_parser import parse_regulation_structure
from app.services.text_processor import TextExtractionError, clean_text, extract_txt_text
from app.services.validator import validate_results

router = APIRouter(prefix="/api", tags=["audit"])

UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
ALLOWED_EXTENSIONS = {".pdf", ".txt"}

# Chunk lebih pendek dari ini (kemungkinan cuma header/nomor pasal tanpa isi)
# dilewati agar tidak membuang pemanggilan API secara percuma.
MIN_CHUNK_LENGTH = 15


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_regulation(
    file: UploadFile = File(...),
    nama_regulasi: str | None = Form(None),
) -> AnalyzeResponse:
    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Format file tidak didukung: '{extension}'. Gunakan file .pdf atau .txt.",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="File kosong.")

    max_size_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(file_bytes) > max_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"Ukuran file melebihi batas {settings.max_upload_size_mb} MB.",
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    result_id = uuid.uuid4().hex
    saved_path = UPLOAD_DIR / f"{result_id}{extension}"
    saved_path.write_bytes(file_bytes)

    # --- 1. Ekstraksi teks ---
    try:
        if extension == ".pdf":
            raw_text = extract_pdf_text(str(saved_path))
        else:
            raw_text = extract_txt_text(str(saved_path))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=f"File tidak ditemukan saat diproses: {exc}") from exc
    except (PDFExtractionError, TextExtractionError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    cleaned_text = clean_text(raw_text)

    # --- 2. Deteksi struktur ---
    chunks = parse_regulation_structure(cleaned_text)
    if not chunks:
        raise HTTPException(status_code=422, detail="Tidak ada teks yang bisa dianalisis dari dokumen ini.")

    # --- 3. Kelompokkan chunk jadi batch (Phase 11) untuk menghemat jumlah request AI ---
    relevant_chunks = [c for c in chunks if len(c["text"].strip()) >= MIN_CHUNK_LENGTH]
    batches = create_batches(relevant_chunks, max_chars_per_batch=settings.max_chars_per_batch)

    # --- 4. Analisis AI per batch + validasi ---
    provider = get_ai_provider()
    referensi_regulasi = (
        nama_regulasi.strip() if nama_regulasi and nama_regulasi.strip() else Path(file.filename or "").stem
    )

    validated_results: list[dict] = []
    chunk_errors: list[ChunkError] = []

    for batch in batches:
        try:
            batch_result = analyze_chunks_batch(batch, provider, referensi_regulasi=referensi_regulasi)
        except (AIProviderError, AIResponseParsingError, AuditAnalysisError) as exc:
            babs = sorted({c["bab"] for c in batch if c.get("bab")})
            pasals = sorted({c["pasal"] for c in batch if c.get("pasal")})
            chunk_errors.append(
                ChunkError(
                    bab=", ".join(babs) if babs else None,
                    pasal=", ".join(pasals) if pasals else None,
                    ayat=None,
                    error=str(exc),
                    affected_count=len(batch),
                )
            )
            continue  # satu batch gagal TIDAK menggagalkan seluruh proses

        validated_results.extend(validate_results(batch_result, source_text=cleaned_text))

    total_valid = sum(1 for r in validated_results if r["is_valid"])

    response = AnalyzeResponse(
        result_id=result_id,
        filename=file.filename or "unknown",
        total_chunks=len(chunks),
        total_batches=len(batches),
        total_ketentuan=len(validated_results),
        total_valid=total_valid,
        total_flagged=len(validated_results) - total_valid,
        results=[AuditResultItem(**r) for r in validated_results],
        chunk_errors=chunk_errors,
    )

    # Simpan hasil ke disk agar bisa dipakai endpoint export Excel (Phase 8)
    # dan endpoint GET /api/results/{id} di bawah.
    (OUTPUT_DIR / f"{result_id}.json").write_text(response.model_dump_json(indent=2), encoding="utf-8")

    return response


@router.get("/results/{result_id}", response_model=AnalyzeResponse)
async def get_results(result_id: str) -> AnalyzeResponse:
    output_json_path = OUTPUT_DIR / f"{result_id}.json"
    if not output_json_path.exists():
        raise HTTPException(status_code=404, detail="Hasil analisis tidak ditemukan.")
    data = json.loads(output_json_path.read_text(encoding="utf-8"))
    return AnalyzeResponse(**data)


@router.get("/export/{result_id}")
async def export_to_excel(result_id: str) -> FileResponse:
    output_json_path = OUTPUT_DIR / f"{result_id}.json"
    if not output_json_path.exists():
        raise HTTPException(status_code=404, detail="Hasil analisis tidak ditemukan.")

    data = json.loads(output_json_path.read_text(encoding="utf-8"))
    results = data.get("results", [])
    if not results:
        raise HTTPException(status_code=422, detail="Tidak ada hasil ketentuan untuk diekspor.")

    referensi_regulasi = results[0].get("referensi_regulasi") or Path(data.get("filename", "regulasi")).stem
    excel_filename = build_export_filename(referensi_regulasi)
    excel_path = OUTPUT_DIR / f"{result_id}.xlsx"

    export_results_to_excel(results, str(excel_path))

    return FileResponse(
        path=str(excel_path),
        filename=excel_filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
