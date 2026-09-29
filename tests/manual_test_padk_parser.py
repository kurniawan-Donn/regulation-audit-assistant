from pathlib import Path
from app.services.pdf_parser import extract_pdf_text
from app.services.text_processor import clean_text
from app.services.regulation_parser import parse_regulation_structure

pdf_path = "uploads/PADK_43-PADK03-2025.pdf" 
raw = extract_pdf_text(pdf_path)
cleaned = clean_text(raw)
chunks = parse_regulation_structure(cleaned)

print(f"Total chunks: {len(chunks)}\n")
for c in chunks[:10]:
    ref = " / ".join(filter(None, [c["lampiran"], c["bab"], c["pasal"], c["butir"]]))
    print(f"[{ref or '(no ref)'}]")
    print(f"  {c['text'][:120]}...")
    print()