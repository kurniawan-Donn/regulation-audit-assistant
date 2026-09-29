"""
Pydantic Schemas untuk API.

Berisi:
- Hasil analisis (AuditResultItem, AnalyzeResponse, dll.)
- Preview & Tree (PreviewNode, PreviewResponse, dll.)
- Settings (RuntimeSettingsResponse, RuntimeSettingsUpdate, dll.)
- Audit Workflow (BulkUpdateRequest, AddItemRequest, DeleteItemsRequest, BulkActionResponse)
"""

from pydantic import BaseModel, Field

from app.prompts.aspects import STATUS_KEPATUHAN_DEFAULT


# ---------------------------------------------------------------------------
# Hasil analisis
# ---------------------------------------------------------------------------

class AuditResultItem(BaseModel):
    # AI (7 field)
    referensi_regulasi: str = ""
    aspek: str = ""
    bab_pasal_ayat: str = ""
    point_ketentuan: str = ""
    pemeriksaan: str = ""
    metode_audit: str = ""
    kebutuhan_bukti: str = ""

    # Auditor (2 field)
    status_kepatuhan: str = STATUS_KEPATUHAN_DEFAULT
    catatan_temuan: str = ""

    # Internal (tidak ke Excel)
    is_valid: bool = True
    validation_notes: list[str] = Field(default_factory=list)


class ChunkError(BaseModel):
    lampiran: str | None = None
    bab: str | None = None
    pasal: str | None = None
    ayat: str | None = None
    error: str
    affected_count: int = 1


class AnalyzeResponse(BaseModel):
    result_id: str
    filename: str
    preview_id: str = ""

    total_chunks: int
    total_chunks_available: int = 0
    total_batches: int
    total_ketentuan: int
    total_valid: int
    total_flagged: int

    results: list[AuditResultItem]
    chunk_errors: list[ChunkError] = Field(default_factory=list)
    total_by_aspect: dict[str, int] = Field(default_factory=dict)
    filter_applied: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Edit single item
# ---------------------------------------------------------------------------

class UpdateItemRequest(BaseModel):
    aspek: str | None = None
    bab_pasal_ayat: str | None = None
    point_ketentuan: str | None = None
    pemeriksaan: str | None = None
    metode_audit: str | None = None
    kebutuhan_bukti: str | None = None
    status_kepatuhan: str | None = None
    catatan_temuan: str | None = None


# ---------------------------------------------------------------------------
# Audit Workflow — Bulk / Add / Delete
# ---------------------------------------------------------------------------

class BulkUpdateRequest(BaseModel):
    """
    Payload untuk PATCH /api/results/{id}/items/bulk.
    Update kolom auditor (status + catatan) untuk banyak item sekaligus.
    """
    item_indices: list[int] = Field(..., min_length=1)
    status_kepatuhan: str | None = None
    catatan_temuan: str | None = None


class AddItemRequest(BaseModel):
    """
    Payload untuk POST /api/results/{id}/items.
    Tambah baris manual ke hasil analisis (di luar output AI).
    """
    referensi_regulasi: str = ""
    aspek: str = ""
    bab_pasal_ayat: str = ""
    point_ketentuan: str = ""
    pemeriksaan: str = ""
    metode_audit: str = ""
    kebutuhan_bukti: str = ""
    status_kepatuhan: str = STATUS_KEPATUHAN_DEFAULT
    catatan_temuan: str = ""


class DeleteItemsRequest(BaseModel):
    """Payload untuk DELETE /api/results/{id}/items (body, bukan path)."""
    item_indices: list[int] = Field(..., min_length=1)


class BulkActionResponse(BaseModel):
    """Response generik untuk bulk update / delete / add."""
    affected: int
    total_ketentuan: int
    total_valid: int
    total_flagged: int
    total_by_aspect: dict[str, int] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Preview & Tree
# ---------------------------------------------------------------------------

class PreviewNode(BaseModel):
    id: str
    label: str
    type: str
    page_start: int | None = None
    page_end: int | None = None
    chunk_indices: list[int] = Field(default_factory=list)
    children: list["PreviewNode"] = Field(default_factory=list)


PreviewNode.model_rebuild()


class PreviewResponse(BaseModel):
    preview_id: str
    filename: str
    total_chunks: int
    tree: list[PreviewNode]
    from_cache: bool = False     
    parse_time_ms: int = 0


class PreviewRetrieveResponse(BaseModel):
    preview_id: str
    filename: str
    total_chunks: int
    tree: list[PreviewNode]
    filter_applied: list[str] = Field(default_factory=list)


class AnalyzeSelectedRequest(BaseModel):
    preview_id: str
    selected_chunk_indices: list[int] = Field(..., min_length=1)
    selected_labels: list[str] = Field(default_factory=list)
    nama_regulasi: str | None = None


# ---------------------------------------------------------------------------
# Estimasi Biaya
# ---------------------------------------------------------------------------

class EstimateRequest(BaseModel):
    preview_id: str
    selected_chunk_indices: list[int] = Field(..., min_length=1)


class EstimateResponse(BaseModel):
    total_chunks: int
    total_chars: int
    estimated_batches: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    cost_idr: float
    time_seconds_estimate: int
    model_name: str


# ---------------------------------------------------------------------------
# Runtime Settings
# ---------------------------------------------------------------------------

class RuntimeSettingsResponse(BaseModel):
    """Response GET /api/settings — API key di-mask."""
    gemini_api_key_masked: str = ""
    gemini_api_key_set: bool = False
    gemini_model: str = ""
    gemini_max_output_tokens: int = 8192
    gemini_min_seconds_between_requests: float = 4.5
    max_chars_per_batch: int = 6000
    theme: str = "auto"
    preset_models: list[str] = Field(default_factory=list)


class RuntimeSettingsUpdate(BaseModel):
    """Payload PUT /api/settings."""
    gemini_api_key: str | None = None
    gemini_model: str | None = None
    gemini_max_output_tokens: int | None = None
    gemini_min_seconds_between_requests: float | None = None
    max_chars_per_batch: int | None = None
    theme: str | None = None


class ConnectionTestRequest(BaseModel):
    """Payload POST /api/settings/test-connection."""
    api_key: str | None = None
    model: str | None = None


class ConnectionTestResponse(BaseModel):
    ok: bool
    message: str
    model_tested: str
    latency_ms: int = 0


class DiagnosticsResponse(BaseModel):
    server_ok: bool
    ai_ok: bool
    ai_message: str
    model_name: str
    cache_previews_count: int
    cache_size_mb: float
    outputs_count: int
    app_version: str
    app_env: str

    # ---------------------------------------------------------------------------
# Gap Analysis Tool
# ---------------------------------------------------------------------------

class RequirementItem(BaseModel):
    """Satu baris persyaratan di Gap Analysis."""
    persyaratan: str = ""
    referensi: str = ""
    catatan: str = ""
    status_gap: str = ""  # kosong default, diisi auditor


class AnalyzeRequirementsRequest(BaseModel):
    """Payload POST /api/analyze-requirements."""
    preview_id: str
    nama_regulasi: str | None = None
    # Kalau kosong → analisis semua chunk. Kalau diisi → hanya chunk
    # yang cocok dengan filter teks (case-insensitive substring).
    filter_text: str | None = None


class AnalyzeRequirementsResponse(BaseModel):
    result_id: str
    filename: str
    preview_id: str = ""

    total_chunks_analyzed: int
    total_chunks_available: int
    total_batches: int
    total_requirements: int

    requirements: list[RequirementItem]
    chunk_errors: list[ChunkError] = Field(default_factory=list)
    filter_applied: str = ""


class UpdateRequirementRequest(BaseModel):
    """Payload PATCH /api/requirements/{id}/items/{idx}."""
    persyaratan: str | None = None
    referensi: str | None = None
    catatan: str | None = None
    status_gap: str | None = None


class AddRequirementRequest(BaseModel):
    """Payload POST /api/requirements/{id}/items."""
    persyaratan: str = ""
    referensi: str = ""
    catatan: str = ""
    status_gap: str = ""


class DeleteRequirementsRequest(BaseModel):
    """Payload DELETE /api/requirements/{id}/items."""
    item_indices: list[int] = Field(..., min_length=1)


class RequirementsBulkActionResponse(BaseModel):
    affected: int
    total_requirements: int

    # ---------------------------------------------------------------------------
# Prompt Editor
# ---------------------------------------------------------------------------

class PromptStatusResponse(BaseModel):
    """Response GET /api/prompts/{tool}."""
    tool: str
    default_core: str
    core_override: str | None = None
    core_is_customized: bool = False
    locked_block: str
    user_instructions: str = ""
    updated_at: str | None = None


class PromptUpdateRequest(BaseModel):
    """Payload PUT /api/prompts/{tool}."""
    core_override: str | None = None
    user_instructions: str | None = None


class PromptResetRequest(BaseModel):
    """Payload POST /api/prompts/{tool}/reset."""
    section: str = "all"   # "core" | "user" | "all"


class PromptPreviewResponse(BaseModel):
    """Response POST /api/prompts/{tool}/preview."""
    tool: str
    final_prompt: str
    total_chars: int

# ---------------------------------------------------------------------------
# Prompt Presets
# ---------------------------------------------------------------------------

class PromptPresetInfo(BaseModel):
    """Info 1 preset prompt."""
    id: str
    name: str
    description: str
    core_text: str


class PromptPresetsResponse(BaseModel):
    """Response GET /api/prompts/{tool}/presets."""
    tool: str
    presets: list[PromptPresetInfo]

# ---------------------------------------------------------------------------
# Search Global
# ---------------------------------------------------------------------------

class SearchResultItem(BaseModel):
    """1 hasil pencarian dari 1 item dalam 1 dokumen."""
    source: str                    # "regulation_audit" | "gap_analysis"
    result_id: str
    filename: str
    item_index: int
    # Field umum untuk preview
    title: str                     # ringkasan singkat (mis. point_ketentuan atau persyaratan)
    snippet: str                   # potongan teks dengan context query
    referensi: str = ""            # bab_pasal_ayat / referensi
    aspek: str = ""
    status: str = ""               # status_kepatuhan / status_gap
    created_at: str = ""           # ISO timestamp
    # Full item (untuk preview detail kalau diperlukan)
    raw_item: dict = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """Response GET /api/search."""
    query: str
    total: int
    results: list[SearchResultItem]
    # Ringkasan per dokumen
    by_document: dict[str, int] = Field(default_factory=dict)
    # Filter yang diterapkan
    tools_searched: list[str] = Field(default_factory=list)
    date_filter_days: int | None = None