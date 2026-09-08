"""
Audit Analyzer Service.

Menghubungkan prompt (app/prompts/regulation_audit_prompt.py) dengan
AI provider (app/services/ai_service.py) untuk menganalisis SATU chunk
regulasi menjadi daftar prosedur audit.

Modul ini SENGAJA tetap tipis: tidak melakukan validasi mendalam
(itu tugas validator.py di Phase 6), hanya memastikan bentuk dasar
response (harus berupa list) sudah benar.
"""

from app.prompts.regulation_audit_prompt import (
    SYSTEM_PROMPT,
    build_batch_user_prompt,
    build_user_prompt,
)
from app.services.ai_service import AIProvider


class AuditAnalysisError(Exception):
    """Raised jika response AI tidak berbentuk seperti yang diharapkan (bukan list)."""


def analyze_chunk(
    chunk: dict,
    provider: AIProvider,
    referensi_regulasi: str = "",
) -> list[dict]:
    """
    Analisis satu chunk regulasi menjadi daftar prosedur audit.

    Args:
        chunk: dict hasil dari regulation_parser.parse_regulation_structure(),
            minimal memiliki key "text" (boleh juga "bab", "pasal", "ayat").
        provider: instance AIProvider (biasanya dari get_ai_provider()).
        referensi_regulasi: nama/nomor regulasi, mis. "POJK 11/POJK.03/2022".
            Boleh dikosongkan jika tidak diketahui.

    Returns:
        List of dict, masing-masing dengan key:
        referensi_regulasi, bab_pasal_ayat, point_ketentuan, pemeriksaan.
        List akan KOSONG jika chunk ini tidak relevan dengan audit TI
        (ini perilaku normal, bukan error).

    Raises:
        AuditAnalysisError: jika response AI bukan berbentuk JSON array.
        AIProviderError / AIResponseParsingError: diteruskan dari ai_service
            jika request ke AI gagal atau JSON tidak valid setelah semua retry.
    """
    user_prompt = build_user_prompt(
        chunk_text=chunk["text"],
        referensi_regulasi=referensi_regulasi,
        bab=chunk.get("bab"),
        pasal=chunk.get("pasal"),
        ayat=chunk.get("ayat"),
    )

    result = provider.generate_json(SYSTEM_PROMPT, user_prompt)

    if not isinstance(result, list):
        raise AuditAnalysisError(
            f"Response AI seharusnya berupa JSON array, tapi didapat: {type(result).__name__}"
        )

    return result


def analyze_chunks_batch(
    chunks: list[dict],
    provider: AIProvider,
    referensi_regulasi: str = "",
) -> list[dict]:
    """
    Analisis BANYAK chunk regulasi sekaligus dalam SATU pemanggilan AI
    (Phase 11 - batching untuk mengurangi jumlah request/mengatasi rate limit).

    Args:
        chunks: list chunk dict hasil regulation_parser.parse_regulation_structure()
            (biasanya hasil app.services.chunk_batcher.create_batches()).
        provider: instance AIProvider (biasanya dari get_ai_provider()).
        referensi_regulasi: nama/nomor regulasi, sama untuk semua chunk dalam batch ini.

    Returns:
        List gabungan hasil dari SEMUA chunk dalam batch ini (list of dict
        dengan key referensi_regulasi, bab_pasal_ayat, point_ketentuan,
        pemeriksaan). List akan KOSONG jika tidak ada satu pun chunk yang
        relevan dengan audit TI (perilaku normal, bukan error).

    Raises:
        AuditAnalysisError: jika response AI bukan berbentuk JSON array.
        AIProviderError / AIResponseParsingError: diteruskan dari ai_service.
    """
    if not chunks:
        return []

    user_prompt = build_batch_user_prompt(chunks, referensi_regulasi=referensi_regulasi)
    result = provider.generate_json(SYSTEM_PROMPT, user_prompt)

    if not isinstance(result, list):
        raise AuditAnalysisError(
            f"Response AI seharusnya berupa JSON array, tapi didapat: {type(result).__name__}"
        )

    return result
