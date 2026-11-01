"""Textes restés en langue source dans un PPTX traduit (compte rendu réel).

CE QUI EST EN JEU
-----------------
Trois sources de texte visibles échappaient à la traduction :

1. CELLULE `t="str"` SANS FORMULE. Excel (et les générateurs de rapports)
   écrit parfois un texte saisi comme « chaîne de formule » sans `<f>`. Le
   texte est dans `<v>`, ni dans sharedStrings ni en `inlineStr`. Une cellule
   AVEC formule garde son résultat : Excel le recalcule, on n'y touche pas.
2. MASQUE DES DIAPOSITIVES. Ses formes (pied de page, bandeau) s'affichent sur
   chaque diapositive. Il était extrait mais jamais envoyé au traducteur, et
   absent du flux progressif.

    backend/venv/Scripts/python.exe backend/tests/test_textes_oublies.py
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import zipfile

import racine  # noqa: F401  -- met backend/ sur le chemin

import engines                                              # noqa: E402
from engines.translation_ai import TranslatorAI              # noqa: E402
from fabrique_classeurs import construire_multi              # noqa: E402
from pptx import Presentation                                # noqa: E402

_checks: list[tuple[bool, str]] = []


def check(cond: bool, label: str, detail: str = "") -> None:
    _checks.append((bool(cond), label))
    print(f"  {'OK  ' if cond else 'ECHEC'} {label}"
          + (f"   [{detail}]" if detail and not cond else ""))


LIGNE = ('<row r="99"><c r="A99" t="str"><v>Taux de progression</v></c>'
         '<c r="B99" t="str"><f>"x"</f><v>calculee</v></c></row>')


def _classeur_avec_str(dossier: str) -> str:
    src = construire_multi(os.path.join(dossier, "base.xlsx"))
    sortie = os.path.join(dossier, "str.xlsx")
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


def main() -> int:
    dossier = tempfile.mkdtemp(prefix="precis_test_oublies_")
    _xlsx(dossier)
    _pptx(dossier)
    bons = sum(1 for c, _ in _checks if c)
    print(f"\n  {bons}/{len(_checks)} verifications")
    return 0 if bons == len(_checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
