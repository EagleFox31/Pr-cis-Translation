"""Langue probable d'un document déposé (revue UX de l'aperçu, point S4).

    cd backend && PYTHONUTF8=1 venv/Scripts/python.exe tests/test_langue_document.py
Sans base de données.
"""
import io
import os
import sys
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app.services.langue_document import detecter_langue, langue_du_document  # noqa: E402

EN = ("Our revenue grew by 12 percent this quarter. The team delivered three new products on time. "
      "Customer satisfaction reached a record high and we will expand to two new markets. ") * 3
FR = ("Notre chiffre d'affaires a progressé de 12 % ce trimestre. L'équipe a livré trois nouveaux produits "
      "dans les délais et la satisfaction des clients est au plus haut. Nous allons ouvrir deux marchés. ") * 3
DE = ("Der Umsatz ist in diesem Quartal um 12 Prozent gestiegen und das Team hat drei neue Produkte "
      "pünktlich geliefert. Die Zufriedenheit der Kunden ist auf einem Rekordhoch, und wir werden auch "
      "in zwei neue Märkte gehen. ") * 3


class DetecterLangue(unittest.TestCase):
    def test_latin_languages(self):
        self.assertEqual(detecter_langue(EN), "en")
        self.assertEqual(detecter_langue(FR), "fr")
        self.assertEqual(detecter_langue(DE), "de")

    def test_other_scripts(self):
        self.assertEqual(detecter_langue("Выручка компании выросла на двенадцать процентов в этом квартале. " * 3), "ru")
        self.assertEqual(detecter_langue("本季度收入增长了百分之十二，团队按时交付了三款新产品。" * 3), "zh")

    def test_unsure_returns_none(self):
        self.assertIsNone(detecter_langue(""))
        self.assertIsNone(detecter_langue("Rapport 2026 — tableau 1, tableau 2"))
        self.assertIsNone(detecter_langue("12 345 678 " * 50))

    def test_formats(self):
        self.assertEqual(langue_du_document(EN.encode(), "txt"), "en")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("word/document.xml", "<w:document><w:body>" + "".join(
                f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in FR.split(". ")) + "</w:body></w:document>")
        self.assertEqual(langue_du_document(buf.getvalue(), "docx"), "fr")
        import fitz
        doc = fitz.open(); page = doc.new_page()
        page.insert_textbox(fitz.Rect(40, 40, 560, 800), EN, fontsize=10)
        self.assertEqual(langue_du_document(doc.tobytes(), "pdf"), "en")
        self.assertIsNone(langue_du_document(b"pas un zip", "docx"))


if __name__ == "__main__":
    unittest.main()
