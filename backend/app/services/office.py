"""Conversion en PDF pour l'aperçu — la couche qui décide de METTRE EN CACHE.

La conversion elle-même vit dans `engines.office` : c'est une capacité, pas une
politique. Ce module y ajoute ce qui relève de l'application — où conserver un
résultat, et quand ne pas le conserver.

L'aperçu côte-à-côte s'appuie sur pdf.js : pour obtenir un rendu EXACT des
formats non-PDF (DOCX, PPTX, TXT), on les convertit en PDF via LibreOffice
headless. La conversion ne sert QUE l'aperçu — le téléchargement garde le
format d'origine.
"""
from __future__ import annotations

import logging
import os
import threading
import zipfile
from contextlib import contextmanager
from io import BytesIO

from app.config import PREVIEW_CACHE_DIR, note
from app.core.files import get_file_hash
from engines.office import SOFFICE_PATH, preview_lock, prewarm

__all__ = ["SOFFICE_PATH", "preview_lock", "prewarm", "convert_to_pdf_bytes"]

if SOFFICE_PATH:
    note(logging.INFO, f"LibreOffice  ~  {SOFFICE_PATH}")
else:
    note(logging.WARNING, "LibreOffice introuvable : l'aperçu des formats "
                          "non-PDF sera indisponible.")


# Partie que tout document Office valide contient, par format.
_PARTIE_PRINCIPALE = {
    "docx": "word/document.xml",
    "pptx": "ppt/presentation.xml",
    "xlsx": "xl/workbook.xml",
}


def office_illisible(data: "bytes | str | os.PathLike", ext: str) -> bool:
    """Vrai si `data` n'est pas un document Office lisible pour `ext`.
    `data` est le contenu OU le chemin du fichier (relu sans le charger en
    mémoire).

    Un .docx/.pptx/.xlsx est une archive ZIP dont la table des matières est À
    LA FIN : un envoi coupé en route (réseau, redémarrage du serveur) donne un
    fichier qui a la bonne extension mais qu'aucun moteur ne peut ouvrir. Le
    refuser au dépôt évite un job qui échoue plus loin sur « File is not a zip
    file ». Les autres extensions ne sont pas concernées (Faux)."""
    partie = _PARTIE_PRINCIPALE.get(ext)
    if partie is None:
        return False
    try:
        source = BytesIO(data) if isinstance(data, (bytes, bytearray)) else data
        with zipfile.ZipFile(source) as archive:
            return partie not in archive.namelist()
    except (zipfile.BadZipFile, ValueError, OSError, EOFError):
        return True


def convert_to_pdf_bytes(file_bytes: bytes, ext: str,
                         use_cache: bool = True) -> bytes:
    """Convertit un document en PDF (bytes) pour l'aperçu. Les PDF sont
    renvoyés tels quels. Lève une exception si la conversion échoue.

    `use_cache=False` pour les documents JETABLES et uniques — le PPTX partiel
    d'un job, qui change à chaque diapositive traduite : le mettre en cache
    emplirait `_previews` d'un fichier par état intermédiaire, dont aucun ne
    resservira jamais.
    """
    if ext == "pdf":
        return file_bytes

    from engines.office import convert_to_pdf
    if not use_cache:
        return convert_to_pdf(file_bytes, ext)

    file_hash = get_file_hash(file_bytes)
    os.makedirs(PREVIEW_CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(PREVIEW_CACHE_DIR, f"{file_hash}.pdf")
    data = _lire_cache(cache_path)
    if data is not None:
        return data

    # Un verrou PAR FICHIER : trois demandes simultanées du même document
    # (aperçu ouvert deux fois, onglets) lançaient trois conversions complètes
    # l'une après l'autre — 3 × 40 s sur un gros PPTX. La deuxième et la
    # troisième attendent la première et repartent avec son résultat.
    with _verrou_fichier(file_hash):
        data = _lire_cache(cache_path)
        if data is not None:
            return data
        data = convert_to_pdf(file_bytes, ext)
        tmp = f"{cache_path}.{threading.get_ident()}.tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, cache_path)   # jamais un PDF à moitié écrit lu ailleurs
    from app.services.stockage import limiter_apercus
    limiter_apercus()
    return data


def _lire_cache(cache_path: str) -> bytes | None:
    if not os.path.exists(cache_path):
        return None
    try:
        with open(cache_path, "rb") as f:
            data = f.read()
    except OSError:
        return None
    # Servi = récent : la borne du cache efface d'abord les plus anciens.
    try:
        os.utime(cache_path)
    except OSError:
        pass
    return data


_verrous: dict[str, list] = {}          # hash -> [verrou, nombre d'utilisateurs]
_verrous_mutex = threading.Lock()


@contextmanager
def _verrou_fichier(file_hash: str):
    with _verrous_mutex:
        entree = _verrous.setdefault(file_hash, [threading.Lock(), 0])
        entree[1] += 1
    try:
        with entree[0]:
            yield
    finally:
        with _verrous_mutex:
            entree[1] -= 1
            if entree[1] == 0:
                _verrous.pop(file_hash, None)
