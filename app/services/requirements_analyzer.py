"""
Requirements Analyzer Service.

Menghubungkan prompt requirements_prompt.py dengan AI provider untuk
mengekstrak PERSYARATAN dari potongan regulasi.
"""

from app.prompts.requirements_prompt import (
    build_requirements_batch_user_prompt,
    build_requirements_user_prompt,
    build_system_prompt,
)
from app.services.ai_service import AIProvider


class RequirementsAnalysisError(Exception):
    """Raised jika response AI tidak berbentuk list."""


def analyze_chunk_for_requirements(
    chunk: dict,
    provider: AIProvider,
    referensi_regulasi: str = "",
) -> list[dict]:
    """Ekstrak persyaratan dari 1 chunk."""
    user_prompt = build_requirements_user_prompt(
        chunk_text=chunk["text"],
        referensi_regulasi=referensi_regulasi,
        bab=chunk.get("bab"),
        pasal=chunk.get("pasal"),
        ayat=chunk.get("ayat"),
        lampiran=chunk.get("lampiran"),
        bagian=chunk.get("bagian"),
        butir=chunk.get("butir"),
        page_start=chunk.get("page_start"),
        page_end=chunk.get("page_end"),
    )

    system_prompt = build_system_prompt()
    result = provider.generate_json(system_prompt, user_prompt)

    if not isinstance(result, list):
        raise RequirementsAnalysisError(
            f"Response AI harus JSON array, dapat: {type(result).__name__}"
        )
    return result


def analyze_chunks_for_requirements(
    chunks: list[dict],
    provider: AIProvider,
    referensi_regulasi: str = "",
) -> list[dict]:
    """Ekstrak persyaratan dari banyak chunk sekaligus (batching)."""
    if not chunks:
        return []

    user_prompt = build_requirements_batch_user_prompt(
        chunks, referensi_regulasi=referensi_regulasi
    )

    system_prompt = build_system_prompt()
    result = provider.generate_json(system_prompt, user_prompt)

    if not isinstance(result, list):
        raise RequirementsAnalysisError(
            f"Response AI harus JSON array, dapat: {type(result).__name__}"
        )
    return result