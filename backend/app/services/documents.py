"""Où vivent les documents, et combien de pages ils coûtent.

Ces trois fonctions ont été extraites de l'endpoint de traduction pour être
TESTABLES : noyées dedans, elles ne pouvaient être vérifiées que par des tests
tautologiques, et l'une d'elles cachait un vrai défaut de facturation
(cf. `cap_pages_for_plan`).
"""
from __future__ import annotations

import os

from app.config import TRANSLATIONS_DIR, logger


def build_job_paths(file_hash: str, target_lang: str) -> tuple[str, str]:
    """Où vivent les artefacts d'un document : (job_dir, lang_dir).

    Le magasin est adressé par le SEUL hash du contenu : `translations/{hash}/`.
    Le nom du fichier n'entre PAS dans le chemin — `contrat.pdf` et
    `contrat-final.pdf` au contenu identique, ou le même fichier déposé par deux
    comptes, partagent donc le même dossier et ne sont traduits qu'une fois. Le
    nom d'origine est conservé par Document, pour l'affichage seulement.

    Aucun segment de VERSION de moteur : on ne conserve plus le PDF rendu (il se
    recalcule à la demande depuis l'original + la traduction, sans DeepSeek), et
    ce qui est stocké — la traduction — ne dépend pas de la géométrie du moteur.
    Rien à invalider, donc rien à versionner.
    """
    job_dir = os.path.join(TRANSLATIONS_DIR, file_hash)
    lang_dir = os.path.join(job_dir, target_lang)
    return job_dir, lang_dir


def cap_pages_for_plan(pages_set, ext: str, page_limit: int):
    """Applique la limite de pages du plan à la sélection demandée.

    L'ancienne version, inline, ne forçait la page 1 que pour `ext == "pdf"` :
    un plan d'essai qui déposait un PPTX sans sélection obtenait TOUTES les
    diapositives traduites. La limite ne vaut que si elle s'applique à tout
    format qui sait sélectionner ses pages (PDF et PPTX ; le DOCX, sans notion
    de page à l'extraction, est refusé plus haut pour un plan limité).
    """
    if ext not in ("pdf", "pptx"):
        return pages_set
    if pages_set and len(pages_set) > page_limit:
        return {min(pages_set)}       # on ne garde que la 1re page demandée
    if not pages_set and page_limit == 1:
        return {1}                    # force page 1 uniquement
    return pages_set


def count_pages(file_bytes: bytes, ext: str) -> int:
    """Nombre de pages/diapositives du fichier déposé.

    Sert à FACTURER avant de traduire : sans sélection explicite, il faut bien
    savoir combien de pages on s'apprête à vendre. La lecture est bon marché
    (on ouvre le conteneur, on ne rend rien) et ne touche pas au moteur.

    En cas de doute, on renvoie 1 — jamais 0 : un fichier illisible qui
    coûterait « zéro page » serait une traduction gratuite illimitée pour qui
    sait fabriquer un en-tête invalide. Le vrai refus viendra de l'extraction,
    quelques lignes plus loin, avec un message qui parle.
    """
    try:
        if ext == "pdf":
            import fitz
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                return max(1, doc.page_count)
        if ext == "pptx":
            import io

            from pptx import Presentation
            return max(1, len(Presentation(io.BytesIO(file_bytes)).slides))  # pyrefly: ignore[not-callable]
    except Exception:
        logger.warning("Comptage de pages impossible (%s) — facturé 1 page.", ext)
    return 1
