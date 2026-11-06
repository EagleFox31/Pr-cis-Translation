"""Reprise DOCX/XLSX par lot : un arrêt ne perd que les lots en vol.

`translate_json` note chaque lot réussi dans `<relevé>_lots.json` ; relancé,
il ne renvoie au modèle que les lots manquants, puis efface la note.
Lancer : python tests/test_reprise_lots.py
"""
from __future__ import annotations
import json
import os
import sys
import tempfile
import threading

import racine  # noqa: F401  -- met backend/ sur le chemin

from engines.translation_ai import TranslatorAI  # noqa: E402


def _traducteur(appels, refus=()):
    tr = object.__new__(TranslatorAI)
    tr.client, tr.model, tr.target_batch_size = None, "deepseek-flash", 1
    tr.system_instruction = ""
    verrou = threading.Lock()

    def lot(batch, *_a, **_k):
        with verrou:
            appels.extend(b["text"] for b in batch)
        if any(b["text"] in refus for b in batch):
            return False
        for b in batch:
            b["translated_text"] = "EN " + b["text"]
        return True
    tr._translate_batch = lot
    return tr


def run() -> bool:
    checks = []

    def ok(nom, cond, detail=""):
        checks.append((nom, bool(cond), detail))

    with tempfile.TemporaryDirectory() as tmp:
        chemin = os.path.join(tmp, "extraction_xlsx.json")
        lots = chemin.replace(".json", "_lots.json")
        textes = [f"c{i}" for i in range(6)]
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump({"workbook": {"elements": [
                {"id": f"x{i}", "text": t} for i, t in enumerate(textes)]}}, f)

        appels = []
        succes, _ = _traducteur(appels, refus={"c3", "c4", "c5"}).translate_json(
            chemin, "en", fiche="")
        ok("premier passage arrêté", not succes)
        with open(lots, encoding="utf-8") as f:
            note = json.load(f)
        ok("les lots réussis sont notés", sorted(note["lots"]) == ["0", "1", "2"],
           str(sorted(note["lots"])))

        appels = []
        succes, sortie = _traducteur(appels).translate_json(chemin, "en", fiche="")
        ok("la reprise aboutit", succes)
        ok("seuls les lots manquants repartent au modèle",
           sorted(appels) == ["c3", "c4", "c5"], str(sorted(appels)))
        with open(sortie, encoding="utf-8") as f:
            traduits = [b.get("translated_text") for b in json.load(f)["workbook"]["elements"]]
        ok("le résultat contient tous les lots", traduits == ["EN " + t for t in textes],
           str(traduits))
        ok("la note est effacée après succès", not os.path.exists(lots))

        # Un découpage différent invalide la note.
        _traducteur([], refus={"c5"}).translate_json(chemin, "en", fiche="")
        tr = _traducteur(appels := [])
        tr.target_batch_size = 2
        tr.translate_json(chemin, "en", fiche="")
        ok("autre découpage : tout est retraduit", len(appels) == 6, str(appels))

    print()
    for nom, cond, detail in checks:
        print(f"  {'OK  ' if cond else 'ÉCHEC'}  {nom}"
              + (f"   [{detail}]" if not cond and detail else ""))
    reussis = sum(1 for _, c, _ in checks if c)
    print(f"\n  {reussis}/{len(checks)}\n")
    return reussis == len(checks)


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
