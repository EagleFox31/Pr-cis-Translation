"""Test reel OCR -> DeepSeek -> PDF, uniquement sur un document synthetique."""
import io
import json
from pathlib import Path
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fitz
from app.services.ocr import prepare_scanned_pdf
from engines.pdf.stream import translate_pdf_progressive

with tempfile.TemporaryDirectory(prefix="precis-ocr-smoke-") as directory:
    with fitz.open() as digital, fitz.open() as scan:
        page = digital.new_page()
        page.insert_text((70, 100), "Bonjour, ce service traduit les documents.", fontsize=18)
        page.insert_text((70, 145), "La reconnaissance du texte fonctionne avant la traduction.", fontsize=14)
        target = scan.new_page()
        target.insert_image(target.rect, pixmap=page.get_pixmap(dpi=180))
        original = scan.tobytes()
    prepared, count = prepare_scanned_pdf(original, {1})
    assert count == 1
    source = Path(directory) / "recognized.pdf"
    source.write_bytes(prepared)
    output = Path(directory) / "translated.pdf"
    cache = Path(directory) / "pages.json"
    translate_pdf_progressive(str(source), str(output), target_lang="en", pages={1}, cache_path=str(cache))
    with fitz.open(output) as result:
        text = result[0].get_text().strip()
        assert text and "Bonjour" not in text, "The visible source text must be replaced"
    data = json.loads(cache.read_text())
    assert any(element.get("tr_tagged") for page in data["pages"]
               for element in page["elements"] if element.get("type") == "paragraph")
    print("PASS: production Tesseract recognized a synthetic scan; DeepSeek translated it; translated PDF rendered successfully.")
