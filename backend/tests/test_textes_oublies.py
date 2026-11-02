"""Textes restés en langue source dans un PPTX traduit (compte rendu réel).

CE QUI EST EN JEU
-----------------
Quatre sources de texte visibles échappaient à la traduction :

1. CELLULE `t="str"` SANS FORMULE. Excel (et les générateurs de rapports)
   écrit parfois un texte saisi comme « chaîne de formule » sans `<f>`. Le
   texte est dans `<v>`, ni dans sharedStrings ni en `inlineStr`. Une cellule
   AVEC formule garde son résultat : Excel le recalcule, on n'y touche pas.
2. MASQUE DES DIAPOSITIVES. Ses formes (pied de page, bandeau) s'affichent sur
   chaque diapositive. Il était extrait mais jamais envoyé au traducteur, et
   absent du flux progressif.
3. CLASSEUR INCORPORÉ (tableau, graphique). Seul sharedStrings était lu ; les
   cellules `t="str"` et les textes des graphiques restaient en français. Le
   classeur passe désormais par le moteur XLSX complet.
4. TEXTE RÉPÉTÉ TRADUIT À REBOURS. Un titre anglais présent dans trois mises
   en page revenait en français dans l'une d'elles : la traduction
   majoritaire s'applique désormais à tous les doublons.

    backend/venv/Scripts/python.exe backend/tests/test_textes_oublies.py
"""
from __future__ import annotations

import io
import json
import os
import re
import tempfile
import zipfile

import racine  # noqa: F401  -- met backend/ sur le chemin

import engines                                              # noqa: E402
from engines.translation_ai import TranslatorAI, harmoniser  # noqa: E402
from fabrique_classeurs import (construire_avec_graphique,   # noqa: E402
                                construire_multi)
from pptx import Presentation                                # noqa: E402
from pptx.enum.shapes import PROG_ID                         # noqa: E402

_checks: list[tuple[bool, str]] = []


def check(cond: bool, label: str, detail: str = "") -> None:
    _checks.append((bool(cond), label))
    print(f"  {'OK  ' if cond else 'ECHEC'} {label}"
          + (f"   [{detail}]" if detail and not cond else ""))


LIGNE = ('<row r="99"><c r="A99" t="str"><v>Taux de progression</v></c>'
         '<c r="B99" t="str"><f>"x"</f><v>calculee</v></c></row>')


def _classeur_avec_str(dossier: str, graphique: bool = False) -> str:
    fabrique = construire_avec_graphique if graphique else construire_multi
    src = fabrique(os.path.join(dossier, "base.xlsx"))
    sortie = os.path.join(dossier, "str_g.xlsx" if graphique else "str.xlsx")
    with zipfile.ZipFile(src) as zi, zipfile.ZipFile(sortie, "w") as zo:
        for item in zi.infolist():
            data = zi.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                data = data.replace(b"</sheetData>", LIGNE.encode() + b"</sheetData>")
            zo.writestr(item, data)
    return sortie


def _xlsx(dossier: str) -> None:
    src = _classeur_avec_str(dossier)
    extraction, _ = engines.new_engine("xlsx").extract_text(
        src, os.path.join(dossier, "ex.json"))
    els = extraction["workbook"]["elements"]
    ids = {el["id"] for el in els}
    check("str_sheet1_A99" in ids, "XLSX cellule t=str sans formule relevée", str(sorted(ids))[:200])
    check("str_sheet1_B99" not in ids, "XLSX cellule t=str AVEC formule ignorée")
    for el in els:
        el["translated_text"] = (el["text"] if el["context"]["part"] == "sheetName" else
                                 re.sub(r"(\[\[(\d+)\]\])(.*?)(\[\[/\2\]\])",
                                        lambda m: m.group(1) + "EN:" + m.group(3) + m.group(4),
                                        el["text"]))
    tr = os.path.join(dossier, "tr.json")
    with open(tr, "w", encoding="utf-8") as f:
        json.dump(extraction, f, ensure_ascii=False)
    out = os.path.join(dossier, "out.xlsx")
    ok, msg = engines.new_engine("xlsx").inject_translation(src, tr, out)
    check(ok, "XLSX injection réussie", str(msg))
    with zipfile.ZipFile(out) as z:
        feuille = z.read("xl/worksheets/sheet1.xml").decode("utf-8")
    check("<v>EN:Taux de progression</v>" in feuille, "XLSX cellule t=str traduite")
    check("<v>calculee</v>" in feuille, "XLSX résultat de formule intact")


def _lots_envoyes(extraction: dict, chemin: str) -> list[str]:
    """Les textes que `translate_json` envoie, sans appel réseau."""
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(extraction, f, ensure_ascii=False)
    vus: list[str] = []
    trad = TranslatorAI.__new__(TranslatorAI)

    def lot(batch, *_a, **_k):
        for b in batch:
            vus.append(b["text"])
            b["translated_text"] = b["text"]
        return True
    trad._translate_batch = lot
    trad.fiche_document = lambda *a, **k: ""
    trad.translate_json(chemin, "en", fiche="")
    return vus


def _deck(chemin: str) -> None:
    """Un deck dont le masque porte une zone de texte (hors espace réservé)."""
    prs = Presentation()  # pyrefly: ignore[not-callable]
    prs.slides.add_slide(prs.slide_layouts[6])
    brut = chemin + ".brut"
    prs.save(brut)
    forme = ('<p:sp><p:nvSpPr><p:cNvPr id="99" name="Pied"/><p:cNvSpPr txBox="1"/>'
             '<p:nvPr/></p:nvSpPr><p:spPr/><p:txBody><a:bodyPr/><a:p><a:r>'
             '<a:t>Pied de page du masque</a:t></a:r></a:p></p:txBody></p:sp>')
    with zipfile.ZipFile(brut) as zi, zipfile.ZipFile(chemin, "w") as zo:
        for item in zi.infolist():
            data = zi.read(item.filename)
            if item.filename == "ppt/slideMasters/slideMaster1.xml":
                data = data.replace(b"</p:spTree>", forme.encode() + b"</p:spTree>", 1)
            zo.writestr(item, data)


def _pptx(dossier: str) -> None:
    src = os.path.join(dossier, "deck.pptx")
    _deck(src)

    # Lot : le masque part au traducteur.
    extraction, _ = engines.new_engine("pptx").extract_text(
        src, os.path.join(dossier, "p.json"))
    textes_masque = [el["text"] for sd in extraction["slides"]
                     for m in sd.get("master_elements", []) for el in m["text_elements"]]
    check(any("Pied de page du masque" in t for t in textes_masque),
          "PPTX lot : masque extrait", str(textes_masque)[:200])
    envoyes = _lots_envoyes(extraction, os.path.join(dossier, "p.json"))
    check(any("Pied de page du masque" in t for t in envoyes),
          "PPTX lot : masque envoyé au traducteur")

    # Progressif : extraction + injection du masque.
    eng = engines.new_engine("pptx")
    eng._extract_zip(src)
    sd, _ = eng.extract_slide(1)
    masques = (sd or {}).get("master_elements", [])
    els = [el for m in masques for el in m["text_elements"]]
    check(any("Pied de page du masque" in el["text"] for el in els),
          "PPTX progressif : masque extrait")
    tmap = {el["id"]: "Master footer" if "Pied de page" in el["text"] else el["text"]
            for el in els}
    eng.inject_slide(1, tmap)
    xml = (eng._get_temp_dir() / "ppt" / "slideMasters" / "slideMaster1.xml").read_text(
        encoding="utf-8")
    check("Master footer" in xml and "Pied de page du masque" not in xml,
          "PPTX progressif : masque injecté")
    eng._cleanup_temp()


def _classeur_dans_pptx(dossier: str) -> None:
    """3. Le tableau d'un compte rendu est un classeur incorporé : ses cellules
    `t="str"` et son graphique se traduisent comme un XLSX seul."""
    classeur = _classeur_avec_str(dossier, graphique=True)
    src = os.path.join(dossier, "ole.pptx")
    prs = Presentation()  # pyrefly: ignore[not-callable]
    diapo = prs.slides.add_slide(prs.slide_layouts[6])
    diapo.shapes.add_ole_object(classeur, PROG_ID.XLSX, 0, 0)
    prs.save(src)

    eng = engines.new_engine("pptx")
    extraction, _ = eng.extract_text(src, os.path.join(dossier, "ole.json"))
    excel = [el for sd in extraction["slides"] for el in sd.get("excel_elements", [])]
    textes = " | ".join(el["text"] for el in excel)
    for attendu in ("Taux de progression", "Evolution des ventes", "Marge brute"):
        check(attendu in textes, f"OLE relevé : {attendu}", textes[:200])
    check("calculee" not in textes, "OLE résultat de formule non relevé")
    for el in excel:
        el["translated_text"] = re.sub(
            r"(\[\[(\d+)\]\])(.*?)(\[\[/\2\]\])",
            lambda m: m.group(1) + "EN:" + m.group(3) + m.group(4), el["text"])
    tr = os.path.join(dossier, "ole_tr.json")
    with open(tr, "w", encoding="utf-8") as f:
        json.dump(extraction, f, ensure_ascii=False)
    out = os.path.join(dossier, "ole_out.pptx")
    ok, msg = engines.new_engine("pptx").inject_translation(src, tr, out)
    check(ok, "OLE injection réussie", str(msg))
    with zipfile.ZipFile(out) as z:
        nom = next(n for n in z.namelist() if n.startswith("ppt/embeddings/"))
        with zipfile.ZipFile(io.BytesIO(z.read(nom))) as x:
            feuille = x.read("xl/worksheets/sheet1.xml").decode("utf-8")
            graphe = x.read("xl/charts/chart1.xml").decode("utf-8")
    check("<v>EN:Taux de progression</v>" in feuille, "OLE cellule t=str traduite")
    check("<v>calculee</v>" in feuille, "OLE résultat de formule intact")
    check("EN:Evolution des ventes" in graphe, "OLE titre du graphique traduit")
    caches = re.findall(r"<c:strCache>.*?</c:strCache>", graphe, re.S)
    check(caches and "EN:Marge brute" in " ".join(caches)
          and "<c:v>Marge brute</c:v>" not in graphe,
          "OLE cache de série aligné sur la cellule traduite", " ".join(caches)[:200])


def _harmonisation() -> None:
    blocs = [{"text": "OUR NEW", "translated_text": t} for t in ("OUR NEW", "NOS NOUVELLES", "OUR NEW")]
    blocs += [{"text": "Bilan", "translated_text": "Review"},
              {"text": "Bilan", "translated_text": "Bilan"},
              {"text": "Seul", "translated_text": "Alone"}]
    harmoniser(blocs)
    check(all(b["translated_text"] == "OUR NEW" for b in blocs[:3]),
          "Doublons : la traduction majoritaire l'emporte")
    check(blocs[3]["translated_text"] == blocs[4]["translated_text"] == "Bilan",
          "Doublons à égalité : le texte laissé tel quel l'emporte")
    check(blocs[5]["translated_text"] == "Alone", "Texte unique intact")


def main() -> int:
    dossier = tempfile.mkdtemp(prefix="precis_test_oublies_")
    _xlsx(dossier)
    _pptx(dossier)
    _classeur_dans_pptx(dossier)
    _harmonisation()
    bons = sum(1 for c, _ in _checks if c)
    print(f"\n  {bons}/{len(_checks)} verifications")
    return 0 if bons == len(_checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
