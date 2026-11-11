"""Catalogue des nouveautés : complet, cohérent, aligné sur la version livrée.

Ce qui est MESURÉ :
  • 19 éléments, ids uniques (ils servent d'ancres et de clés « vu ») ;
  • type et domaine dans les listes fermées ; dates ISO valides ;
  • FR et EN complets (titre, resume, detail non vides), textes courts
    présents pour chaque élément phare, 4 phares au plus ;
  • VERSION = version du package.json racine (le seul numéro que voit
    l'utilisateur) ; DATE_VERSION = date de l'élément le plus récent.
"""

import json
from datetime import date
from pathlib import Path

from app.content import nouveautes as cat

RACINE = Path(__file__).resolve().parents[2]


def test_nombre_et_ids_uniques():
    ids = [e["id"] for e in cat.FONCTIONNALITES]
    assert len(ids) == 19
    assert len(set(ids)) == len(ids)


def test_types_domaines_dates():
    for e in cat.FONCTIONNALITES:
        assert e["type"] in cat.TYPES, e["id"]
        assert e["domaine"] in cat.DOMAINES, e["id"]
        assert e["importance"] in (1, 2, 3), e["id"]
        date.fromisoformat(e["date"])
        if e.get("lien"):
            assert e["lien"].startswith("/"), e["id"]


def test_textes_complets_fr_en():
    for e in cat.FONCTIONNALITES:
        for lang in cat.LANGUES:
            textes = e[lang]
            champs = ["titre", "resume", "detail"]
            if e["phare"]:
                champs += ["titre_court", "resume_court"]
            for champ in champs:
                assert textes.get(champ, "").strip(), f"{e['id']} {lang}.{champ}"


def test_phares():
    phares = [e for e in cat.FONCTIONNALITES if e["phare"]]
    assert 1 <= len(phares) <= 4
    assert all(e.get("icone") for e in phares)
    assert [p["id"] for p in cat.phares("fr")] == [p["id"] for p in cat.phares("en")]


def test_elements_par_langue():
    fr, en = cat.elements("fr"), cat.elements("en")
    assert len(fr) == len(en) == 19
    assert [e["date"] for e in fr] == sorted((e["date"] for e in fr), reverse=True)
    assert cat.elements("de") == fr  # langue inconnue : repli sur le français


def test_version_alignee():
    pkg = json.loads((RACINE / "package.json").read_text(encoding="utf-8"))
    assert cat.VERSION == pkg["version"]
    assert cat.DATE_VERSION == max(e["date"] for e in cat.FONCTIONNALITES)


def test_instantane_seo_a_jour():
    import sys
    sys.path.insert(0, str(RACINE / "backend" / "scripts"))
    from exporter_fonctionnalites import CIBLE, instantane

    assert CIBLE.read_text(encoding="utf-8") == instantane(), (
        "frontend/seo/fonctionnalites.json n'est pas à jour : "
        "lancer backend/scripts/exporter_fonctionnalites.py"
    )
