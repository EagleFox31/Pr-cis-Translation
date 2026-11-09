"""OCR local borne pour les pages PDF sans texte (imprime francais/anglais).

L'original reste intact. La copie de travail conserve le fond du scan, efface
les lettres reconnues (voir `ocr_v2`) et ajoute du texte visible que le moteur PDF peut traduire.
Les polices sont approximatives ; les manuscrits ne sont pas pris en charge.
"""
from __future__ import annotations

import io
import logging
import os
import statistics
import tempfile
import time
from dataclasses import dataclass

import fitz
import numpy as np
from PIL import Image

from .ocr_v2.detect import LectureEchouee, Recognizer, Tesseract, completer, lignes_fiables
from .ocr_v2.erase import effacer
from .ocr_v2 import render
from app.config import OCR_DELAI_PAGE_S

# ocrv3 : lecture page par page (statuts ok / blanche / illisible). Un document
# traduit en ocrv2 (scan entier préparé à l'envoi) se rouvre toujours par sa
# copie `.source.pdf`.
OCR_VERSION = "ocrv3"
logger = logging.getLogger(__name__)

# Écart-type des niveaux de gris sous lequel une image est « presque unie » :
# un scan blanc bruité reste très en dessous, une photo ou un dessin très au
# dessus. Sans mot lu, seule une image presque unie est une page blanche.
SEUIL_IMAGE_UNIE = 12.0


class OCRError(ValueError):
    status_code = 422

    def __init__(self, message: str = "", motif: str = "lecture",
                 image_unie: bool = False) -> None:
        super().__init__(message)
        self.motif = motif
        self.image_unie = image_unie


class OCRUnavailable(OCRError):
    status_code = 503


def _ecart_type_gris(image) -> float:
    return float(np.asarray(image.convert("L"), dtype=np.float32).std())


def _recognize(page, directory, deadline, apres, lecteur: Recognizer,
               forcee: bool = False):
    """Rend un document d'une page (fond du scan + texte reconnu).

    `forcee` : lecture demandée par l'utilisateur sur une page déjà jugée
    illisible. Aucun seuil de confiance, et les lignes douteuses sont gardées."""
    debut = time.monotonic()
    dpi = min(220, int(72 * (12_000_000 / max(1, page.rect.width * page.rect.height)) ** 0.5))
    if dpi < 72:
        raise OCRError("La page est trop grande pour la reconnaissance automatique.",
                       "trop_grande")
    pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)
    image = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    image_path = os.path.join(directory, "page.png")
    image.save(image_path, dpi=(dpi, dpi))
    rotation = lecteur.rotation(image_path)
    if rotation:
        image = image.rotate(-rotation, expand=True)
        image.save(image_path, dpi=(dpi, dpi))
    # Lignes horizontales avant lecture : boites justes et style mesurable.
    droit, angle = render.redresser(np.ascontiguousarray(np.asarray(image)[:, :, ::-1]))
    if angle:
        image = Image.fromarray(np.ascontiguousarray(droit[:, :, ::-1]))
        image.save(image_path, dpi=(dpi, dpi))
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise OCRError("Ce scan demande trop de temps. Traduisez moins de pages a la fois.",
                       "temps")
    try:
        words = lecteur.lire(image_path, min(30, remaining))
    except LectureEchouee as exc:
        raise OCRError("La reconnaissance du scan a echoue. Essayez un scan plus net.",
                       "lecture") from exc
    if not words:
        raise OCRError("Aucun mot reconnu dans la page.", "aucun_mot",
                       image_unie=_ecart_type_gris(image) < SEUIL_IMAGE_UNIE)
    if not forcee:
        if statistics.mean(w.conf for w in words) < 65:
            raise OCRError("Le texte du scan n'est pas assez lisible pour etre traduit. Aucune page n'a ete decomptee.",
                           "peu_sur")
        # Ne pas livrer une phrase dont une grande partie des mots a ete ignoree.
        good = [w for w in words if w.conf >= 40]
        if len(good) < 0.9 * len(words):
            raise OCRError("La reconnaissance du scan est trop incertaine. Utilisez un scan plus net.",
                           "peu_sur")
    # Titres jaunes ou orange sur blanc : trop clairs pour la premiere lecture,
    # ils deviennent de l'encre sur le canal le plus sombre. Seconde lecture en
    # complement seulement (sur un aplat vif, ce canal noircit le fond).
    sombre = os.path.join(directory, "sombre.png")
    Image.fromarray(np.ascontiguousarray(np.asarray(image).min(axis=2))).save(sombre, dpi=(dpi, dpi))
    remaining = deadline - time.monotonic()
    if remaining > 10:
        try:
            words = completer(words, lecteur.lire(sombre, min(30, remaining - 5)))
        except LectureEchouee:
            logger.warning("OCR : seconde lecture (couleurs) impossible")
    # Une ligne douteuse n'est ni effacee ni reecrite : elle reste en image.
    if not forcee:
        words, ecartees = lignes_fiables(words)
        if ecartees:
            logger.info("OCR : %d ligne(s) incertaine(s) laissee(s) telles quelles", ecartees)
        if not words:
            raise OCRError("Le texte du scan n'est pas assez lisible pour etre traduit. Aucune page n'a ete decomptee.",
                           "peu_sur")
    lines = {}
    for word in words:
        lines.setdefault(word.ligne, []).append(word)
    # Seuls les pixels des lettres sont remplis, par la methode la plus sure
    # zone par zone (fonds degrades, textures, traits traversants). Le reste de
    # l'image (logos, tampons, signatures hors zones de texte) reste intact.
    # Le temps restant, moins la lecture des `apres` pages suivantes (estimee
    # sur celle-ci), le cout fixe de chaque page (effacement ~1 s, ecriture du
    # texte et choix de la police ~2 s) et
    # l'enregistrement final du PDF, se partage entre l'effacement de cette page
    # et des suivantes. Passe sa part, les zones restantes sont remplies sans
    # analyse.
    now = time.monotonic()
    libre = deadline - now - apres * (1.2 * (now - debut) + 3) - 3 - 6
    limite = max(0.0, libre / (apres + 1))
    bgr = np.ascontiguousarray(np.asarray(image)[:, :, ::-1])
    efface, _ = effacer(bgr, [w.boite for w in words],
                        budget_s=limite, limite_s=limite)
    image = Image.fromarray(np.ascontiguousarray(efface[:, :, ::-1]))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    scale = 72 / dpi
    work = fitz.open()
    target = work.new_page(width=image.width * scale, height=image.height * scale)
    target.insert_image(target.rect, stream=buffer.getvalue())
    # Texte dans le style mesure sur le scan ; ecriture v1 (Helvetica) en repli,
    # aussi quand il ne reste plus le temps de choisir la police (~2 s).
    try:
        render.ecrire(target, bgr, words, dpi,
                      None if deadline - time.monotonic() > 6 + 3 * apres else [])
    except Exception:
        logger.exception("OCR : ecriture stylee impossible, repli Helvetica")
        work.close()
        work = fitz.open()
        target = work.new_page(width=image.width * scale, height=image.height * scale)
        target.insert_image(target.rect, stream=buffer.getvalue())
        for line in lines.values():
            render.ligne_simple(target, line, scale)
    return work


@dataclass
class LecturePage:
    """Résultat de la lecture d'une page : `ok` (avec `pdf`, une page lisible),
    `blanche` ou `illisible` (avec `motif`). Aucun débit n'est lié à ce résultat."""
    statut: str
    motif: str | None = None
    pdf: bytes | None = None


def _lecteur_secours():
    from .ocr_v2.ppocr import PPOCR
    lecteur = PPOCR()
    return None if lecteur.manquant() else lecteur


def _lire_avec(page, lecteur, deadline: float, forcee: bool,
               repertoire: str | None) -> bytes:
    with tempfile.TemporaryDirectory(prefix="precis-ocr-", dir=repertoire) as directory:
        with _recognize(page, directory, deadline, 0, lecteur, forcee) as lue:
            if not lue[0].get_text().strip():
                raise OCRError("Aucun texte lisible reconnu dans la page.", "aucun_mot")
            return lue.tobytes(garbage=3, deflate=True)


def lire_page(doc, numero: int, repertoire: str | None = None, *, forcee: bool = False,
              delai_s: float = OCR_DELAI_PAGE_S, lecteur: Recognizer | None = None,
              lecteur_secours=None) -> LecturePage:
    """Lit la page `numero` (à partir de 1) de `doc` ; ne débite rien.

    L'appelant tient déjà son tour au guichet (`ocr_file`) : le délai court
    donc à partir de maintenant, pas depuis l'attente. Aucune `OCRError` ne
    sort : une page qui ne se lit pas est `illisible` avec son motif. Seule
    `OCRUnavailable` (Tesseract absent) remonte, c'est une panne du service.
    `forcee` : sans seuil de confiance, lignes douteuses gardées ; sans aucun
    mot, une seconde lecture par PP-OCR est tentée.
    `repertoire` : dossier où créer le répertoire de travail (défaut : temporaire système).
    """
    lecteur = lecteur or Tesseract()
    manque = lecteur.manquant()
    if manque == "langues":
        raise OCRUnavailable("Les langues de reconnaissance des scans sont indisponibles.")
    if manque:
        raise OCRUnavailable("La reconnaissance des scans est temporairement indisponible.")
    deadline = time.monotonic() + delai_s
    try:
        page = doc[numero - 1]
        try:
            pdf = _lire_avec(page, lecteur, deadline, forcee, repertoire)
        except OCRError as e:
            if not (forcee and e.motif == "aucun_mot"):
                raise
            secours = lecteur_secours if lecteur_secours is not None else _lecteur_secours()
            if secours is None:
                raise
            pdf = _lire_avec(page, secours, deadline, True, repertoire)
        return LecturePage("ok", None, pdf)
    except OCRUnavailable:
        raise
    except OCRError as e:
        if e.motif == "aucun_mot" and e.image_unie and not forcee:
            return LecturePage("blanche")
        motif = e.motif
        if motif == "lecture" and time.monotonic() >= deadline:
            motif = "temps"
        return LecturePage("illisible", motif)
    except Exception:
        logger.exception("OCR : page %s non lue", numero)
        motif = "temps" if time.monotonic() >= deadline else "lecture"
        return LecturePage("illisible", motif)
