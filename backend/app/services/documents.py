"""Où vivent les documents, et combien de pages ils coûtent.

Ces trois fonctions ont été extraites de l'endpoint de traduction pour être
TESTABLES : noyées dedans, elles ne pouvaient être vérifiées que par des tests
tautologiques, et l'une d'elles cachait un vrai défaut de facturation
(cf. `cap_pages_for_plan`).
"""
from __future__ import annotations

import os
import re
import shutil
import threading
from datetime import datetime, timedelta, timezone

from app.config import TRANSLATIONS_DIR, logger
from app.core.files import pages_token
from app.models.plans import get_plan_storage

# Sans stockage inclus, un document reste accessible ce temps après sa
# traduction ; ensuite il est ARCHIVÉ : listé, grisé, jamais effacé, et rouvert
# dès que le compte passe à un forfait avec stockage (étude Nouveautés §11).
ACCES_SANS_STOCKAGE = timedelta(days=30)


def acces_jusqu_au(user, doc) -> datetime | None:
    """Fin de l'accès à CE document, ou `None` si l'accès est illimité."""
    if get_plan_storage(user.plan) > 0 or doc.created_at is None:
        return None
    debut = doc.created_at
    if debut.tzinfo is None:                 # SQLite rend des dates naïves
        debut = debut.replace(tzinfo=timezone.utc)
    return debut + ACCES_SANS_STOCKAGE


def acces_archive(user, doc, maintenant: datetime | None = None) -> bool:
    """Le document est-il archivé (listé mais plus ouvrable) pour ce compte ?
    Une traduction en cours ne l'est jamais."""
    if doc.status == "translating":
        return False
    fin = acces_jusqu_au(user, doc)
    return fin is not None and (maintenant or datetime.now(timezone.utc)) >= fin

WORDS_PER_PAGE = 500


def text_pages(words: int) -> int:
    """Une page équivalente par tranche commencée de 500 mots."""
    return max(1, (words + WORDS_PER_PAGE - 1) // WORDS_PER_PAGE)


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


def translation_path_for(lang_dir: str, ext: str, pages_set, qsuffix: str) -> str:
    """La traduction persistante d'une sélection : `pages*.json` (PDF, moteur
    v2) ou `translated*.json` (DOCX/PPTX/XLSX). La route qui lance le job et la
    facturation d'une reprise doivent nommer le MÊME fichier."""
    ptok = pages_token(pages_set)
    psuffix = f"_{ptok}" if ptok else ""
    base = "pages" if ext == "pdf" else "translated"
    return os.path.join(lang_dir, f"{base}{qsuffix}{psuffix}.json")


def pages_faites(translation_path: str, ext: str, pages_set, total: int) -> int:
    """Nombre de pages de la sélection (`total` au plus) déjà traduites sur disque."""
    return min(total, len(pages_traduites(translation_path, ext, pages_set, total)))


def pages_traduites(translation_path: str, ext: str, pages_set, total: int) -> set[int]:
    """Pages de la sélection déjà traduites sur disque.

    Lu au démarrage pour ne rendre que les pages NON traduites d'un job coupé
    (redémarrage, pause, annulation),
    et à la reprise pour ne débiter que le reste. Seuls le PDF (cache page par
    page) et le PPTX (fichier de reprise par diapositive) gardent un travail
    partiel ; un DOCX/XLSX n'a rien tant que la traduction n'est pas écrite.
    Une lecture impossible vaut « rien de fait » : on rend trop plutôt que de
    facturer une page que l'on ne peut pas montrer."""
    import json

    def _dans(n: int) -> bool:
        return not pages_set or n in pages_set

    if ext != "pdf" and os.path.exists(translation_path):
        # Traduction écrite : le job avait fini, toute la sélection est faite.
        return set(pages_set) if pages_set else set(range(1, total + 1))
    try:
        if ext == "pdf":
            with open(translation_path, encoding="utf-8") as f:
                data = json.load(f)
            # Même critère que le moteur (`engines/pdf/stream.py`) pour
            # tenir une page pour traduite : un paragraphe porte sa traduction.
            faites = {pg["page_num"] for pg in data.get("pages", [])
                      if _dans(pg.get("page_num") or 0) and any(
                          e.get("tr_tagged") for e in pg.get("elements", [])
                          if e.get("type") == "paragraph")}
            return faites
        if ext == "pptx":
            dossier, nom = os.path.split(translation_path)
            with open(os.path.join(dossier, "reprise_" + nom), encoding="utf-8") as f:
                slides = json.load(f)["slides"]
            return {int(k) for k, v in slides.items()
                    if isinstance(v, dict) and _dans(int(k))}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        pass
    return set()


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
    # Office/TXT n'ont pas de pagination fiable sans rendu. Compter le texte
    # réellement extrait par nos moteurs évite qu'un classeur immense coûte
    # une seule page. Les formules, nombres et cellules vides ne sont pas des mots.
    if ext in ("docx", "xlsx"):
        from app.services.beta_meter import office_cost
        cost = office_cost(file_bytes, ext)
        return text_pages(cost.units if ext == "docx" else cost.words)
    if ext == "txt":
        from app.services.beta_meter import word_count
        words = word_count(file_bytes.decode("utf-8-sig", errors="replace"))
        if words == 0:
            raise ValueError("Ce fichier ne contient pas de texte à traduire.")
        return text_pages(words)
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


def pages_avec_texte(file_bytes: bytes, ext: str) -> set[int] | None:
    """Numéros (1-basés) des pages qui contiennent du texte extractible.

    `None` = « la question ne se pose pas » : format non concerné, ou fichier
    illisible. L'appelant traite alors le document comme avant.

    LE DÉFAUT QUE CECI CORRIGE
    --------------------------
    Un PDF scanné est une suite d'IMAGES. Aucun caractère n'y est extractible :
    le moteur n'en tire rien, ne traduit rien, et rend le document INCHANGÉ.
    Or la facturation, elle, comptait les pages du conteneur — mesuré sur un
    scan synthétique de 3 pages : 3 pages débitées, 0 élément de texte extrait.
    L'utilisateur payait, recevait son document tel quel, et son crédit avait
    disparu. Rien, nulle part, ne le signalait.

    POURQUOI « ZÉRO CARACTÈRE » ET NON UN SEUIL
    -------------------------------------------
    Il serait tentant d'écrire « moins de N caractères = page scannée ». Ce
    serait un nombre choisi sur les documents qu'on a sous la main, qui
    trancherait de travers sur ceux qu'on n'a pas : une page de garde ne
    portant qu'un titre est parfaitement traduisible.

    « Aucun caractère extractible » n'est pas un réglage, c'est un fait
    vérifiable : il n'y a rien à lire, donc rien à traduire, donc rien à
    facturer. La règle vaut pour tout PDF, quelle que soit sa provenance.

    Ce n'est PAS de l'OCR et cela ne prétend pas l'être : on ne devine pas ce
    que contient l'image, on constate seulement qu'on ne l'a pas lue.
    """
    if ext != "pdf":
        return None
    try:
        import fitz
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            return {i + 1 for i, page in enumerate(doc)
                    if page.get_text().strip()}
    except Exception:
        # Illisible : on ne prétend rien. `count_pages` facturera 1 page et le
        # refus viendra de l'extraction, avec un message qui parle.
        logger.warning("Analyse du texte impossible (%s) — document traité "
                       "comme s'il contenait du texte.", ext)
        return None


def reglages_de(doc) -> dict:
    """Réglages enregistrés d'un Document ({} si absents ou illisibles)."""
    import json
    try:
        r = json.loads(doc.reglages or "{}")
    except (ValueError, TypeError):
        return {}
    return r if isinstance(r, dict) else {}


def _selection_du_document(doc):
    """(chemin de traduction, ext, sélection) que le job du Document écrivait,
    depuis ses réglages enregistrés ; None sans original."""
    if doc is None or not doc.original_path:
        return None
    reglages = reglages_de(doc)
    pages = {int(p) for p in str(reglages.get("pages") or "").split(",") if p.strip()}
    ext = os.path.splitext(doc.original_path)[1].lstrip(".").lower()
    lang_dir = os.path.join(os.path.dirname(doc.original_path), doc.target_lang)
    # Suffixe COMPLET (qualité, version OCR) ; les documents d'avant ce
    # champ n'ont que la qualité.
    qsuffix = reglages.get("qsuffix")
    if not isinstance(qsuffix, str):
        qsuffix = "_precise" if reglages.get("precise") else ""
    return translation_path_for(lang_dir, ext, pages or None, qsuffix), ext, pages or None


def pages_selectionnees(doc) -> set[int] | None:
    """Pages visées par le travail d'un Document ; None = tout le document."""
    sel = _selection_du_document(doc)
    return sel[2] if sel else None


def chemin_traduction_du_document(doc) -> str | None:
    """Fichier de traduction (partielle) d'un Document : le ménage doit le
    garder tant que le document peut être repris."""
    sel = _selection_du_document(doc)
    return sel[0] if sel else None


def pages_faites_du_document(doc) -> int:
    """`pages_faites` d'un Document, depuis ses réglages enregistrés
    (sélection effective, qualité) : le fichier que son job écrivait."""
    sel = _selection_du_document(doc)
    if sel is None:
        return 0
    chemin, ext, pages = sel
    return pages_faites(chemin, ext, pages, doc.page_count or 0)


def traduction_partielle_du_document(doc, payees: int) -> tuple[str, set[int]] | None:
    """(fichier, pages livrables) d'un document arrêté (interrompu, en pause,
    annulé) ; None si rien de traduit n'est à livrer.

    Ses pages traduites sont payées : il les reçoit, en aperçu comme en
    téléchargement, le reste en langue d'origine (décision E de l'étude
    reprise/pause/annulation). Le fichier est PARTAGÉ par empreinte entre
    comptes : un autre a pu y traduire plus que ce document n'a payé. On ne
    livre donc que `payees` pages traduites au plus, les premières de la
    sélection. Le PDF se rend depuis son cache page par page, le PPTX depuis
    son fichier de reprise par diapositive, ou depuis la traduction finale
    qu'un autre compte a terminée entre-temps (elle remplace la reprise) ; un
    DOCX/XLSX n'a rien de partiel tant que sa traduction n'est pas écrite."""
    from app.services.jobs import STATUTS_REPRENABLES
    if doc.status not in STATUTS_REPRENABLES or payees <= 0:
        return None
    sel = _selection_du_document(doc)
    if sel is None:
        return None
    chemin, ext, pages = sel
    if ext not in ("pdf", "pptx"):
        return None
    faites = pages_traduites(chemin, ext, pages, doc.page_count or 0)
    livrables = set(sorted(faites)[:payees])
    if ext == "pptx":
        dossier, nom = os.path.split(chemin)
        reprise = os.path.join(dossier, "reprise_" + nom)
        if os.path.isfile(reprise):
            chemin = reprise
    if not livrables or not os.path.isfile(chemin):
        return None
    return chemin, livrables


def copie_du_document(doc) -> str:
    """Traduction propre à CE document, créée au premier changement d'image.

    La traduction d'origine peut servir à d'autres comptes (magasin partagé) :
    on n'y touche pas. La copie (JSON, table et images) vit à côté, sous un nom
    qui reste une traduction pour le balayage et que seul ce document vise."""
    from app.services import images_document, render_cache
    trad = doc.translated_path
    copie = copie_prevue(doc)
    if copie == trad:
        return trad
    with verrou_copie(copie):
        # Deux changements simultanés : le second réutilise la copie du premier
        # au lieu de l'écraser (une page déjà reportée et débitée y serait perdue).
        # La copie n'est pas comparée à la traduction courante : le seul cas où
        # elle en diffère (clôture `done` rejouée, jobs.py) ramène de toute façon
        # `translated_path` sur la traduction partagée, et la copie est refaite.
        if os.path.isfile(copie):
            return copie
        for suffixe in (".images", ".ocr"):
            if os.path.isdir(trad + suffixe):
                shutil.copytree(trad + suffixe, copie + suffixe, dirs_exist_ok=True,
                                ignore=shutil.ignore_patterns("*.tmp"))
        for source, cible in ((images_document.chemin_table(trad), images_document.chemin_table(copie)),
                              (trad + ".source.pdf", copie + ".source.pdf")):
            if os.path.isfile(source):
                shutil.copy2(source, cible)
        # Le JSON en dernier et d'un seul coup : sa présence vaut copie complète.
        with render_cache.verrou_traduction(trad).lire():
            shutil.copy2(trad, copie + ".tmp")
        os.replace(copie + ".tmp", copie)
    return copie


def copie_prevue(doc) -> str:
    """Chemin de la traduction propre au document (existante ou à créer)."""
    base, extension = os.path.splitext(doc.translated_path)
    marque = "_d" + re.sub(r"[^0-9A-Za-z]", "", str(doc.id))[:12]
    return doc.translated_path if base.endswith(marque) else base + marque + extension


_verrous_copie: dict[str, threading.Lock] = {}
_verrous_copie_garde = threading.Lock()


def verrou_copie(copie: str) -> threading.Lock:
    with _verrous_copie_garde:
        return _verrous_copie.setdefault(os.path.abspath(copie), threading.Lock())
