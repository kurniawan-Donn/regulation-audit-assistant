"""
Phase 9 - Testing Menyeluruh: Filtering Ketentuan Non-TI.

Mencakup skenario testing wajib dari brief (section 17, Phase 9):
10. Requirement yang tidak relevan dengan audit TI
"""

from unittest.mock import patch

from app.services.ai_service import AIProvider
from app.services.audit_analyzer import analyze_chunk
from app.services.validator import validate_results


class _AlwaysNonRelevantProvider(AIProvider):
    """Mensimulasikan AI yang benar mengikuti instruksi: [] untuk ketentuan non-TI."""

    def generate_text(self, system_prompt, user_prompt, expect_json=False):
        return "[]"


def test_10_chunk_non_it_menghasilkan_list_kosong():
    chunk = {
        "bab": "BAB VII",
        "pasal": "Pasal 35",
        "ayat": "(1)",
        "text": "Pegawai berhak atas cuti tahunan paling sedikit 12 (dua belas) hari kerja.",
    }
    provider = _AlwaysNonRelevantProvider()

    result = analyze_chunk(chunk, provider)

    assert result == []


def test_10_validator_tidak_error_untuk_list_kosong():
    validated = validate_results([], source_text="teks apapun")
    assert validated == []


@patch("app.api.routes.analyze_chunks_batch")
def test_10_seluruh_dokumen_non_relevan_tetap_response_200(mock_analyze, client, sample_txt_path):
    """
    Kasus realistis: dokumen yang diupload ternyata tidak mengandung ketentuan
    TI sama sekali. Aplikasi HARUS tetap merespons normal (200) dengan
    total_ketentuan=0, BUKAN dianggap error.
    """
    mock_analyze.return_value = []

    with open(sample_txt_path, "rb") as f:
        res = client.post("/api/analyze", files={"file": ("sample_regulation.txt", f, "text/plain")})

    assert res.status_code == 200, res.text
    data = res.json()
    assert data["total_ketentuan"] == 0
    assert data["total_valid"] == 0
    assert data["total_flagged"] == 0
    assert data["chunk_errors"] == []
