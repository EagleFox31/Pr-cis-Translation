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
import threading
import time

import fitz
import numpy as np
from PIL import Image

from .ocr_v2.detect import LectureEchouee, Recognizer, Tesseract, completer, lignes_fiables
from .ocr_v2.erase import effacer
from .ocr_v2 import render

OCR_VERSION = "ocrv2"
logger = logging.getLogger(__name__)
_slot = threading.BoundedSemaphore(1)


class OCRError(ValueError):
    status_code = 422


class OCRUnavailable(OCRError):
    status_code = 503


def _recognize(page, directory, deadline, apres, lecteur: Recognizer):
    debut = time.monotonic()
    dpi = min(220, int(72 * (12_000_000 / max(1, page.rect.width * page.rect.height)) ** 0.5))
    if dpi < 72:
        raise OCRError("La page est trop grande pour la reconnaissance automatique.")
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
        raise OCRError("Ce scan demande trop de temps. Traduisez moins de pages a la fois.")
    try:
        words = lecteur.lire(image_path, min(30, remaining))
    except LectureEchouee as exc:
        raise OCRError("La reconnaissance du scan a echoue. Essayez un scan plus net.") from exc
    if not words or statistics.mean(w.conf for w in words) < 65:
        raise OCRError("Le texte du scan n'est pas assez lisible pour etre traduit. Aucune page n'a ete decomptee.")
    # Ne pas livrer une phrase dont une grande partie des mots a ete ignoree.
    good = [w for w in words if w.conf >= 40]
    if len(good) < 0.9 * len(words):
        raise OCRError("La reconnaissance du scan est trop incertaine. Utilisez un scan plus net.")
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
    words, ecartees = lignes_fiables(words)
    if ecartees:
        logger.info("OCR : %d ligne(s) incertaine(s) laissee(s) telles quelles", ecartees)
    if not words:
        raise OCRError("Le texte du scan n'est pas assez lisible pour etre traduit. Aucune page n'a ete decomptee.")
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


def prepare_scanned_pdf(data: bytes, pages: set[int]) -> tuple[bytes, int]:
    """Prepare uniquement les pages demandees, sans appel IA ni debit."""
    if len(pages) > 10:
        raise OCRError("Reconnaissance limitee a 10 pages scannees par envoi. Selectionnez une plage plus courte.")
    lecteur = Tesseract()
    manque = lecteur.manquant()
    if manque == "langues":
        raise OCRUnavailable("Les langues de reconnaissance des scans sont indisponibles.")
    if manque:
        raise OCRUnavailable("La reconnaissance des scans est temporairement indisponible.")
    if not _slot.acquire(blocking=False):
        raise OCRUnavailable("Une reconnaissance de scan est deja en cours. Reessayez dans un instant.")
    try:
        with (fitz.open(stream=data, filetype="pdf") as source,
              fitz.open() as output,
              tempfile.TemporaryDirectory(prefix="precis-ocr-") as directory):
            deadline = time.monotonic() + 90
            scans = [i for i, page in enumerate(source)
                     if i + 1 in pages and not page.get_text().strip()]
            count = 0
            for index, page in enumerate(source):
                if index not in scans:
                    output.insert_pdf(source, from_page=index, to_page=index)
                    continue
                apres = len(scans) - count - 1
                with _recognize(page, directory, deadline, apres, lecteur) as recognized:
                    if not recognized[0].get_text().strip():
                        raise OCRError("Aucun texte lisible reconnu dans le scan.")
                    output.insert_pdf(recognized)
                count += 1
            return output.tobytes(garbage=3, deflate=True), count
    finally:
        _slot.release()
