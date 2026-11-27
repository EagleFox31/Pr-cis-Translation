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

import asyncio
import contextlib
import logging
import os
import threading
import zipfile
from contextlib import contextmanager
from io import BytesIO
from typing import Callable

from app.config import PREVIEW_CACHE_DIR, note
from app.core.files import get_file_hash
from app.services.file_libreoffice import ConversionAbandonnee, file_conversions
from engines.office import SOFFICE_PATH, preview_lock, prewarm

__all__ = ["SOFFICE_PATH", "preview_lock", "prewarm", "convert_to_pdf_bytes",
           "preparer_apercu", "preparer_apercu_async", "ConversionAbandonnee",
           "tour_conversion",
           "URGENTE", "A_L_AVANCE"]

# Priorités de la file LibreOffice (voir file_libreoffice).
URGENTE, A_L_AVANCE = file_conversions.URGENTE, file_conversions.A_L_AVANCE

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
                         use_cache: bool = True, tour_pris: bool = False,
                         priorite: int = URGENTE) -> bytes:
    """Convertit un document en PDF (bytes) pour l'aperçu. Les PDF sont
    renvoyés tels quels. Lève une exception si la conversion échoue.

    `use_cache=False` pour les documents JETABLES et uniques — le PPTX partiel
    d'un job, qui change à chaque diapositive traduite : le mettre en cache
    emplirait `_previews` d'un fichier par état intermédiaire, dont aucun ne
    resservira jamais.

    Toute conversion passe par la file LibreOffice. `priorite` : URGENTE par
    défaut (un écran l'attend) ; A_L_AVANCE pour un rendu de fond (aucun écran
    n'attend : il passe après les urgentes, et se refuse si la file est
    pleine, `ConversionAbandonnee`). `tour_pris` : l'appelant a déjà son tour
    (voir `tour_conversion`, pour le code asynchrone qui ne doit pas bloquer
    de thread à l'attendre, et `preparer_apercu`).
    """
    if ext == "pdf":
        return file_bytes

    from engines.office import convert_to_pdf
    if tour_pris:
        tour = contextlib.nullcontext
    else:
        def tour():
            return file_conversions.tour(a_l_avance=priorite == A_L_AVANCE)
    if not use_cache:
        with tour():
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
    # Le tour de file se prend AVANT le verrou du fichier : une conversion à
    # l'avance qui attend ne retient pas une demande urgente du même fichier.
    with tour(), _verrou_fichier(file_hash):
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


def preparer_apercu(chemin: str, ext: str,
                    abandon: "Callable[[], bool] | None" = None,
                    tour_pris: bool = False) -> None:
    """Convertit à l'avance un fichier déposé, pour que l'aperçu le retrouve en
    cache. Passe APRÈS les conversions urgentes ; le fichier n'est lu qu'à son
    tour (la file ne retient aucun octet). Lève `ConversionAbandonnee` si la
    file est pleine ou si `abandon()` dit que le fichier est remplacé.

    `tour_pris` : l'appelant (`preparer_apercu_async`) a déjà son tour."""
    tour = (contextlib.nullcontext() if tour_pris
            else file_conversions.tour(a_l_avance=True, abandon=abandon))
    with tour:
        with open(chemin, "rb") as f:
            donnees = f.read()
        convert_to_pdf_bytes(donnees, ext, tour_pris=True)


async def preparer_apercu_async(chemin: str, ext: str,
                                abandon: "Callable[[], bool] | None" = None) -> None:
    """`preparer_apercu` sans thread bloqué à attendre son tour : la coroutine
    attend, seule la conversion (tour pris) s'exécute dans un thread."""
    async with file_conversions.tour_async(a_l_avance=True, abandon=abandon):
        await asyncio.to_thread(preparer_apercu, chemin, ext, abandon, True)


def _en_cache(file_bytes: bytes, ext: str, use_cache: bool) -> bool:
    """Vrai si la conversion n'a rien à lancer : un PDF, ou un résultat déjà en
    cache (il se sert sans passer par la file)."""
    if ext == "pdf":
        return True
    if not use_cache:
        return False
    cache_path = os.path.join(PREVIEW_CACHE_DIR, f"{get_file_hash(file_bytes)}.pdf")
    return os.path.exists(cache_path)


@contextlib.asynccontextmanager
async def tour_conversion(file_bytes: bytes, ext: str, use_cache: bool = True,
                          priorite: int = URGENTE):
    """Prend, depuis une coroutine, le tour de conversion LibreOffice SANS
    occuper de thread, puis rend `tour_pris` à passer à `convert_to_pdf_bytes`
    (exécuté dans un thread, tour déjà pris). Sans conversion à lancer (PDF ou
    déjà en cache), aucun tour n'est pris et `tour_pris` est faux.

        async with tour_conversion(data, ext) as tour_pris:
            pdf = await run_in_threadpool(convert_to_pdf_bytes, data, ext,
                                          tour_pris=tour_pris)
    """
    if _en_cache(file_bytes, ext, use_cache):
        yield False
        return
    async with file_conversions.tour_async(a_l_avance=priorite == A_L_AVANCE):
        yield True


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
