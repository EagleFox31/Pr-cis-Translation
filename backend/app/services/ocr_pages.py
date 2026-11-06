"""Mémoire de la lecture des scans, page par page, à côté de la traduction.

Pour une traduction `<translation_path>` (le JSON des pages), le dossier
`<translation_path>.ocr/` garde :

- `p0012.json` : {"statut": "ok" | "blanche" | "illisible", "motif": ...}
- `p0012.pdf`  : la page lue (fond du scan + texte reconnu), pour `ok` seulement
- `choix.json` : {"12": "original" | "vide" | "retirer"} — ce que l'utilisateur
  a décidé pour une page illisible ou hors sélection (« traduire » n'est pas un
  état : la page devient traduite)
- `selection.json` : [3, 4, 7] — les pages que le job devait traduire, quand
  il n'en visait qu'une partie (les autres sont « hors sélection »)

Toutes les écritures sont atomiques (`os.replace`). Chaque page `ok` reste un
document à part : le cache de traduction y désigne ses images par numéro interne
(`xref`), et ces numéros ne changent jamais tant que le fichier ne bouge pas.

Les statuts `blanche` et `illisible` ne sont jamais facturés (voir `jobs.py`).
"""
from __future__ import annotations

import json
import os
import re
import threading

STATUTS = ("ok", "blanche", "illisible")
CHOIX = ("original", "vide", "retirer")
_PAGE = re.compile(r"^p(\d{4,})\.json$")

_verrous: dict[str, threading.Lock] = {}
_verrous_garde = threading.Lock()


def _verrou(chemin: str) -> threading.Lock:
    cle = os.path.normcase(os.path.abspath(chemin))
    with _verrous_garde:
        return _verrous.setdefault(cle, threading.Lock())


def dossier(translation_path: str) -> str:
    return translation_path + ".ocr"


def _nom(page: int) -> str:
    return f"p{page:04d}"


def _ecrire(chemin: str, octets: bytes) -> None:
    tmp = f"{chemin}.{os.getpid()}.{threading.get_ident()}.tmp"
    try:
        with open(tmp, "wb") as f:
            f.write(octets)
        os.replace(tmp, chemin)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _ecrire_json(chemin: str, valeur) -> None:
    _ecrire(chemin, json.dumps(valeur, ensure_ascii=False).encode("utf-8"))


def _lire_json(chemin: str):
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# ── Pages ────────────────────────────────────────────────────────────────────
def lire(translation_path: str, page: int) -> dict | None:
    """{"statut", "motif"} de la page, ou None si elle n'a jamais été lue."""
    info = _lire_json(os.path.join(dossier(translation_path), _nom(page) + ".json"))
    if not isinstance(info, dict) or info.get("statut") not in STATUTS:
        return None
    return {"statut": info["statut"], "motif": info.get("motif")}


def ecrire(translation_path: str, page: int, statut: str, motif: str | None = None,
           pdf: bytes | None = None) -> None:
    """Enregistre la lecture d'une page. Le PDF est posé AVANT le JSON : un
    JSON `ok` sans son PDF n'existe jamais, même après une coupure."""
    if statut not in STATUTS:
        raise ValueError(f"statut inconnu : {statut}")
    d = dossier(translation_path)
    os.makedirs(d, exist_ok=True)
    base = os.path.join(d, _nom(page))
    if statut == "ok":
        if not pdf:
            raise ValueError("une page `ok` demande son PDF")
        _ecrire(base + ".pdf", pdf)
    _ecrire_json(base + ".json", {"statut": statut, "motif": motif})
    if statut != "ok":
        try:
            os.remove(base + ".pdf")
        except OSError:
            pass


def effacer(translation_path: str, page: int) -> None:
    """Oublie la lecture d'une page (retour arrière d'une inclusion refusée)."""
    base = os.path.join(dossier(translation_path), _nom(page))
    for ext in (".json", ".pdf"):
        try:
            os.remove(base + ext)
        except OSError:
            pass


def pdf_de(translation_path: str, page: int) -> bytes | None:
    try:
        with open(os.path.join(dossier(translation_path), _nom(page) + ".pdf"), "rb") as f:
            return f.read()
    except OSError:
        return None


def lister(translation_path: str) -> dict[int, dict]:
    """{numéro: {"statut", "motif"}} de toutes les pages lues."""
    d = dossier(translation_path)
    try:
        noms = os.listdir(d)
    except OSError:
        return {}
    out: dict[int, dict] = {}
    for nom in noms:
        m = _PAGE.match(nom)
        if not m:
            continue
        info = lire(translation_path, int(m.group(1)))
        if info:
            out[int(m.group(1))] = info
    return out


def pages_illisibles(translation_path: str) -> dict[int, str | None]:
    """{numéro: motif} des pages illisibles (les blanches n'en font pas partie)."""
    return {n: i["motif"] for n, i in sorted(lister(translation_path).items())
            if i["statut"] == "illisible"}


def pages_blanches(translation_path: str) -> list[int]:
    """Pages lues sans aucun texte : rien à traduire, livrées telles quelles."""
    return sorted(n for n, i in lister(translation_path).items() if i["statut"] == "blanche")


def pages_non_facturables(translation_path: str) -> set[int]:
    """Pages `illisible` ou `blanche` : jamais facturées."""
    return {n for n, i in lister(translation_path).items()
            if i["statut"] in ("illisible", "blanche")}


# ── Choix de l'utilisateur ───────────────────────────────────────────────────
def lire_choix(translation_path: str) -> dict[int, str]:
    brut = _lire_json(os.path.join(dossier(translation_path), "choix.json"))
    if not isinstance(brut, dict):
        return {}
    out: dict[int, str] = {}
    for cle, valeur in brut.items():
        try:
            n = int(cle)
        except (TypeError, ValueError):
            continue
        if valeur in CHOIX:
            out[n] = valeur
    return out


def ecrire_choix(translation_path: str, pages: list[int], choix: str | None) -> None:
    """Pose (ou, avec None, retire) le choix des `pages`. Lecture-écriture sous
    verrou : deux requêtes simultanées ne s'écrasent pas."""
    d = dossier(translation_path)
    os.makedirs(d, exist_ok=True)
    chemin = os.path.join(d, "choix.json")
    with _verrou(chemin):
        actuel = lire_choix(translation_path)
        for n in pages:
            if choix is None:
                actuel.pop(n, None)
            else:
                actuel[n] = choix
        _ecrire_json(chemin, {str(n): c for n, c in sorted(actuel.items())})


def pages_vides(translation_path: str) -> set[int]:
    return {n for n, c in lire_choix(translation_path).items() if c == "vide"}


def pages_originales(translation_path: str) -> set[int]:
    """Pages dont l'utilisateur a choisi de garder l'original : livrées sans
    mention « page non traduite »."""
    return {n for n, c in lire_choix(translation_path).items() if c == "original"}


def pages_retirees(translation_path: str) -> set[int]:
    """Pages hors sélection que l'utilisateur a retirées du fichier livré."""
    return {n for n, c in lire_choix(translation_path).items() if c == "retirer"}


# ── Sélection du job ─────────────────────────────────────────────────────────
def ecrire_selection(translation_path: str, pages) -> None:
    d = dossier(translation_path)
    os.makedirs(d, exist_ok=True)
    _ecrire_json(os.path.join(d, "selection.json"), sorted(int(p) for p in pages))


def lire_selection(translation_path: str) -> set[int] | None:
    """Pages visées par le job, ou None (tout le document, ou traduction
    antérieure à ce fichier)."""
    brut = _lire_json(os.path.join(dossier(translation_path), "selection.json"))
    if not isinstance(brut, list):
        return None
    return {n for n in brut if isinstance(n, int) and n > 0} or None


def ecrire_budget(translation_path: str, job_id: str, traitees, consommees) -> None:
    """Pages parcourues par un job à budget (`traitees`) et celles qui ont
    pris une place du budget (`consommees`), relues à la clôture."""
    d = dossier(translation_path)
    os.makedirs(d, exist_ok=True)
    _ecrire_json(os.path.join(d, f"budget_{job_id}.json"),
                 {"traitees": sorted(set(traitees)), "consommees": sorted(set(consommees))})


def lire_budget(translation_path: str, job_id: str) -> tuple[set[int], set[int]] | None:
    brut = _lire_json(os.path.join(dossier(translation_path), f"budget_{job_id}.json"))
    if not isinstance(brut, dict):
        return None
    lues = [{n for n in brut.get(k) or [] if isinstance(n, int) and n > 0}
            for k in ("traitees", "consommees")]
    return lues[0], lues[1]


def pages_hors_selection(translation_path: str, total: int,
                         presentes: set[int]) -> set[int]:
    """Pages laissées hors de la sélection et pas encore incluses après coup
    (`presentes` : pages déjà dans la traduction). Une page qui a un état de
    lecture suit le chemin des pages illisibles ou blanches, pas celui-ci."""
    selection = lire_selection(translation_path)
    if not selection:
        return set()
    return (set(range(1, total + 1)) - selection - set(presentes)
            - set(lister(translation_path)))
