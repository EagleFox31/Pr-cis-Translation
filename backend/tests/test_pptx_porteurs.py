"""PPTX : lignes coupées à la main, symboles, espaces doubles.

Cas tirés du PowerPoint de production analysé (docs/etude-pptx-qualite-gerold.md) :
titre coupé par des sauts de ligne, bandeau coupé en paragraphes, coches
Wingdings. Règle de non-régression commune : réinjecter la SOURCE comme
traduction rend exactement le texte d'origine.
"""
from __future__ import annotations

import os
import tempfile
from collections import defaultdict

import racine  # noqa: F401  -- met backend/ sur le chemin
from lxml import etree

from engines import runtags
from engines.pptx.engine import PPTXTranslatorEngine

A = "http://schemas.openxmlformats.org/drawingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
RPR = '<a:rPr lang="en-US" sz="1000" b="1"/>'


def _r(texte, rpr=RPR):
    return f"<a:r>{rpr}<a:t xml:space=\"preserve\">{texte}</a:t></a:r>"


def _sp(*paragraphes, ph=False):
    nv = '<p:nvPr><p:ph type="title"/></p:nvPr>' if ph else "<p:nvPr/>"
    corps = "".join(f"<a:p>{p}</a:p>" for p in paragraphes)
    return (f'<p:sld xmlns:a="{A}" xmlns:p="{P}"><p:cSld><p:spTree><p:sp>'
            f"<p:nvSpPr>{nv}</p:nvSpPr><p:txBody>{corps}</p:txBody>"
            "</p:sp></p:spTree></p:cSld></p:sld>")


def _extraire(xml):
    eng = PPTXTranslatorEngine()
    root = etree.fromstring(xml.encode())
    data = []
    eng._process_xml_element(root, 1, data, defaultdict(set), "p",
                             {"shapes": True})
    return {d["id"]: d["text"] for d in data}


def _injecter(xml, tmap):
    eng = PPTXTranslatorEngine()
    with tempfile.TemporaryDirectory() as d:
        chemin = os.path.join(d, "s.xml")
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(xml)
        eng._inject_in_xml(chemin, 1, "p", tmap)
        root = etree.parse(chemin).getroot()
    return [[t.text or "" for t in p.iter(f"{{{A}}}t")]
            for p in root.iter(f"{{{A}}}p")]


def _aller_retour(xml):
    avant = _injecter(xml, {})
    assert _injecter(xml, _extraire(xml)) == avant


# ── découpe des lignes ──────────────────────────────────────────────────────

def test_decoupe_rend_la_coupe_source():
    lignes = ["Toyota", "Service Advisor Program", "Deployment Guide"]
    texte = runtags.joindre_lignes(lignes)
    assert runtags.decouper_lignes(texte, [len(l) for l in lignes]) == lignes


def test_decoupe_coupure_au_trait_d_union():
    assert runtags.joindre_lignes(["Self-", "study"]) == "Self-study"
    assert runtags.decouper_lignes("Self-study", [5, 5]) == ["Self-", "study"]


def test_decoupe_moins_de_mots_que_de_lignes():
    assert runtags.decouper_lignes("Rappel", [11, 11]) == ["Rappel", ""]


# ── saut de ligne manuel ────────────────────────────────────────────────────

TITRE = _sp(_r("Toyota ") + "<a:br/>" + _r("Service Advisor Program ")
            + "<a:br/>" + _r("Deployment Guide"))


def test_saut_de_ligne_une_seule_unite():
    assert _extraire(TITRE) == {
        "slide1_p_p0": "[[0]]Toyota Service Advisor Program Deployment Guide[[/0]]"}


def test_saut_de_ligne_redecoupe_sur_les_memes_lignes():
    sortie = _injecter(TITRE, {"slide1_p_p0":
        "[[0]]Guide de déploiement du programme Conseiller Service Toyota[[/0]]"})
    assert len(sortie[0]) == 3 and all(l.strip() for l in sortie[0])
    assert " ".join(l.strip() for l in sortie[0]) == \
        "Guide de déploiement du programme Conseiller Service Toyota"


def test_pas_de_fusion_apres_fin_de_phrase_ou_avant_puce():
    xml = _sp(_r("Done.") + "<a:br/>" + _r("Next step")
              + "<a:br/>" + _r("- item"))
    assert _extraire(xml) == {"slide1_p_p0":
        "[[0]]Done.[[/0]][[1]]Next step[[/1]][[2]]- item[[/2]]"}


def test_pas_de_fusion_si_mise_en_forme_differente():
    xml = _sp(_r("Titre") + "<a:br/>" + _r("sous-titre", '<a:rPr sz="800"/>'))
    assert _extraire(xml) == {"slide1_p_p0":
        "[[0]]Titre[[/0]][[1]]sous-titre[[/1]]"}


def test_aller_retour_saut_de_ligne():
    _aller_retour(TITRE)


# ── libellé coupé en paragraphes ────────────────────────────────────────────

BANDEAU = _sp(_r("Appointment"), _r("Preparation"))


def test_bandeau_une_seule_unite():
    assert _extraire(BANDEAU) == {
        "slide1_p_p0": "[[0]]Appointment Preparation[[/0]]"}


def test_bandeau_redecoupe_sur_les_paragraphes():
    sortie = _injecter(BANDEAU, {"slide1_p_p0":
                                 "[[0]]Préparation du rendez-vous[[/0]]"})
    assert sortie == [["Préparation"], ["du rendez-vous"]]


def test_bandeau_ancienne_traduction_par_paragraphe():
    sortie = _injecter(BANDEAU, {"slide1_p_p0": "[[0]]Rendez-vous[[/0]]",
                                 "slide1_p_p1": "[[0]]Préparation[[/0]]"})
    assert sortie == [["Rendez-vous"], ["Préparation"]]


def test_pas_de_fusion_espace_reserve_ou_texte_long():
    assert len(_extraire(_sp(_r("Appointment"), _r("Preparation"), ph=True))) == 2
    assert len(_extraire(_sp(_r("One two three four"), _r("five")))) == 2


def test_aller_retour_bandeau():
    _aller_retour(BANDEAU)


# ── symboles ────────────────────────────────────────────────────────────────

COCHE = " "


def test_coche_seule_pas_envoyee():
    assert _extraire(_sp(_r(COCHE))) == {}


def test_coche_gardee_a_cote_du_texte():
    xml = _sp(_r(COCHE) + _r(" TSM-FIR as Kaizen"))
    assert _extraire(xml) == {"slide1_p_p0": "[[0]] TSM-FIR as Kaizen[[/0]]"}
    assert _injecter(xml, {"slide1_p_p0": "[[0]] TSM-FIR comme Kaizen[[/0]]"}) \
        == [[COCHE, " TSM-FIR comme Kaizen"]]


def test_prefixe_symbole_dans_le_run():
    xml = _sp(_r("→ Next step"))
    assert _extraire(xml) == {"slide1_p_p0": "[[0]]Next step[[/0]]"}
    assert _injecter(xml, {"slide1_p_p0": "[[0]]Étape suivante[[/0]]"}) \
        == [["→ Étape suivante"]]


# ── espaces doubles ─────────────────────────────────────────────────────────

def test_pas_d_espace_double_cree():
    xml = _sp(_r("Customer handling"))
    assert _injecter(xml, {"slide1_p_p0": "[[0]]Accueil  client[[/0]]"}) \
        == [["Accueil client"]]


def test_pas_d_espace_double_a_la_jonction():
    xml = _sp(_r("Customer ") + _r("handling", '<a:rPr i="1"/>'))
    assert _injecter(xml, {"slide1_p_p0":
                           "[[0]]Accueil [[/0]][[1]] client[[/1]]"}) \
        == [["Accueil ", "client"]]
