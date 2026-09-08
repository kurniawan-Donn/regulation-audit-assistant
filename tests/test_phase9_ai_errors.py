"""
Phase 9 - Testing Menyeluruh: Error Handling AI.

Mencakup skenario testing wajib dari brief (section 17, Phase 9):
7. AI timeout
8. API error
9. Invalid JSON dari AI

Semua di-mock (tidak memanggil Gemini API sungguhan) supaya deterministik
dan tidak butuh API key/network untuk dijalankan sebagai bagian test suite.
"""

from unittest.mock import patch

import pytest
from google.api_core import exceptions as google_exceptions

from app.services.ai_service import (
    AIProvider,
    AIProviderError,
    AIResponseParsingError,
    GeminiProvider,
)


@patch("app.services.ai_service.genai.GenerativeModel")
def test_7_ai_timeout_habiskan_retry_lalu_error(mock_model_class):
    mock_model_class.return_value.generate_content.side_effect = google_exceptions.DeadlineExceeded(
        "simulasi timeout"
    )
    provider = GeminiProvider(api_key="fake-key", max_network_retries=1, retry_backoff_seconds=0)

    with pytest.raises(AIProviderError):
        provider.generate_text("system", "user")

    # 1 percobaan awal + 1 retry = 2 panggilan
    assert mock_model_class.return_value.generate_content.call_count == 2


@patch("app.services.ai_service.genai.GenerativeModel")
def test_8_api_error_non_retryable_langsung_gagal(mock_model_class):
    """Error non-transient (mis. API key ditolak) TIDAK boleh di-retry, harus langsung gagal."""
    mock_model_class.return_value.generate_content.side_effect = google_exceptions.PermissionDenied(
        "simulasi API key ditolak"
    )
    provider = GeminiProvider(api_key="fake-key", max_network_retries=2, retry_backoff_seconds=0)

    with pytest.raises(AIProviderError):
        provider.generate_text("system", "user")

    # Error non-transient -> tidak boleh retry -> hanya 1 kali panggilan
    assert mock_model_class.return_value.generate_content.call_count == 1


def test_9_invalid_json_habiskan_retry_lalu_error():
    class _AlwaysBadJSON(AIProvider):
        def __init__(self):
            self.call_count = 0

        def generate_text(self, system_prompt, user_prompt, expect_json=False):
            self.call_count += 1
            return "ini teks biasa, bukan JSON sama sekali"

    provider = _AlwaysBadJSON()

    with pytest.raises(AIResponseParsingError):
        provider.generate_json("system", "user", max_retries=2)

    assert provider.call_count == 3  # percobaan awal + 2 retry


@patch("app.api.routes.analyze_chunks_batch")
def test_ai_error_di_satu_chunk_tidak_menggagalkan_seluruh_request(mock_analyze, client, sample_txt_path):
    """Kombinasi skenario 7/8: error AI di satu chunk harus tercatat di chunk_errors, bukan bikin 500."""
    mock_analyze.side_effect = AIProviderError("simulasi Gemini down")

    with open(sample_txt_path, "rb") as f:
        res = client.post("/api/analyze", files={"file": ("sample_regulation.txt", f, "text/plain")})

    assert res.status_code == 200, res.text
    data = res.json()
    assert data["total_ketentuan"] == 0
    assert len(data["chunk_errors"]) > 0
    assert all("simulasi Gemini down" in e["error"] for e in data["chunk_errors"])
