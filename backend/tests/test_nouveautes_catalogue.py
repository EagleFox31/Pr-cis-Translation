"""Catalogue des nouveautés : complet, cohérent, aligné sur la version livrée.

Ce qui est MESURÉ :
  • 28 éléments, ids uniques (ils servent d'ancres et de clés « vu ») ;
  • type et domaine dans les listes fermées ; dates ISO valides ;
  • FR et EN complets (titre, resume, detail non vides), textes courts
    présents pour chaque élément phare, 4 phares au plus ;
  • VERSION = version du package.json racine (le seul numéro que voit
    l'utilisateur) ; DATE_VERSION = date de l'élément le plus récent.
"""

import json
from datetime import date
from pathlib import Path

import racine  # noqa: F401  -- met backend/ sur le chemin

from app.content import nouveautes as cat

RACINE = Path(__file__).resolve().parents[2]
# Portées Conventional Commits sans effet visible pour l'utilisateur.
PORTEES_INTERNES = {"release", "ci", "build", "deps", "infra", "deploy"}


def test_nombre_et_ids_uniques():
    ids = [e["id"] for e in cat.FONCTIONNALITES]
    assert len(ids) == 28
    assert len(set(ids)) == len(ids)


def test_types_domaines_dates():
    for e in cat.FONCTIONNALITES:
        assert e["type"] in cat.TYPES, e["id"]
        assert e["domaine"] in cat.DOMAINES, e["id"]
        assert e["importance"] in (1, 2, 3), e["id"]
        date.fromisoformat(e["date"])
        if e.get("lien"):
            assert e["lien"].startswith("/"), e["id"]


def test_audience_admin_filtree():
    for e in cat.FONCTIONNALITES:
        assert e.get("audience", "tous") in cat.AUDIENCES, e["id"]
    interne = {**cat.FONCTIONNALITES[0], "id": "outil-admin", "audience": "admin", "phare": False}
    from datetime import datetime
    from app.services.nouveautes import a_voir
    origine = cat.FONCTIONNALITES
    cat.FONCTIONNALITES = [*origine, interne]
    try:
        assert "outil-admin" not in {e["id"] for e in cat.elements("fr")}
        assert "outil-admin" in {e["id"] for e in cat.elements("fr", admin=True)}
        vues = datetime(2000, 1, 1)
        assert "outil-admin" not in {e["id"] for e in a_voir(vues, "fr")["elements"]}
        assert "outil-admin" in {e["id"] for e in a_voir(vues, "fr", admin=True)["elements"]}
    finally:
        cat.FONCTIONNALITES = origine


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
    assert len(fr) == len(en) == 27
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


def ecart_catalogue(journal: str, version: str, elements: list[dict]) -> str | None:
    """Message d'erreur si `version` annonce des « Features » visibles sans
    élément public du catalogue daté depuis la version précédente, sinon None."""
    import re

    # Sections de la plus récente à la plus ancienne : [version](lien) (date)
    entetes = list(re.finditer(
        r"^## \[(\d+\.\d+\.\d+)\]\([^)]*\) \((\d{4}-\d{2}-\d{2})\)", journal, re.M))
    rang = next((i for i, m in enumerate(entetes) if m.group(1) == version), None)
    if rang is None or rang + 1 >= len(entetes):
        return None
    section = journal[entetes[rang].end():entetes[rang + 1].start()]
    if "### Features" not in section:
        return None
    features = section.split("### Features", 1)[1].split("\n### ", 1)[0]
    portees = re.findall(r"^\* (?:\*\*([\w-]+):\*\* )?", features, re.M)
    # Outillage (release, CI, build…) : rien à montrer dans les nouveautés.
    if portees and all(p in PORTEES_INTERNES for p in portees):
        return None
    precedente = entetes[rang + 1].group(2)
    publics = [e["date"] for e in elements if e.get("audience", "tous") == "tous"]
    # « >= » : deux releases le même jour partagent la date (1.9.0 et 1.10.0).
    if publics and max(publics) >= precedente:
        return None
    return (
        f"La version {version} annonce des fonctionnalités, mais aucun élément "
        f"public du catalogue n'est daté depuis la version précédente ({precedente}) : "
        "ajouter les nouveautés dans backend/app/content/nouveautes.py (FR et EN), "
        "puis lancer backend/scripts/exporter_fonctionnalites.py"
    )


def test_version_avec_fonctionnalites_publiee_au_catalogue():
    """Une version dont le CHANGELOG annonce des « Features » visibles doit
    ajouter au moins un élément public au catalogue depuis la version précédente.

    Release Please écrit la section de la version dans la PR de release : ce
    test échoue donc sur cette PR tant que les nouveautés ne sont pas publiées
    (oubli constaté en 1.8.0 et 1.9.0 malgré la case du modèle de PR)."""
    journal = RACINE / "CHANGELOG.md"
    if not journal.exists():  # image Docker : pas de CHANGELOG, rien à vérifier
        return
    erreur = ecart_catalogue(journal.read_text(encoding="utf-8"), cat.VERSION, cat.FONCTIONNALITES)
    assert erreur is None, erreur


def _journal(features: str, date_prec: str = "2026-11-10") -> str:
    return (
        "## [2.0.0](https://x/compare/v1.0.0...v2.0.0) (2026-11-18)\n\n\n"
        f"### Features\n\n{features}\n\n### Bug Fixes\n\n* **ui:** correctif\n\n"
        f"## [1.0.0](https://x/compare/v0.9.0...v1.0.0) ({date_prec})\n"
    )


def test_ecart_catalogue_cas_limites():
    anciens = [{"date": "2026-11-09"}, {"date": "2026-11-17", "audience": "admin"}]
    # Non-régression 1.8.0 / 1.9.0 : fonctionnalité visible, catalogue ancien → échec.
    assert ecart_catalogue(_journal("* **translate:** mode gratuit"), "2.0.0", anciens)
    assert ecart_catalogue(_journal("* tarifs revus"), "2.0.0", anciens)
    # Une seule portée visible parmi des internes suffit à exiger le catalogue.
    assert ecart_catalogue(_journal("* **ci:** a\n* **ui:** b"), "2.0.0", anciens)
    # Outillage seul (1.10.0 : annonce WhatsApp des releases) → rien à publier.
    assert ecart_catalogue(_journal("* **release:** annonce\n* **ci:** cache"), "2.0.0", anciens) is None
    # Release le même jour que la précédente : un élément de ce jour suffit.
    meme_jour = [{"date": "2026-11-18"}]
    assert ecart_catalogue(_journal("* **ui:** b", "2026-11-18"), "2.0.0", meme_jour) is None
    # Version absente ou première version : rien à comparer.
    assert ecart_catalogue(_journal("* **ui:** b"), "9.9.9", anciens) is None
    assert ecart_catalogue(_journal("* **ui:** b"), "1.0.0", anciens) is None


if __name__ == "__main__":
    import sys

    echecs = 0
    for nom, fn in list(globals().items()):
        if nom.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  OK  {nom}")
            except Exception as exc:  # noqa: BLE001
                echecs += 1
                print(f"  ECHEC  {nom} : {exc!r}")
    sys.exit(1 if echecs else 0)


def test_version_suivie_par_release_please():
    """La release monte package.json : VERSION et l'instantané SEO doivent
    suivre dans la même PR, sinon test_version_alignee casse la release."""
    conf = json.loads((RACINE / "release-please-config.json").read_text(encoding="utf-8"))
    extra = {f["path"]: f for f in conf["packages"]["."].get("extra-files", [])}
    assert extra["backend/app/content/nouveautes.py"]["type"] == "generic"
    assert extra["frontend/seo/fonctionnalites.json"]["jsonpath"] == "$.version"
    source = (RACINE / "backend/app/content/nouveautes.py").read_text(encoding="utf-8")
    assert any(l.startswith("VERSION = ") and "x-release-please-version" in l
               for l in source.splitlines())
