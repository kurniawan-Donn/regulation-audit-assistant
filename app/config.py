"""
Application configuration.

Semua nilai dibaca dari environment variable (.env).
Modul ini menjadi satu-satunya sumber konfigurasi agar tidak ada
nilai konfigurasi yang tersebar di banyak file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Regulation to IT Audit Assistant"
    app_env: str = "development"
    debug: bool = True

    # AI provider - akan dipakai mulai Phase 4
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.7-flash"
    gemini_max_output_tokens: int = 8192
    # Jarak minimum antar-request ke Gemini (detik), untuk menjaga RPM
    # free tier tidak terlampaui. Default 4.5s -> aman untuk ~13 RPM.
    gemini_min_seconds_between_requests: float = 4.5

    # Batching - Phase 11: gabungkan banyak chunk kecil jadi sedikit request
    # untuk mengatasi limit RPD/RPM (bukan TPM, yang biasanya masih longgar).
    max_chars_per_batch: int = 6000

    # Upload settings - akan dipakai mulai Phase 2
    max_upload_size_mb: int = 20

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Singleton settings instance, di-import oleh modul lain
settings = Settings()
