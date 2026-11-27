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
import re
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


def office_illisible(data: bytes, ext: str) -> bool:
    """Vrai si `data` n'est pas un document Office lisible pour `ext`.

    Un .docx/.pptx/.xlsx est une archive ZIP dont la table des matières est À
    LA FIN : un envoi coupé en route (réseau, redémarrage du serveur) donne un
    fichier qui a la bonne extension mais qu'aucun moteur ne peut ouvrir. Le
    refuser au dépôt évite un job qui échoue plus loin sur « File is not a zip
    file ». Les autres extensions ne sont pas concernées (Faux)."""
    partie = _PARTIE_PRINCIPALE.get(ext)
    if partie is None:
        return False
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
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

    if not use_cache:
        return _convertir(file_bytes, ext)

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
        data = _convertir(file_bytes, ext)
        tmp = f"{cache_path}.{threading.get_ident()}.tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, cache_path)   # jamais un PDF à moitié écrit lu ailleurs
    from app.services.stockage import limiter_apercus
    limiter_apercus()
    return data


# Diapositives converties ensemble au plus. Le deck ENTIER d'un seul tenant a
# coûté 1 494 Mo à LibreOffice sur 75 diapositives (docs/etude-apercu-par-page.md),
# assez pour tuer le serveur à 1 Go ; une diapositive seule : ~300 Mo.
DIAPOS_PAR_CONVERSION = 1


def _convertir(file_bytes: bytes, ext: str) -> bytes:
    from engines.office import convert_to_pdf
    if ext != "pptx" or _nb_diapos(file_bytes) <= DIAPOS_PAR_CONVERSION:
        return convert_to_pdf(file_bytes, ext)
    return _pptx_par_diapos(file_bytes, convert_to_pdf)


def _nb_diapos(file_bytes: bytes) -> int:
    """Diapositives présentes dans l'archive, sans la décompresser (l'aperçu
    progressif convertit des decks d'une seule diapositive, un par page)."""
    try:
        with zipfile.ZipFile(BytesIO(file_bytes)) as archive:
            return sum(1 for n in archive.namelist()
                       if re.fullmatch(r"ppt/slides/slide\d+\.xml", n))
    except (zipfile.BadZipFile, ValueError, OSError, EOFError):
        return 0


def _pptx_par_diapos(file_bytes: bytes, convert_to_pdf) -> bytes:
    """Un PPTX converti `DIAPOS_PAR_CONVERSION` diapositives à la fois, puis
    réassemblé : même PDF que le deck entier, sans son pic de mémoire.

    Un lot rendu sans page (diapositive masquée, que LibreOffice n'exporte pas
    non plus dans le deck entier) est simplement absent du résultat."""
    import tempfile
    import fitz
    import engines
    eng = engines.new_engine("pptx")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        source = os.path.join(td, "source.pptx")
        with open(source, "wb") as f:
            f.write(file_bytes)
        try:
            eng._extract_zip(source)
            total = eng.slide_count()
            lot_path = os.path.join(td, "lot.pptx")
            with fitz.open() as sortie:
                for debut in range(1, total + 1, DIAPOS_PAR_CONVERSION):
                    nums = set(range(debut, min(total, debut + DIAPOS_PAR_CONVERSION - 1) + 1))
                    eng.build_partial_pptx(lot_path, max(nums), only_slides=nums)
                    with open(lot_path, "rb") as f:
                        rendu = convert_to_pdf(f.read(), "pptx")
                    with fitz.open(stream=rendu, filetype="pdf") as lot:
                        if lot.page_count > len(nums):
                            raise ValueError(f"{lot.page_count} page(s) rendue(s) "
                                             f"pour {len(nums)} diapositive(s)")
                        sortie.insert_pdf(lot)
                if not sortie.page_count:
                    raise ValueError("Aucune diapositive rendue.")
                return sortie.tobytes(garbage=3, deflate=True)
        finally:
            eng._cleanup_temp()


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
