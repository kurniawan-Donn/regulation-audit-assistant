"""
AI Service - abstraksi provider AI.

Desain:

    AIProvider (abstract)
        |
        +-- GeminiProvider   <- dipakai sekarang

Nantinya provider lain (OpenAIProvider, AnthropicProvider, LocalLLMProvider)
tinggal dibuat sebagai subclass baru dari AIProvider tanpa mengubah kode
yang memanggilnya (routes.py, dsb. cukup memanggil get_ai_provider()).

Dua lapis retry yang berbeda tujuannya:
1. Retry jaringan (di dalam GeminiProvider.generate_text) - untuk error
   transient seperti timeout, service unavailable, rate limit.
2. Retry parsing (di dalam AIProvider.generate_json) - untuk kasus
   response AI berhasil didapat tapi bukan JSON valid.
"""

import json
import re
import time
from abc import ABC, abstractmethod
from typing import Any

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

from app.config import settings

# Error transient dari sisi Google yang layak di-retry di level jaringan.
_RETRYABLE_GOOGLE_EXCEPTIONS = (
    google_exceptions.DeadlineExceeded,
    google_exceptions.ServiceUnavailable,
    google_exceptions.ResourceExhausted,
    google_exceptions.InternalServerError,
    google_exceptions.TooManyRequests,
)


class AIProviderError(Exception):
    """Error umum saat memanggil AI provider (network, timeout, API error, dll)."""


class AIResponseParsingError(AIProviderError):
    """Response AI berhasil didapat tetapi tetap bukan JSON valid setelah semua retry."""


class AIProvider(ABC):
    """Kontrak yang wajib dipenuhi setiap provider AI."""

    @abstractmethod
    def generate_text(
        self, system_prompt: str, user_prompt: str, expect_json: bool = False
    ) -> str:
        """
        Kirim system prompt + user prompt ke AI, kembalikan raw text response.

        Args:
            system_prompt: instruksi peran/tugas AI.
            user_prompt: konten yang diminta untuk dianalisis.
            expect_json: jika True, provider yang mendukung "JSON mode"
                native (seperti Gemini) akan memaksa output berupa JSON.

        Raises:
            AIProviderError: jika request gagal (timeout, API error, dsb.)
                setelah seluruh retry jaringan habis.
        """
        raise NotImplementedError

    def generate_json(
        self, system_prompt: str, user_prompt: str, max_retries: int = 2
    ) -> Any:
        """
        Sama seperti generate_text(), tapi hasilnya di-parse menjadi
        object Python (list/dict) hasil json.loads().

        Jika hasil bukan JSON valid, prompt akan dikirim ulang dengan
        peringatan tambahan, maksimal `max_retries` kali.

        Raises:
            AIResponseParsingError: jika tetap gagal setelah semua retry.
            AIProviderError: jika request ke AI sendiri gagal (bukan soal parsing).
        """
        current_user_prompt = user_prompt
        last_parse_error: Exception | None = None

        for attempt in range(max_retries + 1):
            raw_text = self.generate_text(
                system_prompt, current_user_prompt, expect_json=True
            )
            try:
                return _parse_json_response(raw_text)
            except (json.JSONDecodeError, ValueError) as exc:
                last_parse_error = exc
                current_user_prompt = (
                    f"{user_prompt}\n\n"
                    "PERINGATAN: Response Anda sebelumnya BUKAN JSON valid. "
                    "Keluarkan HANYA JSON valid, tanpa markdown code fence, "
                    "tanpa penjelasan tambahan di luar JSON."
                )

        raise AIResponseParsingError(
            f"Gagal mendapatkan JSON valid dari AI setelah {max_retries + 1} "
            f"percobaan. Error parsing terakhir: {last_parse_error}"
        )


def _parse_json_response(raw_text: str) -> Any:
    """Bersihkan markdown code fence (jika ada) lalu parse sebagai JSON."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    if not text:
        raise ValueError("Response AI kosong.")
    return json.loads(text)


class GeminiProvider(AIProvider):
    """Implementasi AIProvider menggunakan Google Gemini API."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        timeout_seconds: int = 60,
        max_network_retries: int = 2,
        retry_backoff_seconds: float = 2.0,
        max_output_tokens: int | None = None,
        min_seconds_between_requests: float | None = None,
    ) -> None:
        self._api_key = api_key or settings.gemini_api_key
        self._model_name = model_name or settings.gemini_model
        self._timeout_seconds = timeout_seconds
        self._max_network_retries = max_network_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._max_output_tokens = (
            max_output_tokens if max_output_tokens is not None else settings.gemini_max_output_tokens
        )
        self._min_seconds_between_requests = (
            min_seconds_between_requests
            if min_seconds_between_requests is not None
            else settings.gemini_min_seconds_between_requests
        )
        self._last_request_time: float = 0.0

        if not self._api_key:
            raise ValueError(
                "GEMINI_API_KEY belum diset. Isi nilainya pada file .env "
                "(lihat .env.example)."
            )

        genai.configure(api_key=self._api_key)

    def _wait_for_rate_limit(self) -> None:
        """
        Jeda otomatis sebelum tiap request, supaya jarak antar-request ke
        Gemini tidak lebih rapat dari `min_seconds_between_requests`.

        Ini pengaman terhadap limit RPM (requests per minute) free tier -
        berlaku baik dipanggil untuk 1 chunk maupun banyak batch berturutan
        dalam satu request /api/analyze.
        """
        if self._min_seconds_between_requests <= 0:
            return
        elapsed = time.time() - self._last_request_time
        remaining = self._min_seconds_between_requests - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def generate_text(
        self, system_prompt: str, user_prompt: str, expect_json: bool = False
    ) -> str:
        model = genai.GenerativeModel(
            model_name=self._model_name,
            system_instruction=system_prompt,
        )

        generation_config: dict[str, Any] = {
            "temperature": 0,
            "max_output_tokens": self._max_output_tokens,
        }
        if expect_json:
            generation_config["response_mime_type"] = "application/json"

        last_error: Exception | None = None

        for attempt in range(self._max_network_retries + 1):
            self._wait_for_rate_limit()
            try:
                response = model.generate_content(
                    user_prompt,
                    generation_config=generation_config,
                    request_options={"timeout": self._timeout_seconds},
                )
                self._last_request_time = time.time()
                return _extract_text_from_response(response)

            except _RETRYABLE_GOOGLE_EXCEPTIONS as exc:
                self._last_request_time = time.time()
                last_error = exc
                if attempt < self._max_network_retries:
                    time.sleep(self._retry_backoff_seconds * (attempt + 1))
                    continue
                raise AIProviderError(
                    f"Gemini API gagal setelah {attempt + 1} percobaan "
                    f"(timeout/unavailable/rate limit): {exc}"
                ) from exc

            except AIProviderError:
                raise

            except Exception as exc:
                self._last_request_time = time.time()
                # Error non-transient (mis. API key tidak valid, request
                # diblokir kebijakan konten, dsb.) - tidak perlu di-retry.
                raise AIProviderError(f"Gagal memanggil Gemini API: {exc}") from exc

        # Seharusnya tidak pernah sampai sini, tapi jaga-jaga.
        raise AIProviderError(f"Gemini API gagal: {last_error}")


def _extract_text_from_response(response: Any) -> str:
    """Ambil teks dari response Gemini, dengan pesan error yang jelas jika gagal."""
    if not getattr(response, "candidates", None):
        feedback = getattr(response, "prompt_feedback", None)
        raise AIProviderError(
            "Gemini tidak mengembalikan kandidat response. Kemungkinan "
            f"konten diblokir oleh safety filter. Detail: {feedback}"
        )
    try:
        return response.text
    except Exception as exc:
        raise AIProviderError(
            f"Gagal membaca teks dari response Gemini: {exc}"
        ) from exc


def get_ai_provider() -> AIProvider:
    """
    Factory function - satu-satunya tempat yang perlu diubah jika provider
    AI diganti di kemudian hari (misalnya ke OpenAIProvider).
    """
    return GeminiProvider()
