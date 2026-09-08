"""
Manual test untuk Phase 4 - Gemini integration.

PENTING: Test ini TIDAK memanggil Gemini API sungguhan (tidak butuh
API key asli, tidak butuh koneksi internet ke Google). Semua panggilan
ke `genai.GenerativeModel` di-mock, supaya logic retry & error handling
bisa diuji secara deterministik tanpa bergantung pada layanan eksternal.

Untuk uji coba dengan Gemini API SUNGGUHAN, isi GEMINI_API_KEY di .env
lalu jalankan skrip terpisah (lihat catatan di akhir file ini).

Cara pakai:
    python tests/manual_test_phase4.py
"""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.api_core import exceptions as google_exceptions

from app.config import settings
from app.services.ai_service import (
    AIProvider,
    AIProviderError,
    AIResponseParsingError,
    GeminiProvider,
    _parse_json_response,
)


def print_section(title: str) -> None:
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def test_parse_json_response() -> None:
    print_section("TEST 1: _parse_json_response()")

    assert _parse_json_response('[{"a": 1}]') == [{"a": 1}]
    print("OK - JSON polos berhasil di-parse")

    assert _parse_json_response('```json\n[{"a": 1}]\n```') == [{"a": 1}]
    print("OK - JSON yang dibungkus markdown code fence berhasil di-parse")

    try:
        _parse_json_response("ini bukan json sama sekali")
        raise AssertionError("Seharusnya raise error untuk teks bukan JSON")
    except Exception as exc:
        print(f"OK - error ter-raise dengan benar untuk teks invalid: {type(exc).__name__}")


def test_gemini_provider_requires_api_key() -> None:
    print_section("TEST 2: GeminiProvider wajib API key")
    # Patch settings.gemini_api_key ke kosong juga, karena GeminiProvider
    # fallback ke settings saat api_key eksplisit tidak diberikan/kosong.
    with patch.object(settings, "gemini_api_key", ""):
        try:
            GeminiProvider(api_key="")
            raise AssertionError("Seharusnya raise ValueError jika api_key kosong")
        except ValueError as exc:
            print(f"OK - ValueError ter-raise: {exc}")


class _FakeProvider(AIProvider):
    """Provider palsu untuk menguji retry logic generate_json() tanpa API asli."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls = 0

    def generate_text(self, system_prompt: str, user_prompt: str, expect_json: bool = False) -> str:
        self.calls += 1
        return self._responses.pop(0)


def test_generate_json_retry_success() -> None:
    print_section("TEST 3: generate_json() retry lalu berhasil")
    provider = _FakeProvider(["ini bukan json", '{"ok": true}'])
    result = provider.generate_json("system", "user", max_retries=2)
    assert result == {"ok": True}
    assert provider.calls == 2
    print(f"OK - berhasil parse JSON setelah {provider.calls} percobaan")


def test_generate_json_retry_exhausted() -> None:
    print_section("TEST 4: generate_json() gagal terus -> AIResponseParsingError")
    provider = _FakeProvider(["bukan json"] * 5)
    try:
        provider.generate_json("system", "user", max_retries=2)
        raise AssertionError("Seharusnya raise AIResponseParsingError")
    except AIResponseParsingError:
        assert provider.calls == 3  # percobaan awal + 2 retry
        print(f"OK - AIResponseParsingError ter-raise setelah {provider.calls} percobaan")


@patch("app.services.ai_service.genai.GenerativeModel")
def test_gemini_network_retry_then_success(mock_model_class: MagicMock) -> None:
    print_section("TEST 5: GeminiProvider retry jaringan lalu berhasil (mocked)")

    fake_response = MagicMock()
    fake_response.candidates = [MagicMock()]
    fake_response.text = "Halo dari Gemini"

    mock_model_class.return_value.generate_content.side_effect = [
        google_exceptions.DeadlineExceeded("simulated timeout"),
        fake_response,
    ]

    provider = GeminiProvider(api_key="fake-key-for-test", retry_backoff_seconds=0)
    result = provider.generate_text("system prompt", "user prompt")

    assert result == "Halo dari Gemini"
    assert mock_model_class.return_value.generate_content.call_count == 2
    print("OK - percobaan 1 DeadlineExceeded, percobaan 2 berhasil, hasil akhir benar")


@patch("app.services.ai_service.genai.GenerativeModel")
def test_gemini_network_retry_exhausted(mock_model_class: MagicMock) -> None:
    print_section("TEST 6: GeminiProvider retry jaringan habis -> AIProviderError (mocked)")

    mock_model_class.return_value.generate_content.side_effect = google_exceptions.ServiceUnavailable(
        "simulated outage"
    )

    provider = GeminiProvider(
        api_key="fake-key-for-test", max_network_retries=2, retry_backoff_seconds=0
    )
    try:
        provider.generate_text("system", "user")
        raise AssertionError("Seharusnya raise AIProviderError")
    except AIProviderError as exc:
        call_count = mock_model_class.return_value.generate_content.call_count
        assert call_count == 3  # percobaan awal + 2 retry
        print(f"OK - AIProviderError ter-raise setelah {call_count} percobaan: {exc}")


@patch("app.services.ai_service.genai.GenerativeModel")
def test_gemini_blocked_response(mock_model_class: MagicMock) -> None:
    print_section("TEST 7: Response Gemini kosong/diblokir safety filter (mocked)")

    fake_response = MagicMock()
    fake_response.candidates = []
    fake_response.prompt_feedback = "BLOCK_REASON_SAFETY (simulasi)"
    mock_model_class.return_value.generate_content.return_value = fake_response

    provider = GeminiProvider(api_key="fake-key-for-test")
    try:
        provider.generate_text("system", "user")
        raise AssertionError("Seharusnya raise AIProviderError untuk response kosong")
    except AIProviderError as exc:
        print(f"OK - AIProviderError ter-raise untuk response yang diblokir: {exc}")


if __name__ == "__main__":
    test_parse_json_response()
    test_gemini_provider_requires_api_key()
    test_generate_json_retry_success()
    test_generate_json_retry_exhausted()
    test_gemini_network_retry_then_success()
    test_gemini_network_retry_exhausted()
    test_gemini_blocked_response()
    print_section("SEMUA TEST PHASE 4 SELESAI (tanpa memanggil Gemini API asli)")

# ---------------------------------------------------------------------------
# CATATAN: Untuk uji coba dengan Gemini API SUNGGUHAN:
#
#   1. Isi GEMINI_API_KEY di file .env dengan API key asli dari
#      https://aistudio.google.com/app/apikey
#   2. Jalankan potongan kode berikut secara terpisah:
#
#       from app.services.ai_service import get_ai_provider
#       provider = get_ai_provider()
#       print(provider.generate_text("Anda adalah asisten AI.", "Halo, siapa kamu?"))
#
#   Ini sengaja tidak dijadikan bagian dari manual_test_phase4.py agar
#   test ini tidak gagal/butuh biaya API hanya karena API key belum diisi.
# ---------------------------------------------------------------------------
