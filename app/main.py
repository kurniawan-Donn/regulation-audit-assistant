"""
Regulation to IT Audit Assistant - Application Entry Point

Phase 7: root ("/") sekarang menyajikan halaman upload (templates/index.html),
menggantikan JSON status sederhana dari Phase 1. Endpoint status/JSON masih
tersedia di /health untuk keperluan monitoring.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as audit_router
from app.config import settings

app = FastAPI(
    title=settings.app_name,
    description=(
        "MVP untuk membantu auditor IT mengubah ketentuan regulasi "
        "menjadi prosedur pemeriksaan audit."
    ),
    version="0.1.0",
)

# --- Lokasi folder ---
# main.py berada di folder "app", jadi:
BASE_DIR = Path(__file__).resolve().parent          # folder app/
PROJECT_ROOT = BASE_DIR.parent                      # folder root proyek (satu tingkat di atas app)

# Folder static dan templates berada di root proyek (bukan di dalam app)
static_dir = PROJECT_ROOT / "static"
TEMPLATES_DIR = PROJECT_ROOT / "templates"

# Mount static folder
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(audit_router)


@app.get("/")
def read_root() -> FileResponse:
    """Menyajikan halaman upload utama."""
    return FileResponse(TEMPLATES_DIR / "index.html")


@app.get("/health")
def health_check() -> dict:
    """Endpoint health check sederhana untuk keperluan testing/monitoring."""
    return {
        "status": "ok",
        "env": settings.app_env,
    }