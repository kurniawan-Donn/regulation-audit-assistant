"""
Manual test untuk Phase 3 - Regulation structure detection.

Cara pakai:
    python tests/manual_test_phase3.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.regulation_parser import parse_regulation_structure
from app.services.text_processor import clean_text, extract_txt_text

BASE_DIR = os.path.dirname(__file__)
SAMPLE_TXT = os.path.join(BASE_DIR, "sample_files", "sample_regulation.txt")


def print_section(title: str) -> None:
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def find_chunk(chunks, pasal_contains: str, ayat_equals: str | None = None):
    for c in chunks:
        if c["pasal"] and pasal_contains in c["pasal"]:
            if ayat_equals is None or c["ayat"] == ayat_equals:
                return c
    return None


def main() -> None:
    raw = extract_txt_text(SAMPLE_TXT)
    cleaned = clean_text(raw)

    print_section("TEST 1: Jumlah chunk terdeteksi")
    chunks = parse_regulation_structure(cleaned)
    print(f"Total chunk: {len(chunks)}")
    assert len(chunks) > 5, "Seharusnya ada beberapa chunk (preamble, tiap pasal/ayat)"
    print("OK")

    print_section("TEST 2: Ayat gaya 'Ayat (1)' di baris terpisah (Pasal 20)")
    c = find_chunk(chunks, "Pasal 20", "(1)")
    assert c is not None, "Chunk Pasal 20 ayat (1) harus ditemukan"
    assert c["bab"] == "BAB V", f"BAB salah: {c['bab']}"
    assert "kebijakan keamanan informasi" in c["text"]
    print(f"OK -> bab={c['bab']!r}, pasal={c['pasal']!r}, ayat={c['ayat']!r}")
    print(f"   text: {c['text'][:80]}...")

    print_section("TEST 3: Ayat gaya inline '(1) ...' dalam satu baris (Pasal 22)")
    c = find_chunk(chunks, "Pasal 22", "(1)")
    assert c is not None, "Chunk Pasal 22 ayat (1) harus ditemukan"
    assert "prosedur pengelolaan insiden" in c["text"]
    print(f"OK -> bab={c['bab']!r}, pasal={c['pasal']!r}, ayat={c['ayat']!r}")
    print(f"   text: {c['text'][:80]}...")

    print_section("TEST 4: Deteksi Huruf pada Pasal 21 ayat (2)")
    c = find_chunk(chunks, "Pasal 21", "(2)")
    assert c is not None, "Chunk Pasal 21 ayat (2) harus ditemukan"
    print(f"huruf terdeteksi: {c['huruf']}")
    assert c["huruf"] == ["a", "b", "c", "d"], f"Huruf tidak sesuai: {c['huruf']}"
    print("OK - huruf a, b, c, d terdeteksi dengan urutan benar")

    print_section("TEST 5: Pasal tanpa Ayat (Pasal 30) tetap satu chunk utuh")
    c = find_chunk(chunks, "Pasal 30")
    assert c is not None
    assert c["ayat"] is None, f"Pasal 30 seharusnya tidak punya ayat, dapat: {c['ayat']}"
    assert "31 Maret" in c["text"]
    print(f"OK -> pasal={c['pasal']!r}, ayat={c['ayat']!r}")

    print_section("TEST 6: Referensi asli tidak berubah (anti-hallucination check)")
    for c in chunks:
        if c["pasal"] and "Pasal 20" in c["pasal"]:
            assert c["pasal"] in cleaned, "Referensi pasal harus persis ada di teks sumber"
    print("OK - semua referensi pasal cocok persis dengan teks sumber")

    print_section("SEMUA TEST PHASE 3 SELESAI")
    print(f"\nRingkasan {len(chunks)} chunk pertama:")
    for i, c in enumerate(chunks[:6], start=1):
        print(f"{i}. bab={c['bab']} | pasal={c['pasal']} | ayat={c['ayat']} | huruf={c['huruf']}")


if __name__ == "__main__":
    main()
