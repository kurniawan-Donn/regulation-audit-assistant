"""
Prompt Manager — simpan & baca override prompt dari user.

Storage: data/prompts.json
Struktur:
{
  "regulation_audit": {
    "core_override": "...(teks user, null kalau belum pernah edit)...",
    "user_instructions": "...(teks user, bisa kosong)...",
    "updated_at": "2025-01-15T10:30:00Z"
  },
  "gap_analysis": {
    "core_override": null,
    "user_instructions": ""
  }
}
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
PROMPTS_FILE = DATA_DIR / "prompts.json"

SUPPORTED_TOOLS = ("regulation_audit", "gap_analysis")

MAX_CORE_OVERRIDE_CHARS = 20000
MAX_USER_INSTR_CHARS = 5000
MIN_CORE_OVERRIDE_CHARS = 50


def _empty_store() -> dict:
    return {
        tool: {
            "core_override": None,
            "user_instructions": "",
            "updated_at": None,
        }
        for tool in SUPPORTED_TOOLS
    }


def _ensure_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_store() -> dict:
    _ensure_dir()
    if not PROMPTS_FILE.exists():
        return _empty_store()
    try:
        data = json.loads(PROMPTS_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Gagal baca prompts.json: %s. Pakai default.", exc)
        return _empty_store()

    # Merge dengan skema default (kalau ada field baru)
    base = _empty_store()
    for tool in SUPPORTED_TOOLS:
        if tool in data and isinstance(data[tool], dict):
            base[tool].update({
                "core_override": data[tool].get("core_override"),
                "user_instructions": data[tool].get("user_instructions", ""),
                "updated_at": data[tool].get("updated_at"),
            })
    return base


def _save_store(store: dict) -> None:
    _ensure_dir()
    PROMPTS_FILE.write_text(
        json.dumps(store, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_user_override(tool: str) -> dict:
    """
    Ambil override untuk tool tertentu.
    Return dict {core_override, user_instructions, updated_at}.
    Kalau tool tidak dikenal, return dict kosong.
    """
    if tool not in SUPPORTED_TOOLS:
        return {"core_override": None, "user_instructions": "", "updated_at": None}
    store = _load_store()
    return store[tool]


def _sanitize_text(text: str, max_chars: int) -> str:
    """Bersihkan input user: trim + batasi panjang."""
    if not isinstance(text, str):
        return ""
    text = text.strip()
    if len(text) > max_chars:
        text = text[:max_chars]
    return text


def update_prompt(
    tool: str,
    core_override: str | None = None,
    user_instructions: str | None = None,
) -> dict:
    """
    Update prompt override untuk tool.

    - core_override: None = tidak diubah; "" = reset ke default (None);
      string = set override baru
    - user_instructions: None = tidak diubah; string = set baru (bisa kosong)

    Return: dict override setelah update.
    """
    if tool not in SUPPORTED_TOOLS:
        raise ValueError(f"Tool '{tool}' tidak dikenal.")

    store = _load_store()
    current = store[tool]

    if core_override is not None:
        cleaned = _sanitize_text(core_override, MAX_CORE_OVERRIDE_CHARS)
        if len(cleaned) < MIN_CORE_OVERRIDE_CHARS:
            # Kalau terlalu pendek, anggap reset ke default
            cleaned = None
        current["core_override"] = cleaned

    if user_instructions is not None:
        cleaned = _sanitize_text(user_instructions, MAX_USER_INSTR_CHARS)
        current["user_instructions"] = cleaned

    current["updated_at"] = datetime.now(timezone.utc).isoformat()
    store[tool] = current
    _save_store(store)
    return current


def reset_prompt(tool: str, section: str = "all") -> dict:
    """
    Reset prompt ke default.

    section:
    - "core"    → reset core_override saja
    - "user"    → reset user_instructions saja
    - "all"     → reset keduanya
    """
    if tool not in SUPPORTED_TOOLS:
        raise ValueError(f"Tool '{tool}' tidak dikenal.")

    store = _load_store()
    current = store[tool]

    if section in ("core", "all"):
        current["core_override"] = None
    if section in ("user", "all"):
        current["user_instructions"] = ""

    current["updated_at"] = datetime.now(timezone.utc).isoformat()
    store[tool] = current
    _save_store(store)
    return current


def get_default_core(tool: str) -> str:
    """Ambil default core prompt untuk tool tertentu (dari module .py)."""
    if tool == "regulation_audit":
        from app.prompts.regulation_audit_prompt import CORE_PROMPT_DEFAULT
        return CORE_PROMPT_DEFAULT
    if tool == "gap_analysis":
        from app.prompts.requirements_prompt import CORE_PROMPT_DEFAULT
        return CORE_PROMPT_DEFAULT
    return ""


def get_locked_block(tool: str) -> str:
    """Ambil blok locked untuk tool tertentu."""
    if tool == "regulation_audit":
        from app.prompts.regulation_audit_prompt import get_locked_block as _f
        return _f()
    if tool == "gap_analysis":
        from app.prompts.requirements_prompt import LOCKED_BLOCK
        return LOCKED_BLOCK
    return ""


def get_full_status(tool: str) -> dict:
    """
    Return status lengkap untuk frontend:
    - default_core: prompt core default (dari .py)
    - core_override: override user (null kalau belum diedit)
    - core_is_customized: bool
    - locked_block: blok locked (read-only)
    - user_instructions: teks user
    - updated_at
    """
    override = get_user_override(tool)
    default_core = get_default_core(tool)
    locked = get_locked_block(tool)

    return {
        "tool": tool,
        "default_core": default_core,
        "core_override": override.get("core_override"),
        "core_is_customized": override.get("core_override") is not None,
        "locked_block": locked,
        "user_instructions": override.get("user_instructions") or "",
        "updated_at": override.get("updated_at"),
    }


def preview_final_prompt(tool: str) -> str:
    """Bangun prompt final (yang akan dikirim ke AI) untuk preview."""
    if tool == "regulation_audit":
        from app.prompts.regulation_audit_prompt import build_system_prompt
        return build_system_prompt()
    if tool == "gap_analysis":
        from app.prompts.requirements_prompt import build_system_prompt
        return build_system_prompt()
    return ""