"""PPTX : texte traduit qui déborde de sa zone (étape c).

Règle : l'original fait référence. S'il tenait, la traduction doit tenir ; s'il
débordait déjà, la traduction ne doit pas déborder davantage. Remèdes : une
traduction plus courte d'abord, puis la police réduite, jamais sous 80 %.

Zone de test : 143 pt utiles de large (environ 8 em à 18 pt, en largeurs Arial) et
40 pt de haut (une seule ligne de 18 pt).
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import racine  # noqa: F401  -- met backend/ sur le chemin
from lxml import etree

from app.services import translation_runner as tr
from engines.pptx.engine import PPTXTranslatorEngine

A = "http://schemas.openxmlformats.org/drawingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
ID = "slide1_p_p0"


def _slide(texte, corps="<a:bodyPr/>", cy=600000):
    return (f'<p:sld xmlns:a="{A}" xmlns:p="{P}"><p:cSld><p:spTree><p:sp>'
            f'<p:nvSpPr><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="0" y="0"/>'
            f'<a:ext cx="2000000" cy="{cy}"/></a:xfrm></p:spPr>'
            f'<p:txBody>{corps}<a:p><a:r><a:rPr lang="en-US" sz="1800"/>'
            f'<a:t>{texte}</a:t></a:r></a:p></p:txBody>'
            "</p:sp></p:spTree></p:cSld></p:sld>")


def _moteur(xml):
    eng = PPTXTranslatorEngine()
    eng.temp_dir = Path(tempfile.mkdtemp(prefix="debord_"))
    chemin = eng._slide_path(1)
    chemin.parent.mkdir(parents=True)
    chemin.write_bytes(xml.encode())
    return eng, chemin


def _injecter(xml, traduction):
    eng, chemin = _moteur(xml)
    eng._inject_in_xml(chemin, 1, "p", {ID: traduction})
    return eng, chemin, etree.parse(str(chemin)).getroot()


def _echelle(root):
    el = root.find(f".//{{{A}}}normAutofit")
    return None if el is None else int(el.get("fontScale"))


def test_source_tient_traduction_deborde_police_reduite():
    _e, _c, root = _injecter(_slide("Short text"), "Texte un peu plus long")
    assert _echelle(root) == 92500          # deux lignes tiennent à 92,5 %


def test_reduction_jamais_sous_80_pourcent():
    _e, _c, root = _injecter(_slide("Short text"),
                             "Un texte beaucoup trop long pour cette petite zone")
    assert _echelle(root) == 80000


def test_traduction_qui_tient_inchangee():
    xml = _slide("Short text")
    _e, _c, root = _injecter(xml, "Texte court")
    assert root.find(f".//{{{A}}}bodyPr")[:] == []


def test_source_deborde_traduction_pas_pire_inchangee():
    # L'original prend déjà deux lignes dans une zone d'une ligne : l'auteur
    # l'a accepté. Une traduction de deux lignes aussi n'est pas touchée.
    _e, _c, root = _injecter(_slide("aaa bbb ccc ddd eee fff"),
                             "aaaa bbb ccc dd eee ff")
    assert _echelle(root) is None


def test_source_deborde_traduction_deborde_plus_reduite_au_niveau_source():
    # Original : deux lignes (débord accepté). Traduction : trois lignes. On
    # ramène à deux lignes (le débord de l'original), pas à une seule.
    _e, _c, root = _injecter(_slide("aaa bbb ccc ddd eee fff"),
                             "aaaa bbbb cccc dddd eeee ffff gggg")
    assert _echelle(root) == 90000


def test_zone_qui_grandit_seule_ignoree():
    corps = "<a:bodyPr><a:spAutoFit/></a:bodyPr>"
    _e, _c, root = _injecter(_slide("Short text", corps),
                             "Un texte beaucoup trop long pour cette zone")
    assert _echelle(root) is None
    assert root.find(f".//{{{A}}}spAutoFit") is not None


def test_ajustement_existant_remplace_puis_restaure():
    # noAutofit d'origine : remplacé par la réduction, et réinjecter une
    # traduction qui tient le remet tel quel.
    corps = "<a:bodyPr><a:noAutofit/></a:bodyPr>"
    eng, chemin, root = _injecter(_slide("Short text", corps),
                                  "Texte un peu plus long")
    assert _echelle(root) == 92500
    assert root.find(f".//{{{A}}}noAutofit") is None
    eng._inject_in_xml(chemin, 1, "p", {ID: "Texte court"})
    root = etree.parse(str(chemin)).getroot()
    assert _echelle(root) is None
    assert root.find(f".//{{{A}}}noAutofit") is not None


def test_reinjection_ne_cumule_pas():
    # La passe de cohérence réinjecte dans le fichier DÉJÀ traduit : la mesure
    # de l'original est celle prise à la première injection.
    eng, chemin, _r = _injecter(_slide("Short text"), "Texte un peu plus long")
    eng._inject_in_xml(chemin, 1, "p", {ID: "Texte un peu plus long"})
    root = etree.parse(str(chemin)).getroot()
    assert _echelle(root) == 92500
    assert len(root.findall(f".//{{{A}}}normAutofit")) == 1


def test_aller_retour_source_identique():
    for xml in (_slide("Short text"), _slide("aaa bbb ccc ddd eee fff"),
                _slide("Short text", '<a:bodyPr><a:normAutofit fontScale="90000"/></a:bodyPr>')):
        texte = etree.fromstring(xml.encode()).find(f".//{{{A}}}t").text
        _e, chemin, _r = _injecter(xml, texte)
        avant = etree.tostring(etree.fromstring(xml.encode()), method="c14n")
        apres = etree.tostring(etree.parse(str(chemin)).getroot(), method="c14n")
        assert avant == apres


def test_debordements_simulation_sans_ecriture():
    eng, chemin = _moteur(_slide("Short text"))
    ratios = eng.debordements(1, {ID: "Texte un peu plus long"})
    assert set(ratios) == {ID} and 0.9 < ratios[ID] < 1
    assert eng.debordements(1, {ID: "Texte court"}) == {}
    assert b"Short text" in chemin.read_bytes()


def test_compacter_slide_accepte_seulement_plus_court(monkeypatch):
    eng, _c = _moteur(_slide("Short text"))
    vus = []

    class _Faux:
        def _translate_batch(self, batch, target_lang, cb=None, **kw):
            for b in batch:
                vus.append(b["consigne"])
                b["translated_text"] = "Texte plus court"
            return True

    monkeypatch.setattr(tr, "ai_translator", _Faux())
    el = {"id": ID, "text": "Short text", "translated_text": "Texte un peu plus long"}
    assert tr._compacter_slide(eng, 1, {"text_elements": [el]}, "fr") == 1
    assert el["translated_text"] == "Texte plus court"
    assert "MAXIMUM 20 caractères" in vus[0] and "Texte un peu plus long" in vus[0]


def test_compacter_slide_refuse_reponse_plus_longue(monkeypatch):
    eng, _c = _moteur(_slide("Short text"))

    class _Faux:
        def _translate_batch(self, batch, target_lang, cb=None, **kw):
            for b in batch:
                b["translated_text"] = "Une réponse encore bien plus longue"
            return True

    monkeypatch.setattr(tr, "ai_translator", _Faux())
    el = {"id": ID, "text": "Short text", "translated_text": "Texte un peu plus long"}
    assert tr._compacter_slide(eng, 1, {"text_elements": [el]}, "fr") == 0
    assert el["translated_text"] == "Texte un peu plus long"
