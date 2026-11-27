"""Images d'un document qui contiennent du texte (étude images-documents §5).

Avant le lancement d'une traduction, liste les images DISTINCTES d'un PDF,
d'un DOCX, d'un PPTX ou d'un XLSX, écarte celles qu'il est inutile de lire
(scan de page, vectorielle, minuscule, refusée), puis repère par la seule
détection PP-OCR (sans lecture) celles qui portent du texte. Aucune
traduction ni aucun débit ici.

- PDF : une entrée par `xref`, avec toutes ses pages ; les octets sont ceux du
  rendu (`_image_bytes`), pour que l'étape suivante substitue la même image.
- Office : une entrée par partie `media/`, pages de diapositive lues dans les
  relations du PPTX.
- Une page de PDF sans texte presque couverte par une image est un scan : elle
  passe déjà par l'OCR de page, l'image est exclue (`scan`).

La pose (fin du module) traduit ces images dans le travail de fond, garde la
table des images traduites à côté de la traduction du document et la réinjecte
dans le PDF (par `xref`) ou le paquet Office (par partie). Le débit se fait
dans l'appelant, jamais ici.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import io
import json
import logging
import os
import posixpath
import re
import threading
import time
import zipfile
import zlib
from dataclasses import dataclass, field
from pathlib import PurePosixPath

import numpy as np
from PIL import Image

from app.services import ocr_file
from app.services.ocr_v2 import image as ocr_image
from app.services.ocr_v2 import ppocr
from app.services.ocr_v2.image import ImageRefusee
from engines import incorpores

logger = logging.getLogger(__name__)

COTE_MIN = 16               # px : en dessous, rien de lisible
PIXELS_MIN = 10_000
COUVERTURE_SCAN = 0.8       # part de la page couverte par une image de scan
ENTREES_MAX = 10_000
OCTETS_ZIP_MAX = 128 * 1024 * 1024
VECTORIELLES = (".emf", ".wmf", ".svg", ".emz", ".wmz")
# Une image n'est pas lue plus finement que sa taille affichée dans le document
# à POINTS_PAR_POUCE (comme « Compresser les images » de PowerPoint) : un texte
# de 8 pt y fait encore 17 px, assez pour la détection. Jamais sous COTE_LECTURE_MIN.
POINTS_PAR_POUCE, COTE_LECTURE_MIN, EMU_PAR_POUCE = 150, 960, 914400
_MEDIA = {"docx": "word", "pptx": "ppt", "xlsx": "xl"}
# Formats dont les images à texte sont traduites avec leur page : ceux dont
# le rendu à la demande pose la table d'images (pas le xlsx).
IMAGES_PROPOSABLES = ("pdf", "docx", "pptx")
_RELS_DIAPO = re.compile(r"^ppt/slides/_rels/slide(\d+)\.xml\.rels$")
CACHE_MAX = 32


@dataclass
class ImageDoc:
    cle: str                    # PDF : "xref:<n>" ; Office : nom de la partie
    pages: list[int] = field(default_factory=list)
    largeur: int = 0
    hauteur: int = 0
    exclusion: str | None = None
    octets: bytes | None = None
    cote_max: int | None = None     # px utiles pour la lecture (taille affichée)


@dataclass
class Analyse:
    images: list[ImageDoc] = field(default_factory=list)    # toutes
    a_texte: list[ImageDoc] = field(default_factory=list)
    analysees: int = 0
    incomplet: bool = False
    indisponible: bool = False


# ── Liste des images ─────────────────────────────────────────────────────────

def _controler(img: ImageDoc) -> None:
    """Contrôles d'entrée de l'image (type, poids, pixels) puis taille minimale."""
    if img.octets is None:
        img.exclusion = "type"
        return
    try:
        im = ocr_image.verifier(img.octets)
    except ImageRefusee as e:
        img.exclusion = e.code
        return
    img.largeur, img.hauteur = im.width, im.height
    if min(im.width, im.height) < COTE_MIN or im.width * im.height < PIXELS_MIN:
        img.exclusion = "petite"


def _lister_pdf(data: bytes) -> list[ImageDoc]:
    import fitz
    from engines.pdf.engine import _image_bytes

    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:
        raise ValueError("Le fichier PDF n'est pas valide.") from e
    with doc:
        par_xref: dict[int, ImageDoc] = {}
        scans: set[int] = set()
        for numero, page in enumerate(doc, 1):
            images = page.get_images(full=True)
            if not images:
                continue
            vide = page.get_text().strip() == ""
            aire = abs(page.rect.width * page.rect.height) or 1.0
            for info in images:
                xref = info[0]
                img = par_xref.get(xref)
                if img is None:
                    img = par_xref[xref] = ImageDoc(f"xref:{xref}")
                if numero not in img.pages:
                    img.pages.append(numero)
                if vide and xref not in scans:
                    try:
                        rects = page.get_image_rects(xref)
                    except Exception:
                        rects = []
                    if any(abs((r & page.rect).get_area()) / aire >= COUVERTURE_SCAN for r in rects):
                        scans.add(xref)
        for xref, img in par_xref.items():
            if xref in scans:
                img.exclusion = "scan"
                continue
            try:
                img.octets, _ = _image_bytes(doc, xref)
            except Exception:
                img.octets = None
            _controler(img)
        return list(par_xref.values())


def _ouvrir_zip(data: bytes) -> zipfile.ZipFile:
    """Archive Office avec les garde-fous de `office_cost` (beta_meter)."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise ValueError("Le fichier Office n'est pas valide.") from e
    entrees = archive.infolist()
    if len(entrees) > ENTREES_MAX or sum(e.file_size for e in entrees) > OCTETS_ZIP_MAX:
        archive.close()
        raise ValueError("Le document décompressé est trop volumineux pour être traité.")
    for e in entrees:
        chemin = PurePosixPath(e.filename.replace("\\", "/"))
        if chemin.is_absolute() or ".." in chemin.parts or e.flag_bits & 1:
            archive.close()
            raise ValueError("Le conteneur Office n'est pas valide.")
    return archive


def _pages_diapos(archive: zipfile.ZipFile) -> dict[str, list[int]]:
    """Partie média -> numéros des diapositives qui la référencent."""
    pages: dict[str, list[int]] = {}
    for e in archive.infolist():
        m = _RELS_DIAPO.match(e.filename)
        if not m or e.file_size > 1024 * 1024:
            continue
        numero = int(m.group(1))
        xml = archive.read(e).decode("utf-8", errors="replace")
        for balise in re.findall(r"<Relationship\b[^>]*>", xml):
            cible = re.search(r'\bTarget\s*=\s*"([^"]*)"', balise)
            if not cible or re.search(r'TargetMode\s*=\s*"External"', balise):
                continue
            c = cible.group(1)
            partie = c.lstrip("/") if c.startswith("/") else posixpath.normpath(posixpath.join("ppt/slides", c))
            if numero not in pages.setdefault(partie, []):
                pages[partie].append(numero)
    return pages


def _cotes_affichees(archive: zipfile.ZipFile, ext: str) -> dict[str, int | None]:
    """Partie média -> côté utile en px (plus grande taille affichée, à
    POINTS_PAR_POUCE). None si une de ses utilisations n'a pas de taille lisible
    (fond de diapositive…) : aucun plafond alors."""
    racine = _MEDIA[ext]
    pouces: dict[str, float | None] = {}
    for e in archive.infolist():
        if (not e.filename.startswith(racine + "/") or not e.filename.endswith(".xml")
                or e.file_size > 8 * 1024 * 1024):
            continue
        dossier, nom = posixpath.split(e.filename)
        try:
            rels = archive.read(f"{dossier}/_rels/{nom}.rels").decode("utf-8", errors="replace")
        except KeyError:
            continue
        cibles = {}
        for balise in re.findall(r"<Relationship\b[^>]*>", rels):
            rid = re.search(r'\bId\s*=\s*"([^"]*)"', balise)
            cible = re.search(r'\bTarget\s*=\s*"([^"]*)"', balise)
            if rid and cible:
                c = cible.group(1)
                c = (c.lstrip("/") if c.startswith("/")
                     else posixpath.normpath(posixpath.join(dossier, c)))
                if c.startswith(racine + "/media/"):
                    cibles[rid.group(1)] = c
        if not cibles:
            continue
        xml = archive.read(e).decode("utf-8", errors="replace")
        for m in re.finditer(r'r:(?:embed|link)\s*=\s*"([^"]*)"', xml):
            partie = cibles.get(m.group(1))
            if partie is None:
                continue
            if ext == "docx":   # <wp:extent> précède l'image dans son <w:drawing>
                debut = xml.rfind("<w:drawing", 0, m.start())
                tailles = re.findall(r'<wp:extent\s+cx="(\d+)"\s+cy="(\d+)"', xml[debut:m.start()]) if debut >= 0 else []
            else:               # <a:ext> suit l'image dans son <p:pic> / <xdr:pic>
                fin = re.search(r"</(?:p|xdr):pic>|<(?:p|xdr):pic[ >]", xml[m.end():])
                zone = xml[m.end():m.end() + fin.start()] if fin else ""
                tailles = re.findall(r'<a:ext\s+cx="(\d+)"\s+cy="(\d+)"', zone)
            if not tailles:
                pouces[partie] = None
            elif partie not in pouces or pouces[partie] is not None:
                cote = max(int(v) for v in tailles[-1 if ext == "docx" else 0]) / EMU_PAR_POUCE
                pouces[partie] = max(pouces.get(partie) or 0.0, cote)
    return {p: (None if v is None else max(COTE_LECTURE_MIN, round(v * POINTS_PAR_POUCE)))
            for p, v in pouces.items()}


def _lister_office(data: bytes, ext: str) -> list[ImageDoc]:
    motif = re.compile(rf"^{_MEDIA[ext]}/media/[^/]+$")
    # Aperçus d'objets incorporés : redessinés depuis l'objet traduit (ou
    # signalés s'il ne l'est pas), jamais lus par l'OCR ni facturés en image.
    with _ouvrir_zip(data) as archive:
        # Après les garde-fous du zip : `reperer` décompresse.
        apercus = {o.apercu.lower() for o in incorpores.reperer(data) if o.apercu}
        diapos = _pages_diapos(archive) if ext == "pptx" else {}
        try:
            cotes = _cotes_affichees(archive, ext)
        except Exception:
            cotes = {}
        out = []
        for e in sorted(archive.infolist(), key=lambda e: e.filename):
            if e.is_dir() or not motif.match(e.filename):
                continue
            img = ImageDoc(e.filename, sorted(diapos.get(e.filename, [])),
                           cote_max=cotes.get(e.filename))
            if e.filename.lower() in apercus:
                img.exclusion = "apercu_objet"
            elif e.filename.lower().endswith(VECTORIELLES):
                img.exclusion = "vectorielle"
            elif e.file_size > ocr_image.OCTETS_MAX:
                img.exclusion = "taille"
            else:
                try:
                    img.octets = archive.read(e)
                except Exception:
                    img.octets = None
                _controler(img)
            out.append(img)
        return out


def lister(data: bytes, ext: str) -> list[ImageDoc]:
    """Images distinctes du document (une image répétée = une entrée)."""
    if ext == "pdf":
        return _lister_pdf(data)
    if ext in _MEDIA:
        try:
            return _lister_office(data, ext)
        except (zlib.error, EOFError, zipfile.BadZipFile, RuntimeError) as e:
            # Octets compressés abîmés : même refus qu'un zip illisible.
            raise ValueError("Le fichier Office n'est pas valide.") from e
    return []


# ── Détection ────────────────────────────────────────────────────────────────

def _bgr(octets: bytes) -> np.ndarray:
    with Image.open(io.BytesIO(octets)) as im:
        rgb = im.convert("RGB")
    return np.ascontiguousarray(np.asarray(rgb)[:, :, ::-1])


def detecter(images: list[ImageDoc], lecteur=None, delai_s: float = 20.0) -> Analyse:
    """Repère les images à texte par la détection seule, dans un délai global."""
    res = Analyse(images=list(images))
    lecteur = lecteur or ocr_image._ppocr()
    if lecteur.manquant():
        res.indisponible = True
        return res
    fin = time.monotonic() + delai_s
    for img in images:
        if img.exclusion or img.octets is None:
            continue
        if time.monotonic() >= fin:
            res.incomplet = True
            break
        try:
            with ppocr.plafond(img.cote_max):
                trouvees = len(lecteur.detecter_image(_bgr(img.octets)))
            if trouvees:
                res.a_texte.append(img)
        except Exception:
            pass                # image illisible : traitée comme sans texte
        res.analysees += 1
    return res


_CACHE: dict[str, Analyse] = {}
_VERROU = threading.Lock()


def analyser(data: bytes, ext: str, lecteur=None, delai_s: float = 20.0) -> Analyse:
    """`detecter(lister(...))`, mémorisé par empreinte du fichier (32 au plus)."""
    cle = hashlib.sha256(data).hexdigest() + ext
    with _VERROU:
        if cle in _CACHE:
            return _CACHE[cle]
    res = detecter(lister(data, ext), lecteur, delai_s)
    gardees = {id(i) for i in res.a_texte}
    for img in res.images:      # seules les images à texte gardent leurs octets
        if id(img) not in gardees:
            img.octets = None
    if not (res.incomplet or res.indisponible):
        with _VERROU:
            _CACHE[cle] = res
            while len(_CACHE) > CACHE_MAX:
                del _CACHE[next(iter(_CACHE))]
    return res


def vignette(octets: bytes, cote: int = 160) -> str:
    """Data URL JPEG (qualité 70) de l'image, réduite à `cote` px au plus."""
    with Image.open(io.BytesIO(octets)) as im:
        im = im.convert("RGBA")
    fond = Image.new("RGB", im.size, (255, 255, 255))
    fond.paste(im, mask=im.getchannel("A"))
    fond.thumbnail((cote, cote))
    sortie = io.BytesIO()
    fond.save(sortie, "JPEG", quality=70)
    return "data:image/jpeg;base64," + base64.b64encode(sortie.getvalue()).decode("ascii")


# ── Pose des images traduites ────────────────────────────────────────────────

def poser_office(data: bytes, table: dict[str, bytes]) -> bytes:
    """Paquet Office réécrit, chaque partie nommée dans `table` remplacée.

    Même nom, même ordre d'entrées, même compression ; le reste est copié tel
    quel. Rien à remplacer : les octets d'origine.
    """
    if not table:
        return data
    with zipfile.ZipFile(io.BytesIO(data)) as source:
        entrees = source.infolist()
        if not any(e.filename in table for e in entrees):
            return data
        sortie = io.BytesIO()
        with zipfile.ZipFile(sortie, "w") as cible:
            for e in entrees:
                octets = table[e.filename] if e.filename in table else source.read(e)
                cible.writestr(copy.copy(e), octets)
    return sortie.getvalue()


def chemin_table(translation_path: str) -> str:
    """Table des images traduites, gardée à côté de la traduction du document."""
    return translation_path + ".images.json"


def _dossier_images(translation_path: str) -> str:
    return translation_path + ".images"


def _mime_de(octets: bytes) -> str:
    if octets[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if octets[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if octets[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if octets[:4] == b"RIFF" and octets[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


_EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg",
               "image/gif": ".gif", "image/webp": ".webp"}


def _ecrire_atomiquement(chemin: str, octets: bytes) -> None:
    tmp = chemin + ".tmp"
    with open(tmp, "wb") as f:
        f.write(octets)
    os.replace(tmp, chemin)


def charger_table(translation_path: str) -> dict[str, bytes]:
    """{clé d'image: octets traduits} d'un document ; `{}` si absente ou illisible.
    Les images remises à l'original (`retirees`) n'y figurent pas."""
    try:
        with open(chemin_table(translation_path), encoding="utf-8") as f:
            meta = json.load(f)
        images = meta["images"]
        retirees = set(meta.get("retirees") or ())
        dossier = _dossier_images(translation_path)
        table = {}
        for cle, info in images.items():
            if cle in retirees:
                continue
            try:
                with open(os.path.join(dossier, os.path.basename(info["fichier"])), "rb") as f:
                    table[cle] = f.read()
            except (OSError, KeyError, TypeError):
                continue                # image manquante : l'original reste
        return table
    except (OSError, ValueError, KeyError, AttributeError):
        return {}


def ecrire_table(translation_path: str, table: dict[str, bytes], rapport: dict,
                 mimes: dict[str, str] | None = None) -> None:
    """Écrit la table à côté de la traduction : le JSON `chemin_table` et, dans
    `<traduction>.images/`, un fichier par image (nom dérivé de la clé).
    Écriture atomique ; le JSON vient en dernier."""
    dossier = _dossier_images(translation_path)
    os.makedirs(dossier, exist_ok=True)
    images, gardes = {}, set()
    for cle, octets in table.items():
        mime = (mimes or {}).get(cle) or _mime_de(octets)
        nom = hashlib.sha1(cle.encode("utf-8")).hexdigest()[:20] + _EXTENSIONS.get(mime, ".bin")
        _ecrire_atomiquement(os.path.join(dossier, nom), octets)
        images[cle] = {"fichier": nom, "mime": mime}
        gardes.add(nom)
    for nom in os.listdir(dossier):     # restes d'un passage précédent
        if nom not in gardes:
            try:
                os.remove(os.path.join(dossier, nom))
            except OSError:
                pass
    _ecrire_atomiquement(chemin_table(translation_path), json.dumps(
        {"rapport": rapport, "images": images}, ensure_ascii=False).encode("utf-8"))


_VERROU_TABLE = threading.Lock()


def _lire_meta(translation_path: str) -> dict | None:
    try:
        with open(chemin_table(translation_path), encoding="utf-8") as f:
            meta = json.load(f)
        return meta if isinstance(meta.get("images"), dict) else None
    except (OSError, ValueError, AttributeError):
        return None


def etat_images(translation_path: str) -> list[tuple[str, bool, bytes | None]]:
    """[(clé, remise à l'original ?, octets traduits)] de la table du document."""
    meta = _lire_meta(translation_path)
    if meta is None:
        return []
    retirees = set(meta.get("retirees") or ())
    dossier = _dossier_images(translation_path)
    sortie = []
    for cle, info in meta["images"].items():
        try:
            with open(os.path.join(dossier, os.path.basename(info["fichier"])), "rb") as f:
                octets = f.read()
        except (OSError, KeyError, TypeError):
            octets = None
        sortie.append((cle, cle in retirees, octets))
    return sortie


def marquer_originale(translation_path: str, cle: str, originale: bool) -> bool:
    """Remet l'image `cle` à l'original (ou rétablit sa traduction) dans la
    table ; les octets traduits restent gardés. False si la clé est inconnue."""
    with _VERROU_TABLE:
        meta = _lire_meta(translation_path)
        if meta is None or cle not in meta["images"]:
            return False
        retirees = set(meta.get("retirees") or ())
        retirees.add(cle) if originale else retirees.discard(cle)
        meta["retirees"] = sorted(retirees)
        _ecrire_atomiquement(chemin_table(translation_path),
                             json.dumps(meta, ensure_ascii=False).encode("utf-8"))
        return True


def _lire_cache(dossier: str, sha: str):
    """(remplacée, mime, octets) d'une image déjà traduite, ou None."""
    try:
        with open(os.path.join(dossier, sha + ".json"), encoding="utf-8") as f:
            meta = json.load(f)
        with open(os.path.join(dossier, sha + ".bin"), "rb") as f:
            return bool(meta["remplacee"]), meta.get("mime", ""), f.read()
    except (OSError, ValueError, KeyError):
        return None


def _ecrire_cache(dossier: str, sha: str, remplacee: bool, mime: str, octets: bytes) -> None:
    try:
        os.makedirs(dossier, exist_ok=True)
        _ecrire_atomiquement(os.path.join(dossier, sha + ".bin"), octets if remplacee else b"")
        _ecrire_atomiquement(os.path.join(dossier, sha + ".json"),
                             json.dumps({"remplacee": remplacee, "mime": mime}).encode("utf-8"))
    except OSError as e:
        logger.warning("Cache d'image non écrit : %s", e)


def traduire_images(data: bytes, ext: str, traduire, dossier: str, budget: int | None,
                    analyse: Analyse | None = None,
                    arret=None, langue: str | None = None) -> tuple[dict[str, bytes], dict]:
    """Traduit les images à texte du document ; renvoie `(table, rapport)`.

    `table` : {clé d'image: octets traduits}, pour les seules images remplacées.
    `budget` : nombre d'images remplacées au plus (None : sans limite) ; les
    suivantes ne sont pas lues (`sans_credit`). Une image dont la lecture ou la
    traduction échoue reste en original (`echecs`) : jamais d'échec du document.
    Cache disque par empreinte des octets source, dans `dossier`.
    `arret` : rappel appelé pendant l'attente du guichet OCR (peut lever l'arrêt).
    `langue` : langue cible, pour les césures dans les images.
    """
    a_texte = (analyse or analyser(data, ext)).a_texte
    table: dict[str, bytes] = {}
    rapport = {"proposees": len(a_texte), "traduites": 0, "inchangees": 0,
               "sans_credit": 0, "echecs": 0}
    for img in a_texte:
        if budget is not None and rapport["traduites"] >= budget:
            rapport["sans_credit"] += 1
            continue
        try:
            if img.octets is None:
                raise ValueError("octets de l'image absents")
            sha = hashlib.sha256(img.octets).hexdigest()
            trouve = _lire_cache(dossier, sha)
            if trouve is None:
                rendu = ocr_image.traduire_image(
                    img.octets, traduire, tour=lambda: ocr_file.tour(arret=arret),
                    langue=langue)
                trouve = (rendu.remplacee, rendu.mime, rendu.data)
                _ecrire_cache(dossier, sha, *trouve)
        except Exception as e:
            logger.warning("Image %s non traduite : %s", img.cle, e)
            rapport["echecs"] += 1
            continue
        remplacee, _, octets = trouve
        if remplacee:
            table[img.cle] = octets
            rapport["traduites"] += 1
        else:
            rapport["inchangees"] += 1
    return table, rapport


# ── Images du travail : la page part avec ses images (étude 23/11) ─────────
# Une page n'est livrée qu'une fois ses images à texte traduites. Un fil lit
# les images des pages attendues, puis lit d'avance celles des pages permises
# suivantes. Rien n'est lu pour une page qui ne sera pas traduite (plafond,
# sélection, budget). Aucun débit : la page couvre ses images.

def ajouter_a_table(translation_path: str, cle: str, octets: bytes,
                    mime: str | None = None, rapport: dict | None = None) -> None:
    """Ajoute une image traduite à la table du document, en gardant les
    autres images et les choix « garder l'original »."""
    with _VERROU_TABLE:
        dossier = _dossier_images(translation_path)
        os.makedirs(dossier, exist_ok=True)
        meta = _lire_meta(translation_path) or {"rapport": {}, "images": {}}
        mime = mime or _mime_de(octets)
        nom = hashlib.sha1(cle.encode("utf-8")).hexdigest()[:20] + _EXTENSIONS.get(mime, ".bin")
        _ecrire_atomiquement(os.path.join(dossier, nom), octets)
        meta["images"][cle] = {"fichier": nom, "mime": mime}
        if rapport is not None:
            meta["rapport"] = rapport
        _ecrire_atomiquement(chemin_table(translation_path),
                             json.dumps(meta, ensure_ascii=False).encode("utf-8"))


def _retirees(translation_path: str) -> set[str]:
    meta = _lire_meta(translation_path)
    return set(meta.get("retirees") or ()) if meta else set()


class ImagesDuTravail:
    """Images à texte d'un travail, traduites page par page.

    `pages` : pages permises (None : toutes). `avance` : pages permises lues
    d'avance après la plus haute page attendue. `reste()` : nombre de pages
    encore permises au-delà (budget), ou None. `arret()` : lève l'arrêt du
    travail (pause, annulation) ; il interrompt la lecture comme l'attente.
    Une image illisible ou en échec reste d'origine, la page part quand même.
    """

    PAS_S = 0.3

    def __init__(self, data: bytes, ext: str, traduire, dossier: str,
                 translation_path: str, langue: str | None = None,
                 pages=None, avance: int = 3, reste=None, arret=None, lecteur=None,
                 persister: bool = True):
        self._data, self._ext, self._traduire = data, ext, traduire
        self._dossier, self._chemin, self._langue = dossier, translation_path, langue
        self._permises = sorted(set(pages)) if pages is not None else None
        self._avance, self._reste, self._arret = avance, reste, arret
        self._lecteur = lecteur
        # persister False : rien n'est écrit dans la table du document avant
        # `reporter()` (page incluse après coup : seulement si elle est payée).
        self._persister = persister
        self._a_reporter: dict[str, tuple[bytes, str | None]] = {}
        self._cond = threading.Condition()
        self._index: dict[int, list[ImageDoc]] | None = None
        self._traitees: set[str] = set()
        self._attendues: set[int] = set()
        self._fini = False          # fil terminé : fermé, arrêté ou en panne
        self._ferme = False
        self._fil: threading.Thread | None = None
        self.rapport = {"traduites": 0, "inchangees": 0, "echecs": 0}
        self._table = {cle: o for cle, _, o in etat_images(translation_path) if o}
        # Images déjà traduites (reprise) : rien à relire pour elles.
        self._traitees.update(self._table)

    # ── Côté travail ──────────────────────────────────────────────────────
    def demander(self, pages) -> None:
        """Annonce des pages attendues, sans attendre ; lance le fil."""
        with self._cond:
            self._attendues.update(p for p in pages if self._permise(p))
            if self._fil is None:
                self._fil = threading.Thread(target=self._boucle, name="images-travail",
                                             daemon=True)
                self._fil.start()
            self._cond.notify_all()

    def attendre(self, page: int) -> dict[str, bytes]:
        """Table des images traduites, une fois celles de `page` traitées.
        Sans limite de temps ; `arret()` interrompt l'attente."""
        if not self._permise(page):
            return self.table()
        self.demander([page])
        while True:
            with self._cond:
                if self._fini or self._page_faite(page):
                    break
                self._cond.wait(self.PAS_S)
            if self._arret is not None:
                self._arret()
        self._verifier_fin()
        return self.table()

    def attendre_tout(self) -> dict[str, bytes]:
        """Toutes les pages permises : document livré d'un bloc (Word)."""
        self.demander([])
        while True:
            with self._cond:
                if self._fini or self._index is not None:
                    pages = [p for p in (self._index or {}) if self._permise(p)]
                    break
                self._cond.wait(self.PAS_S)
            if self._arret is not None:
                self._arret()
        self.demander(pages)
        for page in sorted(pages):
            self.attendre(page)
        self._verifier_fin()
        return self.table()

    def _verifier_fin(self) -> None:
        """Fil terminé (arrêt avalé, panne) : l'arrêt du travail est relu,
        pour qu'une pause ou une annulation ne livre pas la page sans ses
        images."""
        if self._fini and self._arret is not None:
            self._arret()

    def reporter(self) -> None:
        """Écrit dans la table du document les images gardées en attente."""
        with self._cond:
            a_ecrire, self._a_reporter = self._a_reporter, {}
        for cle, (octets, mime) in a_ecrire.items():
            ajouter_a_table(self._chemin, cle, octets, mime, dict(self.rapport))

    @property
    def traduites(self) -> int:
        return self.rapport["traduites"]

    def table(self) -> dict[str, bytes]:
        """Images traduites, sans celles remises à l'original."""
        retirees = _retirees(self._chemin)
        with self._cond:
            return {c: o for c, o in self._table.items() if c not in retirees}

    def fermer(self) -> None:
        with self._cond:
            self._ferme = True
            self._cond.notify_all()

    # ── Fil de lecture ────────────────────────────────────────────────────
    def _permise(self, page: int) -> bool:
        return self._permises is None or page in self._permises

    def _page_faite(self, page: int) -> bool:
        if self._index is None:
            return False
        return all(i.cle in self._traitees for i in self._index.get(page, ()))

    def _indexer(self) -> dict[int, list[ImageDoc]]:
        try:
            images = lister(self._data, self._ext)
        except Exception as e:
            logger.warning("Images du travail non listées : %s", e)
            return {}
        premiere = self._permises[0] if self._permises else 1
        index: dict[int, list[ImageDoc]] = {}
        for img in images:
            if img.exclusion or img.octets is None:
                continue
            # Word : pas de pages (rattachées à la première) ; PowerPoint :
            # images des masques, attendues par chaque diapositive permise
            # (une diapositive reprise ne les lit donc pas seule).
            sans_page = (self._permises or [premiere]) if self._ext == "pptx" else [premiere]
            for page in img.pages or sans_page:
                if self._permise(page):
                    index.setdefault(page, []).append(img)
        return index

    def _prochaine(self) -> int | None:
        """Plus petite page attendue non faite, sinon page à lire d'avance."""
        en_attente = sorted(p for p in self._attendues if not self._page_faite(p))
        if en_attente:
            return en_attente[0]
        if not self._attendues or not self._avance:
            return None
        haute = max(self._attendues)
        suivantes = [p for p in (self._permises or sorted(self._index or ())) if p > haute]
        n = self._avance
        if self._reste is not None:
            try:
                reste = self._reste()
            except Exception:
                reste = 0
            if reste is not None:
                n = min(n, max(reste, 0))
        for p in suivantes[:n]:
            if not self._page_faite(p):
                return p
        return None

    def _boucle(self) -> None:
        try:
            index = self._indexer()
            lecteur = self._lecteur
            if index:
                lecteur = lecteur or ocr_image._ppocr()
                if lecteur.manquant():
                    logger.warning("Images du travail : lecteur OCR indisponible")
                    index = {}
            with self._cond:
                self._index = index
                self._cond.notify_all()
            while True:
                with self._cond:
                    page = self._prochaine()
                    while page is None and not self._ferme:
                        self._cond.wait(self.PAS_S)
                        page = self._prochaine()
                    if self._ferme:
                        return
                    a_lire = [i for i in self._index.get(page, ()) if i.cle not in self._traitees]
                for img in a_lire:
                    with self._cond:
                        if self._ferme:
                            return
                    self._traiter(img, lecteur)
                    with self._cond:
                        self._traitees.add(img.cle)
                        img.octets = None
                        self._cond.notify_all()
        except BaseException as e:
            # Arrêt du travail (pause, annulation) ou panne : les pages partent
            # avec leurs images d'origine.
            logger.info("Images du travail interrompues : %s", e)
        finally:
            with self._cond:
                self._fini = True
                self._cond.notify_all()

    def _traiter(self, img: ImageDoc, lecteur) -> None:
        """Détecte, traduit (cache) et ajoute l'image à la table. L'arrêt du
        travail remonte ; toute autre erreur laisse l'image d'origine."""
        if img.octets is None:          # déjà lue pour une autre page
            return
        try:
            with ppocr.arret(self._arret), ppocr.plafond(img.cote_max):
                if not len(lecteur.detecter_image(_bgr(img.octets))):
                    return
            sha = hashlib.sha256(img.octets).hexdigest()
            trouve = _lire_cache(self._dossier, sha)
            if trouve is None:
                with ppocr.arret(self._arret), ppocr.plafond(img.cote_max):
                    rendu = ocr_image.traduire_image(
                        img.octets, self._traduire,
                        tour=lambda: ocr_file.tour(arret=self._arret), langue=self._langue)
                trouve = (rendu.remplacee, rendu.mime, rendu.data)
                _ecrire_cache(self._dossier, sha, *trouve)
            remplacee, mime, octets = trouve
            if not remplacee:
                self.rapport["inchangees"] += 1
                return
            self.rapport["traduites"] += 1
            if self._persister:
                ajouter_a_table(self._chemin, img.cle, octets, mime or None, dict(self.rapport))
            with self._cond:
                self._table[img.cle] = octets
                if not self._persister:
                    self._a_reporter[img.cle] = (octets, mime or None)
        except Exception as e:
            logger.warning("Image %s non traduite : %s", img.cle, e)
            self.rapport["echecs"] += 1
