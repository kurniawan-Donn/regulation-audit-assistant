"""
Pydantic Schemas untuk API.
"""

from pydantic import BaseModel, Field


class AuditResultItem(BaseModel):
    referensi_regulasi: str
    bab_pasal_ayat: str
    point_ketentuan: str
    pemeriksaan: str
    is_valid: bool
    validation_notes: list[str] = Field(default_factory=list)


class ChunkError(BaseModel):
    bab: str | None = None
    pasal: str | None = None
    ayat: str | None = None
    error: str
    affected_count: int = 1  # jumlah chunk asli dalam batch yang gagal


class AnalyzeResponse(BaseModel):
    result_id: str
    filename: str
    total_chunks: int
    total_batches: int
    total_ketentuan: int
    total_valid: int
    total_flagged: int
    results: list[AuditResultItem]
    chunk_errors: list[ChunkError] = Field(default_factory=list)
