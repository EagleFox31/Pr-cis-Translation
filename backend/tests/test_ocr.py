"""Reconnaissance reelle de scans, orientation, fond et rendu du moteur PDF."""
import io
import os
import tempfile
import time
from unittest.mock import patch

import racine  # noqa: F401
import fitz
from PIL import Image
from app.services.ocr import OCRUnavailable, lire_page
from engines.pdf.engine import PDFObjectEngine
from engines.pdf.tagging import tag_paragraph


def scanned_pdf(rotated=False):
    with fitz.open() as source, fitz.open() as output:
        page = source.new_page(width=595, height=842)
        page.draw_rect(page.rect, color=None, fill=(1, 1, 0.8))
        page.insert_text((60, 80), "Congratulations on your graduation", fontsize=20)
        for row in range(12):
            page.insert_text((60, 130 + row * 28),
                             "This official certificate confirms successful academic studies.", fontsize=12)
        page.draw_circle((480, 700), 30, color=(0, 0, 1), width=3)
        image = Image.open(io.BytesIO(page.get_pixmap(dpi=180).tobytes("png")))
        if rotated:
            image = image.rotate(90, expand=True)
        png = io.BytesIO(); image.save(png, format="PNG")
        scan = output.new_page(width=image.width * 72 / 180, height=image.height * 72 / 180)
        scan.insert_image(scan.rect, stream=png.getvalue())
        # Page numerique hors selection, conservee a l'identique.
        digital = output.new_page()
        digital.insert_text((70, 100), "Untouched digital page", fontsize=18)
        return output.tobytes()


def lire(octets, numero=1):
    with fitz.open(stream=octets, filetype="pdf") as doc:
        return lire_page(doc, numero)


def verifier_fond_et_sceau(page):
    pix = page.get_pixmap()
    # Le sceau bleu en dehors du texte et le fond jaune restent visibles.
    assert pix.pixel(480, 670)[2] > 180 and pix.pixel(480, 670)[0] < 100
    assert pix.pixel(20, 20)[0] > 240 and pix.pixel(20, 20)[2] < 230


def main():
    started = time.monotonic()
    original = scanned_pdf()
    lecture = lire(original)
    assert lecture.statut == "ok", lecture
    prepared = lecture.pdf
    with fitz.open(stream=original, filetype="pdf") as before, fitz.open(stream=prepared, filetype="pdf") as after:
        assert len(after) == 1
        assert not before[0].get_text().strip()
        assert "Congratulations" in after[0].get_text()
        verifier_fond_et_sceau(after[0])
    rotated = lire(scanned_pdf(rotated=True))
    with fitz.open(stream=rotated.pdf, filetype="pdf") as doc:
        assert "Congratulations" in doc[0].get_text(), "Sideways scans must be readable"
        assert doc[0].rect.height > doc[0].rect.width
    with tempfile.TemporaryDirectory() as tmp:
        source = os.path.join(tmp, "recognized.pdf")
        result = os.path.join(tmp, "translated.pdf")
        with open(source, "wb") as f:
            f.write(prepared)
        engine = PDFObjectEngine()
        data, _ = engine.extract(source)
        for page in data["pages"]:
            for element in page["elements"]:
                if element.get("type") == "paragraph":
                    text, styles = tag_paragraph(element)
                    element["tr_tagged"] = text.replace("Congratulations", "Felicitations")
                    element["tr_segments"] = styles
        engine.reinject(data, result, draw_borders=False, translated=True)
        with fitz.open(result) as doc:
            assert "Felicitations" in doc[0].get_text(), "OCR text must reach the translation renderer"
            assert "Congratulations" not in doc[0].get_text()
            verifier_fond_et_sceau(doc[0])
        # Le job lit la page dans sa boucle et garde l'original intact. Le fond
        # du scan doit survivre au travail et a la reouverture ; la page
        # numerique hors selection reste a l'identique.
        from app.services.translation_runner import run_pdf_v2_job, render_translation_bytes
        from app.services.jobs import jobs
        original_path = os.path.join(tmp, "original.pdf")
        translation_path = os.path.join(tmp, "pages_debug_ocrv3.json")
        output_path = os.path.join(tmp, "output.pdf")
        job_id = jobs.create()
        run_pdf_v2_job(job_id, original, original_path, output_path, "scan.pdf",
                       os.path.join(tmp, "partial.pdf"), translation_path,
                       "en", {1}, True)
        assert os.path.isfile(output_path), "OCR job must render successfully"
        with open(original_path, "rb") as f:
            assert f.read() == original, "Never overwrite the original scan"
        with fitz.open(output_path) as doc, fitz.open(stream=original, filetype="pdf") as before:
            assert len(doc) == 2
            # Hors selection : page d'origine, avec la seule mention « non incluse ».
            from engines.pdf.stream import mention_non_incluse
            assert doc[1].get_text() == before[1].get_text() + mention_non_incluse("en") + chr(10)
            verifier_fond_et_sceau(doc[0])
        reopened = render_translation_bytes(original_path, translation_path, "pdf", "en")
        with fitz.open(stream=reopened, filetype="pdf") as doc:
            assert "Congratulations" in doc[0].get_text(), "Reopening must use the recognized source"
            verifier_fond_et_sceau(doc[0])
        # Ancienne traduction : scan entier prepare a l'envoi, jamais rendu sans lui.
        ancienne = os.path.join(tmp, "pages_debug_ocrv1.json")
        with open(ancienne, "w", encoding="utf-8") as f:
            f.write('{"pages": []}')
        try:
            render_translation_bytes(original_path, ancienne, "pdf", "en")
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("Missing OCR source must not silently return an untranslated scan")
    with fitz.open() as blank:
        blank.new_page()
        assert lire(blank.tobytes()).statut == "blanche", "A blank page must not become a paid translation"
    with patch("app.services.ocr_v2.detect.shutil.which", return_value=None):
        try:
            lire(original)
        except OCRUnavailable:
            pass
        else:
            raise AssertionError("Missing OCR must fail explicitly")
    print(f"PASS: real OCR, rotated scan, digital page preserved, colored background and seal, translated rendering, blank page ({time.monotonic()-started:.2f}s)")


if __name__ == "__main__":
    main()
