"""
Cost Estimator — perkiraan biaya + waktu sebelum analisis AI.

Asumsi:
- Rata-rata 4 karakter per token (teks Indonesia formal)
- System prompt (~2500 token) dikirim ulang di setiap batch
- Output ≈ 25% dari input (JSON dengan 7 field per item)
- Waktu = batch × (delay rate-limit + 8 detik processing)
"""

from dataclasses import dataclass

from app.config import settings

CHARS_PER_TOKEN = 4.0
OUTPUT_TO_INPUT_RATIO = 0.25
SYSTEM_PROMPT_TOKENS = 2500
SECONDS_PER_BATCH_PROCESSING = 8


@dataclass
class CostEstimate:
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


def estimate(chunks: list[dict]) -> CostEstimate:
    """Estimasi biaya & waktu untuk menganalisis `chunks`."""
    if not chunks:
        return CostEstimate(
            total_chunks=0, total_chars=0, estimated_batches=0,
            input_tokens=0, output_tokens=0, total_tokens=0,
            cost_usd=0.0, cost_idr=0.0, time_seconds_estimate=0,
            model_name=settings.gemini_model,
        )

    max_chars = settings.max_chars_per_batch
    total_chars = sum(len(c.get("text", "")) for c in chunks)

    # Hitung jumlah batch (mengikuti logika chunk_batcher.create_batches)
    batches = 1
    current = 0
    for c in chunks:
        size = len(c.get("text", ""))
        if current and current + size > max_chars:
            batches += 1
            current = 0
        current += size

    content_tokens = int(total_chars / CHARS_PER_TOKEN)
    # System prompt diulang di setiap batch
    input_tokens = content_tokens + (SYSTEM_PROMPT_TOKENS * batches)
    output_tokens = int(content_tokens * OUTPUT_TO_INPUT_RATIO) + (200 * batches)

    cost_usd = (
        (input_tokens / 1_000_000) * settings.gemini_input_price_per_1m_usd
        + (output_tokens / 1_000_000) * settings.gemini_output_price_per_1m_usd
    )
    cost_idr = cost_usd * settings.usd_to_idr

    time_seconds = int(
        batches * (settings.gemini_min_seconds_between_requests + SECONDS_PER_BATCH_PROCESSING)
    )

    return CostEstimate(
        total_chunks=len(chunks),
        total_chars=total_chars,
        estimated_batches=batches,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        cost_usd=round(cost_usd, 4),
        cost_idr=round(cost_idr, 2),
        time_seconds_estimate=time_seconds,
        model_name=settings.gemini_model,
    )