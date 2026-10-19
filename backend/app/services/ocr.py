"""OCR local borne pour les pages PDF sans texte (imprime francais/anglais).

L'original reste intact. La copie de travail conserve le fond du scan, masque
les mots reconnus et ajoute du texte visible que le moteur PDF peut traduire.
Les polices sont approximatives ; les manuscrits ne sont pas pris en charge.
"""
from __future__ import annotations

import csv
import io
import os
import re
import shutil
import statistics
import subprocess
import tempfile
import threading
import time

import fitz
from PIL import Image, ImageDraw

OCR_VERSION = "ocrv1"
_slot = threading.BoundedSemaphore(1)


class OCRError(ValueError):
    status_code = 422


class OCRUnavailable(OCRError):
    status_code = 503


def _run(args, timeout):
    try:
        return subprocess.run(args, capture_output=True, text=True,
                              timeout=timeout, check=True,
                              env={**os.environ, "OMP_THREAD_LIMIT": "1"})
    except (subprocess.SubprocessError, OSError) as exc:
        raise OCRError("La reconnaissance du scan a echoue. Essayez un scan plus net.") from exc


def _recognize(page, directory, deadline):
    dpi = min(220, int(72 * (12_000_000 / max(1, page.rect.width * page.rect.height)) ** 0.5))
    if dpi < 72:
        raise OCRError("La page est trop grande pour la reconnaissance automatique.")
    pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)
    image = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    image_path = os.path.join(directory, "page.png")
    image.save(image_path, dpi=(dpi, dpi))
    # OSD detecte notamment les scans poses sur le cote. Un echec OSD sur
    # une page courte n'empeche pas la reconnaissance du texte horizontal.
    try:
        osd = _run(["tesseract", image_path, "stdout", "--psm", "0"], 10)
        rotation = re.search(r"Rotate:\s*(90|180|270)\b", osd.stdout)
        if rotation:
            image = image.rotate(-int(rotation[1]), expand=True)
            image.save(image_path, dpi=(dpi, dpi))
    except OCRError:
        pass
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise OCRError("Ce scan demande trop de temps. Traduisez moins de pages a la fois.")
    result = _run(["tesseract", image_path, "stdout", "-l", "fra+eng",
                   "--psm", "3", "tsv"], min(30, remaining))
    words = [row for row in csv.DictReader(io.StringIO(result.stdout), delimiter="\t")
             if row.get("level") == "5" and (row.get("text") or "").strip()]
    if not words or statistics.mean(float(w["conf"]) for w in words) < 65:
        raise OCRError("Le texte du scan n'est pas assez lisible pour etre traduit. Aucune page n'a ete decomptee.")
    # Ne pas livrer une phrase dont une grande partie des mots a ete ignoree.
    good = [w for w in words if float(w["conf"]) >= 40]
    if len(good) < 0.9 * len(words):
        raise OCRError("La reconnaissance du scan est trop incertaine. Utilisez un scan plus net.")
    lines = {}
    draw = ImageDraw.Draw(image)
    for word in words:
        x, y, w, h = [int(word[k]) for k in ("left", "top", "width", "height")]
        # Couleur dominante autour du mot : conserve les fonds colores des
        # attestations. Le reste de l'image (logos, tampons, signatures hors
        # zones de texte) n'est pas reconstruit et reste intact.
        ring = []
        for xx in range(max(0, x - 2), min(image.width, x + w + 2), max(1, w // 12)):
            for yy in (max(0, y - 2), min(image.height - 1, y + h + 2)):
                ring.append(image.getpixel((xx, yy)))
        background = tuple(int(statistics.median(p[c] for p in ring)) for c in range(3))
        draw.rectangle((max(0, x - 1), max(0, y - 1),
                        min(image.width - 1, x + w), min(image.height - 1, y + h)),
                       fill=background)
        key = tuple(word[k] for k in ("block_num", "par_num", "line_num"))
        lines.setdefault(key, []).append(word)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    scale = 72 / dpi
    work = fitz.open()
    target = work.new_page(width=image.width * scale, height=image.height * scale)
    target.insert_image(target.rect, stream=buffer.getvalue())
    for line in lines.values():
        text = " ".join(w["text"].strip() for w in line)
        x0 = min(int(w["left"]) for w in line) * scale
        y0 = min(int(w["top"]) for w in line) * scale
        x1 = max(int(w["left"]) + int(w["width"]) for w in line) * scale
        y1 = max(int(w["top"]) + int(w["height"]) for w in line) * scale
        size = min((y1 - y0) / 0.8,
                   (x1 - x0) / max(0.1, fitz.get_text_length(text, fontsize=1)))
        target.insert_text((x0, y1 - 0.1 * (y1 - y0)), text,
                           fontname="helv", fontsize=size)
    return work


def prepare_scanned_pdf(data: bytes, pages: set[int]) -> tuple[bytes, int]:
    """Prepare uniquement les pages demandees, sans appel IA ni debit."""
    if len(pages) > 10:
        raise OCRError("Reconnaissance limitee a 10 pages scannees par envoi. Selectionnez une plage plus courte.")
    if not shutil.which("tesseract"):
        raise OCRUnavailable("La reconnaissance des scans est temporairement indisponible.")
    try:
        languages = _run(["tesseract", "--list-langs"], 5).stdout.splitlines()
    except OCRError as exc:
        raise OCRUnavailable("La reconnaissance des scans est temporairement indisponible.") from exc
    if not {"fra", "eng", "osd"}.issubset(set(languages)):
        raise OCRUnavailable("Les langues de reconnaissance des scans sont indisponibles.")
    if not _slot.acquire(blocking=False):
        raise OCRUnavailable("Une reconnaissance de scan est deja en cours. Reessayez dans un instant.")
    try:
        with (fitz.open(stream=data, filetype="pdf") as source,
              fitz.open() as output,
              tempfile.TemporaryDirectory(prefix="precis-ocr-") as directory):
            deadline = time.monotonic() + 90
            count = 0
            for index, page in enumerate(source):
                if index + 1 not in pages or page.get_text().strip():
                    output.insert_pdf(source, from_page=index, to_page=index)
                    continue
                with _recognize(page, directory, deadline) as recognized:
                    if not recognized[0].get_text().strip():
                        raise OCRError("Aucun texte lisible reconnu dans le scan.")
                    output.insert_pdf(recognized)
                count += 1
            return output.tobytes(garbage=3, deflate=True), count
    finally:
        _slot.release()
