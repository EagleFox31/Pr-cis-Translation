"""R2 : une seule police par famille dans un document traduit.

Le sous-ensemble embarqué ne couvre que les lettres de l'original. Si la
langue cible en demande d'autres et que le remplaçant est la même police ou
son clone métrique, toute la famille prend le remplaçant ; un remplaçant
seulement « proche » reste au cas par cas ; un rendu non traduit ne change pas.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.stdout.reconfigure(encoding="utf-8")

from engines.pdf.engine import PDFObjectEngine, _weight_class  # noqa: E402

EMB, CLONE = object(), object()
SOUS_ENSEMBLE = set("RAPORTNUELrapotnuel0123456789éèàç")


def moteur(couche, traduit=True, lang="en_EN"):
    eng = PDFObjectEngine()
    eng.reflow_lang = lang
    eng._rendu_traduit = traduit
    eng._pick_font = lambda raw, txt: EMB
    eng._renders_glyph = lambda f, c: f is CLONE or c in SOUS_ENSEMBLE

    def repli(raw, bold, italic):
        cle = (raw.split("+")[-1], _weight_class(raw, bold), bool(bold), bool(italic))
        eng.__dict__.setdefault("_fallback_couche", {})[cle] = couche
        return CLONE
    eng._full_fallback_font = repli
    return eng


CAS = [
    ("clone : toute la famille passe au clone",
     lambda: moteur("clone")._famille_remplacee("ABCDEF+Calibri", False, False) is True),
    ("police identique : toute la famille la prend",
     lambda: moteur("identique")._famille_remplacee("Calibri", True, False) is True),
    ("police seulement proche : cas par cas",
     lambda: moteur("proche")._famille_remplacee("Calibri", False, False) is False),
    ("rendu non traduit : police embarquée gardée",
     lambda: moteur("clone", traduit=False)._famille_remplacee("Calibri", False, False) is False),
]


def test_sous_ensemble_complet():
    eng = moteur("clone")
    eng._renders_glyph = lambda f, c: True
    return eng._famille_remplacee("Calibri", False, False) is False


CAS.append(("sous-ensemble qui couvre l'alphabet : gardé", test_sous_ensemble_complet))

if __name__ == "__main__":
    ok = 0
    for nom, f in CAS:
        r = f()
        ok += bool(r)
        print(f"  {'OK  ' if r else 'ÉCHEC'}  {nom}")
    print(f"\n  {ok}/{len(CAS)}")
    sys.exit(0 if ok == len(CAS) else 1)
