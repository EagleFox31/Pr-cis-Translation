"""Polices Type3 de Skia (Chrome « Enregistrer en PDF ») : nom réel, gras et
italique lus dans le /FontDescriptor ; un mot peint avec deux objets police au
même style visible reste un seul segment."""
import fitz

from engines.pdf import engine
from engines.pdf.tagging import _line_segments


def _doc_type3(nom, poids, angle):
    doc = fitz.open()
    doc.new_page()
    fd = doc.get_new_xref()
    doc.update_object(
        fd, f"<< /Type /FontDescriptor /FontName /{nom} /Flags 32 "
            f"/FontWeight {poids} /ItalicAngle {angle} >>")
    font = doc.get_new_xref()
    doc.update_object(
        font, f"<< /Type /Font /Subtype /Type3 /FontDescriptor {fd} 0 R >>")
    return doc, font


def _raw(font_xref, flags=0):
    return {"blocks": [{"type": 0, "lines": [{"spans": [
        {"font": f"Type3 ({font_xref} 0 R)", "flags": flags}]}]}]}


def test_type3_gras_italique_depuis_descripteur():
    doc, x = _doc_type3("ABCDEF+Arimo-BoldItalic", 700, -12)
    raw = engine._normaliser_type3(doc, _raw(x))
    span = raw["blocks"][0]["lines"][0]["spans"][0]
    assert span["font"] == "ABCDEF+Arimo-BoldItalic"
    assert span["flags"] & 16 and span["flags"] & 2


def test_type3_regulier_sans_flags():
    doc, x = _doc_type3("Arimo", 400, 0)
    span = engine._normaliser_type3(doc, _raw(x))["blocks"][0]["lines"][0][
        "spans"][0]
    assert span["font"] == "Arimo"
    assert not span["flags"] & 18


def test_type3_sans_descripteur_inchange():
    doc = fitz.open()
    doc.new_page()
    x = doc.get_new_xref()
    doc.update_object(x, "<< /Type /Font /Subtype /Type3 >>")
    span = engine._normaliser_type3(doc, _raw(x))["blocks"][0]["lines"][0][
        "spans"][0]
    assert span["font"] == f"Type3 ({x} 0 R)"


def _run(font, text, x0, x1):
    return {"font": font, "text": text, "size": 10.0, "color": [0, 0, 0],
            "bold": False, "italic": False, "bbox": [x0, 0, x1, 10]}


def test_mot_sur_deux_objets_police_reste_entier():
    line = {"gw": 5.0, "runs": [_run("Type3 (12 0 R)", "Dévelop", 0, 35),
                                _run("Type3 (14 0 R)", "pement", 35, 65)]}
    segs = _line_segments(line)
    assert [s["text"] for s in segs] == ["Développement"]


def test_changement_de_police_entre_mots_conserve():
    line = {"gw": 5.0, "runs": [_run("Arimo", "Hello ", 0, 30),
                                _run("Tinos", "world", 30, 55)]}
    segs = _line_segments(line)
    assert [s["text"] for s in segs] == ["Hello ", "world"]


def test_police_variable_nom_regular_poids_gras():
    # Chrome nomme « Lora-Regular » une police variable peinte en 700.
    doc, x = _doc_type3("AAAAAA+Lora-Regular", 700, 0)
    span = engine._normaliser_type3(doc, _raw(x))["blocks"][0]["lines"][0][
        "spans"][0]
    assert span["font"] == "AAAAAA+Lora-Bold"
    assert span["flags"] & 16
