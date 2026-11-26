"""Messages de traduction gardés avec le document (avis_document).

Un message envoyé pendant la traduction doit se relire plus tard, quand on
rouvre le document depuis « Mes documents ». Un fichier abîmé ne doit rien
casser : il ne renvoie simplement aucun message.

Exécution :  cd backend && venv/Scripts/python.exe tests/test_avis_document.py
"""
from __future__ import annotations
import os
import shutil
import sys
import tempfile

import racine  # noqa: F401  -- met backend/ sur le chemin

import app.services.avis_document as avis_document            # noqa: E402
import app.services.translation_runner as runner              # noqa: E402


def run() -> int:
    checks = []

    def ok(nom, cond, detail=""):
        checks.append((nom, bool(cond), detail))
        print(f"  {'OK   ' if cond else 'ÉCHEC'} {nom}" + (f"  ({detail})" if detail and not cond else ""))

    dossier = tempfile.mkdtemp(prefix="avis_")
    trad = os.path.join(dossier, "translation.json")
    emis = []
    ancien_emit = runner.jobs.emit
    runner.jobs.emit = lambda job_id, type_, donnees: emis.append((job_id, type_, donnees))
    try:
        ok("LECTURE  aucun fichier = aucun message", avis_document.lire(trad) == [])
        ok("LECTURE  sans chemin = aucun message", avis_document.lire(None) == [])

        # 0) Quels messages montrer selon l'état du document. Le fichier est
        #    partagé entre les envois d'un même fichier : un document en file
        #    héritait de « Termes harmonisés… L'aperçu est à jour ».
        tous = [{"type": "ocr", "pages": [3]}, {"type": "coherence", "slides": [2]}]
        pour = avis_document.pour_document
        ok("ETAT  terminé : tous les messages", pour(tous, "done", True) == tous)
        ok("ETAT  en erreur : aucun", pour(tous, "error", True) == [])
        ok("ETAT  pas encore commencé : aucun", pour(tous, "translating", False) == [])
        ok("ETAT  en cours : pas d'harmonisation (fin de traitement)",
           pour(tous, "translating", True) == [tous[0]])
        ok("ETAT  en pause : pas d'harmonisation", pour(tous, "paused", True) == [tous[0]])

        # 1) Message émis pendant la traduction : envoyé ET gardé
        runner._avis("job-1", trad, "coherence", {"slides": [1, 2, 4]})
        ok("EMIS  l'écran ouvert reçoit le message",
           emis == [("job-1", "coherence", {"slides": [1, 2, 4]})], str(emis))
        ok("RELU  le message se retrouve plus tard",
           avis_document.lire(trad) == [{"type": "coherence", "slides": [1, 2, 4]}],
           str(avis_document.lire(trad)))

        # 2) Plusieurs types, dans l'ordre d'apparition
        avis_document.ajouter(trad, "ocr", {"pages": 3})
        avis_document.ajouter(trad, "objets", {"non_traites": [{"type": "smartart"}]})
        ok("ORDRE  les messages restent dans l'ordre",
           [a["type"] for a in avis_document.lire(trad)] == ["coherence", "ocr", "objets"])

        # 3) Une reprise remplace le message du même type, sans l'empiler
        avis_document.ajouter(trad, "coherence", {"slides": [7]})
        coh = [a for a in avis_document.lire(trad) if a["type"] == "coherence"]
        ok("REPRISE  un seul message par type, le plus récent",
           coh == [{"type": "coherence", "slides": [7]}], str(coh))

        # 4) Type inconnu ignoré
        avis_document.ajouter(trad, "inconnu", {"x": 1})
        ok("TYPE  un type inconnu n'est pas gardé",
           all(a["type"] != "inconnu" for a in avis_document.lire(trad)))

        ok("TYPE  « images » n'est pas gardé (aucune passe ne l'écrit)",
           (avis_document.ajouter(trad, "images", {"traduites": 1}) or True)
           and all(a["type"] != "images" for a in avis_document.lire(trad)))

        # 4b) Une passe qui n'a plus rien à dire retire son ancien message
        avis_document.retirer(trad, "coherence")
        ok("RETRAIT  l'ancien message de cohérence disparaît",
           [a["type"] for a in avis_document.lire(trad)] == ["ocr", "objets"],
           str(avis_document.lire(trad)))
        date = os.path.getmtime(avis_document.chemin(trad))
        avis_document.retirer(trad, "coherence")
        ok("RETRAIT  rien à retirer : le fichier n'est pas réécrit",
           os.path.getmtime(avis_document.chemin(trad)) == date)
        avis_document.ajouter(trad, "objets", None)
        ok("RETRAIT  None retire aussi", [a["type"] for a in avis_document.lire(trad)] == ["ocr"])

        # 4c) Ménage du stockage : le message suit sa traduction
        from app.services.stockage import _TABLE_IMAGES
        m = _TABLE_IMAGES.match("abc.json.avis.json")
        ok("MENAGE  le fichier de messages est rattaché à sa traduction",
           m is not None and m["trad"] == "abc.json")
        ok("MENAGE  le fichier temporaire aussi",
           _TABLE_IMAGES.match("abc.json.avis.json.tmp") is not None)

        # 5) Fichier abîmé : aucun message, aucune erreur
        with open(avis_document.chemin(trad), "w", encoding="utf-8") as f:
            f.write("{pas du json")
        ok("ABIME  un fichier illisible ne renvoie rien", avis_document.lire(trad) == [])
        with open(avis_document.chemin(trad), "w", encoding="utf-8") as f:
            f.write('{"type": "ocr"}')
        ok("ABIME  un contenu inattendu ne renvoie rien", avis_document.lire(trad) == [])
        avis_document.ajouter(trad, "ocr", {"pages": 2})
        ok("ABIME  on peut réécrire par-dessus",
           avis_document.lire(trad) == [{"type": "ocr", "pages": 2}])

        # 6) Écriture impossible : la traduction continue
        try:
            avis_document.ajouter(os.path.join(dossier, "absent", "t.json"), "ocr", {"pages": 1})
            sans_erreur = True
        except Exception:
            sans_erreur = False
        ok("ECRITURE  un échec d'écriture ne bloque pas la traduction", sans_erreur)
    finally:
        runner.jobs.emit = ancien_emit
        shutil.rmtree(dossier, ignore_errors=True)

    bons = sum(1 for _, c, _ in checks if c)
    print(f"{bons}/{len(checks)}")
    return 0 if bons == len(checks) else 1


if __name__ == "__main__":
    sys.exit(run())
