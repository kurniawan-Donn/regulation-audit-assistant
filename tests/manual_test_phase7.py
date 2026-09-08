import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services.ai_service import AIProviderError

client = TestClient(app)

SAMPLE_TXT_PATH = os.path.join(os.path.dirname(__file__), "sample_files", "sample_regulation.txt")
SAMPLE_PDF_PATH = os.path.join(os.path.dirname(__file__), "sample_files", "sample_regulation.pdf")


def fake_analyze_chunks_batch(chunks, provider, referensi_regulasi=""):
    """
    Mensimulasikan AI di level BATCH (Phase 11): kalau batch mengandung
    chunk Pasal 22, seluruh batch itu gagal (timeout). Kalau mengandung
    chunk Pasal 20, hasilkan 1 item relevan per chunk tsb. Chunk lain
    dianggap tidak relevan dengan audit TI ([]).
    """
    for chunk in chunks:
        if "Pasal 22" in (chunk.get("pasal") or ""):
            raise AIProviderError("Simulated Gemini timeout")

    results = []
    for chunk in chunks:
        if "Pasal 20" in (chunk.get("pasal") or ""):
            results.append({
                "referensi_regulasi": referensi_regulasi,
                "bab_pasal_ayat": f"{chunk.get('bab')} - {chunk.get('pasal')} - {chunk.get('ayat')}",
                "point_ketentuan": "Contoh ketentuan relevan",
                "pemeriksaan": "Periksa contoh prosedur pemeriksaan.",
            })
    return results


def fake_analyze_chunks_batch_no_errors(chunks, provider, referensi_regulasi=""):
    """Sama seperti di atas tapi TANPA simulasi error, untuk menguji efisiensi batching murni."""
    return [
        {
            "referensi_regulasi": referensi_regulasi,
            "bab_pasal_ayat": f"{c.get('bab')} - {c.get('pasal')} - {c.get('ayat')}",
            "point_ketentuan": "Contoh ketentuan relevan",
            "pemeriksaan": "Periksa contoh prosedur pemeriksaan.",
        }
        for c in chunks
        if "Pasal 20" in (c.get("pasal") or "")
    ]


def print_section(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def test_root_serves_html():
    print_section("TEST 1: GET / menyajikan halaman upload")
    res = client.get("/")
    assert res.status_code == 200
    assert "REGULATION TO IT AUDIT ASSISTANT" in res.text.upper()
    assert "Analisis Regulasi" in res.text
    print("OK - halaman upload tersaji dengan benar")


def test_health():
    print_section("TEST 2: GET /health")
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    print("OK -", res.json())


@patch("app.api.routes.analyze_chunks_batch", side_effect=fake_analyze_chunks_batch)
def test_analyze_txt_success(mock_analyze):
    print_section("TEST 3: POST /api/analyze dengan file TXT (AI di-mock, batch dipaksa kecil)")
    # Paksa max_chars_per_batch kecil supaya tiap Pasal jadi batch sendiri-sendiri,
    # sehingga skenario "Pasal 22 gagal, Pasal 20 tetap berhasil" bisa diuji granular.
    with patch.object(settings, "max_chars_per_batch", 10):
        with open(SAMPLE_TXT_PATH, "rb") as f:
            res = client.post(
                "/api/analyze",
                files={"file": ("sample_regulation.txt", f, "text/plain")},
                data={"nama_regulasi": "PERATURAN CONTOH 01/2026"},
            )

    assert res.status_code == 200, res.text
    data = res.json()
    print(f"total_chunks={data['total_chunks']}, total_batches={data['total_batches']}, "
          f"total_ketentuan={data['total_ketentuan']}, total_valid={data['total_valid']}, "
          f"total_flagged={data['total_flagged']}, chunk_errors={len(data['chunk_errors'])}")

    assert data["total_ketentuan"] >= 1, "Harus ada minimal 1 ketentuan relevan (dari Pasal 20)"
    assert len(data["chunk_errors"]) == 2, "Pasal 22 ayat (1) dan (2) seharusnya tercatat sebagai chunk_errors"
    assert all("Pasal 22" in (e["pasal"] or "") for e in data["chunk_errors"])
    assert all(r["referensi_regulasi"] == "PERATURAN CONTOH 01/2026" for r in data["results"])
    assert data["total_valid"] >= 1, "Referensi Pasal 20 ada di dokumen -> seharusnya valid, bukan flagged"
    print("OK - hasil relevan muncul dan VALID, error Pasal 22 tercatat tanpa menggagalkan request")
    return data["result_id"]


@patch("app.api.routes.analyze_chunks_batch", side_effect=fake_analyze_chunks_batch_no_errors)
def test_analyze_pdf_success(mock_analyze):
    print_section("TEST 4: POST /api/analyze dengan file PDF (AI di-mock, batch besar/default)")
    with open(SAMPLE_PDF_PATH, "rb") as f:
        res = client.post(
            "/api/analyze",
            files={"file": ("sample_regulation.pdf", f, "application/pdf")},
        )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["total_ketentuan"] >= 1
    # Dokumen sample kecil -> dengan max_chars_per_batch default (6000), semua
    # chunk relevan seharusnya masuk dalam SATU batch saja -> hemat request.
    assert data["total_batches"] == 1, f"Diharapkan 1 batch untuk dokumen kecil, dapat: {data['total_batches']}"
    # nama_regulasi tidak diisi -> fallback ke nama file (tanpa ekstensi)
    assert data["results"][0]["referensi_regulasi"] == "sample_regulation"
    print(f"OK - PDF diproses dalam {data['total_batches']} pemanggilan API saja "
          f"(sebelumnya: {data['total_chunks']} chunk = {data['total_chunks']} request)")


def test_analyze_rejects_wrong_extension():
    print_section("TEST 5: Tolak ekstensi file yang tidak didukung")
    res = client.post(
        "/api/analyze",
        files={"file": ("dokumen.docx", b"isi apa saja", "application/octet-stream")},
    )
    assert res.status_code == 400
    assert ".docx" in res.json()["detail"]
    print("OK - file .docx ditolak dengan pesan yang jelas:", res.json()["detail"])


def test_analyze_rejects_empty_file():
    print_section("TEST 6: Tolak file kosong")
    res = client.post(
        "/api/analyze",
        files={"file": ("kosong.txt", b"", "text/plain")},
    )
    assert res.status_code == 400
    assert "kosong" in res.json()["detail"].lower()
    print("OK - file kosong ditolak:", res.json()["detail"])


@patch("app.api.routes.analyze_chunks_batch", side_effect=fake_analyze_chunks_batch)
def test_get_results_roundtrip(mock_analyze):
    print_section("TEST 7: GET /api/results/{id} mengembalikan hasil yang sama")
    with open(SAMPLE_TXT_PATH, "rb") as f:
        post_res = client.post("/api/analyze", files={"file": ("sample_regulation.txt", f, "text/plain")})
    result_id = post_res.json()["result_id"]

    get_res = client.get(f"/api/results/{result_id}")
    assert get_res.status_code == 200
    assert get_res.json()["result_id"] == result_id
    assert get_res.json()["total_ketentuan"] == post_res.json()["total_ketentuan"]
    print(f"OK - hasil untuk result_id={result_id} berhasil diambil ulang")


def test_get_results_not_found():
    print_section("TEST 8: GET /api/results/{id} yang tidak ada -> 404")
    res = client.get("/api/results/tidak-ada-id-ini")
    assert res.status_code == 404
    print("OK - 404 untuk result_id yang tidak ditemukan")


if __name__ == "__main__":
    test_root_serves_html()
    test_health()
    result_id = test_analyze_txt_success()
    test_analyze_pdf_success()
    test_analyze_rejects_wrong_extension()
    test_analyze_rejects_empty_file()
    test_get_results_roundtrip()
    test_get_results_not_found()
    print_section("SEMUA TEST PHASE 7 SELESAI")
