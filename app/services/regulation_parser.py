"""
Regulation Structure Parser — State Machine.

DESAIN:
- Setiap baris dicek terhadap sekumpulan regex terurut (prioritas).
- Kalau match → transisi state (set field bab/bagian/pasal/ayat/butir).
- Kalau tidak match → masuk buffer konten.
- Buffer di-flush jadi chunk setiap ada heading baru.

DETERMINISTIK: input sama → output sama. Tidak ada "melihat 5 baris ke belakang".

POST-FILTER:
Setelah parsing, dua jenis chunk dibuang:
1. Cover page (mengandung "SALINAN PERATURAN", "MEMUTUSKAN", dll.)
2. Daftar Isi (density pola nomor halaman tinggi).
"""

import re
from typing import Optional, TypedDict

# ===== Page marker dari pdf_parser =====
_PAGE_MARKER = re.compile(r"^@@PAGE_(\d+)@@$")

# ===== H marker dari pdf_parser (dipakai sebagai "boost" fallback) =====
_H_MARKER = re.compile(r"^@@H@@\s+(.*)$")

# =============================================================================
# PATTERN UNTUK KLASIFIKASI HEADING (urutan prioritas penting!)
# =============================================================================

# Prioritas 1: LAMPIRAN X (HANYA huruf besar)
_P_LAMPIRAN = re.compile(r"^LAMPIRAN\s+([IVXLCDM]+)\b")

# Prioritas 2: BAB X (sendiri di baris)
_P_BAB_ONLY = re.compile(r"^BAB\s+([IVXLCDM]+)\s*$", re.IGNORECASE)
# BAB X JUDUL (inline)
_P_BAB_INLINE = re.compile(r"^BAB\s+([IVXLCDM]+)\s+(\S.+)$", re.IGNORECASE)

# Prioritas 3: I. JUDUL / II. JUDUL (Roman + kapital) — untuk PADK Lampiran
_P_ROMAN = re.compile(r"^([IVXLCDM]+)\.\s+(\S.*)$")

# Prioritas 4: Bagian Kesatu / Bagian Pertama
_P_BAGIAN_KATA = re.compile(r"^Bagian\s+\S+", re.IGNORECASE)

# Prioritas 5: A. JUDUL (Huruf kapital + titik + kapital)
_P_LETTER_UPPER = re.compile(r"^([A-Z])\.\s+(\S.*)$")

# Prioritas 6: Pasal X (POJK gaya klasik)
_P_PASAL = re.compile(r"^Pasal\s+\d+[A-Za-z]?\b", re.IGNORECASE)

# Prioritas 7: 1. JUDUL (angka + titik + kapital) — heading
_P_NUMBER_HEADING = re.compile(r"^(\d+)\.\s+([A-Z].*)$")

# Prioritas 8: (1) / Ayat (1) — ayat
_P_AYAT = re.compile(r"^(?:Ayat\s*)?\((\d+[a-zA-Z]?)\)\s*(.*)$", re.IGNORECASE)

# Prioritas 9: a. teks — butir (lowercase)
_P_BUTIR = re.compile(r"^([a-z])\.\s+(.+)$")

# Pola NEGATIF: cek apa "1. X" adalah konten list, bukan heading
_P_NUMBER_LIST = re.compile(r"^\d+\.\s+[a-z]")

# Batas panjang maksimum untuk judul heading (hindari paragraf panjang)
_MAX_HEADING_LEN = 150


class RegulationChunk(TypedDict):
    lampiran: Optional[str]
    bab: Optional[str]
    bagian: Optional[str]
    pasal: Optional[str]
    ayat: Optional[str]
    butir: Optional[str]
    huruf: list[str]
    page_start: Optional[int]
    page_end: Optional[int]
    text: str


# =============================================================================
# STATE
# =============================================================================

class _State:
    __slots__ = (
        "lampiran", "bab", "bagian", "pasal", "ayat", "butir",
        "buffer", "buffer_page_start", "current_page",
        "chunks", "awaiting_bab_title",
    )

    def __init__(self):
        self.lampiran: Optional[str] = None
        self.bab: Optional[str] = None
        self.bagian: Optional[str] = None
        self.pasal: Optional[str] = None
        self.ayat: Optional[str] = None
        self.butir: Optional[str] = None

        self.buffer: list[str] = []
        self.buffer_page_start: Optional[int] = None
        self.current_page: Optional[int] = None

        self.chunks: list[RegulationChunk] = []

        # Flag: baru saja set "BAB V" sendiri (menunggu judul di baris berikut)
        self.awaiting_bab_title = False

    def reset_below(self, level: str) -> None:
        """Reset semua field di bawah level tertentu (transisi naik/turun)."""
        if level == "lampiran":
            self.bab = self.bagian = self.pasal = self.ayat = self.butir = None
        elif level == "bab":
            self.bagian = self.pasal = self.ayat = self.butir = None
        elif level == "bagian":
            self.pasal = self.ayat = self.butir = None
        elif level == "pasal":
            self.ayat = self.butir = None
        elif level == "ayat":
            self.butir = None

    def flush(self) -> None:
        """Keluarkan isi buffer sebagai chunk (kalau memenuhi syarat)."""
        content = "\n".join(self.buffer).strip()
        self.buffer.clear()
        if len(content) < 15:
            self.buffer_page_start = None
            return

        self.chunks.append(RegulationChunk(
            lampiran=self.lampiran,
            bab=self.bab,
            bagian=self.bagian,
            pasal=self.pasal,
            ayat=self.ayat,
            butir=self.butir,
            huruf=re.findall(r"^([a-z])\.\s+", content, re.MULTILINE),
            page_start=self.buffer_page_start,
            page_end=self.current_page,
            text=content,
        ))
        self.buffer_page_start = None

    def append(self, line: str) -> None:
        if self.buffer_page_start is None:
            self.buffer_page_start = self.current_page
        self.buffer.append(line)


# =============================================================================
# KLASIFIKASI HEADING (deterministik, prioritas berurut)
# =============================================================================

def _classify(text: str) -> tuple[Optional[str], Optional[str]]:
    """
    Return (level, value) atau (None, None).
    Level: "lampiran" | "bab" | "bagian" | "pasal" | "ayat" | "butir"
    """
    t = text.strip()
    if not t or len(t) > 300:
        return None, None

    # 1. LAMPIRAN X
    m = _P_LAMPIRAN.match(t)
    if m:
        return "lampiran", f"Lampiran {m.group(1).upper()}"

    # 2. BAB X (sendiri)
    m = _P_BAB_ONLY.match(t)
    if m:
        return "bab", t

    # 3. BAB X JUDUL (inline)
    m = _P_BAB_INLINE.match(t)
    if m and len(t) <= _MAX_HEADING_LEN:
        return "bab", t

    # 4. I. JUDUL (Roman numeral + Kapital) — untuk PADK Lampiran
    m = _P_ROMAN.match(t)
    if m and len(t) <= _MAX_HEADING_LEN:
        rest = m.group(2)
        if rest and rest[0].isupper():
            # Hindari false positive: "I. Pendahuluan ini..." (kalimat panjang)
            if not t.rstrip().endswith((",", ";", ":")):
                return "bab", t

    # 5. Bagian Kesatu / Bagian Pertama
    if _P_BAGIAN_KATA.match(t):
        return "bagian", t

    # 6. A. JUDUL (Kapital + titik + Kapital)
    m = _P_LETTER_UPPER.match(t)
    if m and len(t) <= _MAX_HEADING_LEN:
        rest = m.group(2)
        if rest and rest[0].isupper():
            if not t.rstrip().endswith((",", ";", ":")):
                return "bagian", t

    # 7. Pasal X
    if _P_PASAL.match(t):
        return "pasal", t

    # 8. 1. JUDUL (angka + titik + Kapital, pendek, bukan list)
    m = _P_NUMBER_HEADING.match(t)
    if m and len(t) <= _MAX_HEADING_LEN:
        if not _P_NUMBER_LIST.match(t):
            if not t.rstrip().endswith((",", ";", ":")):
                return "pasal", t

    # 9. (1) / Ayat (1)
    m = _P_AYAT.match(t)
    if m:
        return "ayat", f"({m.group(1)})"

    # 10. a. teks (butir)
    m = _P_BUTIR.match(t)
    if m:
        return "butir", m.group(1) + "."

    return None, None


# =============================================================================
# TRANSISI STATE
# =============================================================================

def _apply_transition(state: _State, level: str, value: str) -> None:
    """Update state sesuai heading baru."""
    if level == "lampiran":
        state.lampiran = value
        state.reset_below("lampiran")
    elif level == "bab":
        state.bab = value
        state.reset_below("bab")
    elif level == "bagian":
        state.bagian = value
        state.reset_below("bagian")
    elif level == "pasal":
        state.pasal = value
        state.reset_below("pasal")
    elif level == "ayat":
        state.ayat = value
        state.reset_below("ayat")
    elif level == "butir":
        state.butir = value


# =============================================================================
# MAIN PARSER
# =============================================================================

def _parse(text: str) -> list[RegulationChunk]:
    state = _State()

    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue

        # --- Page marker ---
        m = _PAGE_MARKER.match(line)
        if m:
            state.current_page = int(m.group(1))
            continue

        # --- Strip H marker (kalau ada) ---
        m = _H_MARKER.match(line)
        h_marker_present = False
        if m:
            line = m.group(1).strip()
            h_marker_present = True

        # --- Cek apakah ini judul BAB yang baru di-set ("BAB V" + judul) ---
        if state.awaiting_bab_title:
            state.awaiting_bab_title = False
            # Baris berikut harus uppercase, pendek, dan bukan heading baru
            if line.isupper() and len(line) < 150:
                level_check, _ = _classify(line)
                if level_check is None:
                    state.bab = f"{state.bab} — {line}"
                    continue

        # --- Klasifikasi heading ---
        level, value = _classify(line)

        if level is not None:
            # Flush konten sebelum heading baru
            state.flush()
            _apply_transition(state, level, value)

            # Special case: "BAB V" sendiri → tunggu judul
            if level == "bab" and _P_BAB_ONLY.match(line):
                state.awaiting_bab_title = True
            continue

        # --- Bukan heading, masuk konten ---
        state.append(line)

    state.flush()
    return state.chunks


# =============================================================================
# POST-FILTER: buang cover page & Daftar Isi
# =============================================================================

_COVER_KEYWORDS = (
    "SALINAN PERATURAN",
    "SALINAN INI SESUAI",
    "DENGAN RAHMAT TUHAN",
    "MEMUTUSKAN:",
    "MENIMBANG :",
    "MENGINGAT :",
)


def _is_cover_chunk(chunk: RegulationChunk) -> bool:
    """Deteksi chunk cover/legal preamble."""
    head = chunk["text"][:400].upper()
    return any(kw in head for kw in _COVER_KEYWORDS)


def _is_toc_chunk(chunk: RegulationChunk) -> bool:
    """
    Deteksi chunk Daftar Isi.
    Ciri: > 50% baris diakhiri angka, atau > 30% baris hanya angka/Roman.
    """
    text = chunk["text"]
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if len(lines) < 5:
        return False

    ends_digit = sum(1 for l in lines if l and l[-1].isdigit())
    ratio_end_digit = ends_digit / len(lines)

    pure_num = sum(
        1 for l in lines
        if re.match(r"^[IVXLCDM]+\.?$", l) or re.match(r"^\d+\.?$", l)
    )
    ratio_pure = pure_num / len(lines)

    return ratio_end_digit > 0.5 or ratio_pure > 0.3


def _filter_chunks(chunks: list[RegulationChunk]) -> list[RegulationChunk]:
    """Buang cover page & TOC dari list chunk."""
    return [
        c for c in chunks
        if not _is_cover_chunk(c) and not _is_toc_chunk(c)
    ]


# =============================================================================
# ENTRY POINT
# =============================================================================

def parse_regulation_structure(text: str) -> list[RegulationChunk]:
    """Parse teks regulasi → list chunk terstruktur."""
    raw_chunks = _parse(text)
    return _filter_chunks(raw_chunks)