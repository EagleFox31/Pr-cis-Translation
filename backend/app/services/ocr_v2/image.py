"""Image traduite pour l'extension (étude §7 et §7.2).

Lit le texte d'une image, l'efface lettre par lettre et dessine la traduction
à sa place, dans la couleur d'origine. La traduction est injectée
(`traduire(textes) -> textes`) : la route de l'extension y branche le
traducteur et le débit, le module reste testable sans réseau.

- Contrôles avant décodage : type réel, poids, pixels, animation.
- Honnêteté : une ligne lue avec une confiance < 70 n'est pas touchée.
- Blocs : lignes voisines de même hauteur, traduites d'un seul tenant.
- Mise en place : boîte élargie jusqu'à 1,35 fois, retour à la ligne, puis
  réduction jusqu'au plancher ; sous le plancher, l'original reste et la
  traduction est renvoyée pour l'info-bulle.
"""
import functools
import io
import os
import re
import tempfile
import threading
import time
from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

from engines.pdf import polices
from .detect import LectureEchouee
from .erase import T_TEX, effacer, indicateurs, zones_par_boite
from .mask import masque_couleur

OCTETS_MAX = 10 * 1024 * 1024
PIXELS_MAX = 25_000_000
# Format lu -> type de l'original ; MPO = JPEG de smartphone (image secondaire ignorée).
FORMATS = {"PNG": "image/png", "JPEG": "image/jpeg", "MPO": "image/jpeg",
           "WEBP": "image/webp", "GIF": "image/gif"}
CONFIANCE_MIN = 70
ELARGIR = 1.35
PLANCHER = 0.6
PLANCHER_PX = 9
DELAI_S = 30.0
_CJK = re.compile(r"[぀-ヿ㐀-鿿豈-﫿가-힯]")
_ROBOTO = os.path.join(polices.FONTS_DIR, "roboto-Regular.ttf")


class ImageRefusee(ValueError):
    """Image refusée avant décodage ; `code` : type, taille, pixels, animee."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


@dataclass
class Bloc:
    texte: str
    boite: tuple[int, int, int, int]  # (x, y, w, h) en pixels
    lignes: list = field(default_factory=list)  # boîtes des lignes d'origine
    traduction: str = ""
    remplace: bool = False


@dataclass
class ImageTraduite:
    data: bytes
    mime: str
    blocs: list[Bloc]

    @property
    def remplacee(self):
        """Vrai si au moins un bloc a été dessiné : c'est ce qui se débite."""
        return any(b.remplace for b in self.blocs)


def verifier(data):
    """Image PIL ouverte (en-tête seulement), ou `ImageRefusee`."""
    if len(data) > OCTETS_MAX:
        raise ImageRefusee("taille")
    try:
        im = Image.open(io.BytesIO(data))
    except Image.DecompressionBombError:
        raise ImageRefusee("pixels")
    except Exception:
        raise ImageRefusee("type")
    if im.format not in FORMATS:
        raise ImageRefusee("type")
    if im.width * im.height > PIXELS_MAX:
        raise ImageRefusee("pixels")
    if im.format != "MPO" and getattr(im, "is_animated", False):
        raise ImageRefusee("animee")
    return im


@functools.lru_cache(maxsize=1)
def _fichier_police():
    """Noto Sans si déjà sur disque (aucun téléchargement), sinon Roboto du dépôt."""
    r = polices.resolveur()
    if r.possede("Noto Sans", 400, False):
        p, couche = r.resoudre("Noto Sans")
        if p and couche == "identique":
            return p
    return _ROBOTO


def _police(fichier, taille):
    # Une police par fil : FreeType n'est pas sûr d'un fil à l'autre.
    return _police_fil(fichier, taille, threading.get_ident())


@functools.lru_cache(maxsize=256)
def _police_fil(fichier, taille, fil):
    return ImageFont.truetype(fichier, taille)


def _union(boites):
    """Boîte englobante, en pixels entiers (les lecteurs peuvent rendre des flottants)."""
    x0 = int(min(b[0] for b in boites)); y0 = int(min(b[1] for b in boites))
    x1 = int(np.ceil(max(b[0] + b[2] for b in boites)))
    y1 = int(np.ceil(max(b[1] + b[3] for b in boites)))
    return (x0, y0, x1 - x0, y1 - y0)


def _joindre(morceaux):
    """Mots d'une ligne : sans espace entre deux caractères CJK."""
    out = ""
    for m in morceaux:
        if out and not (_CJK.search(out[-1]) and _CJK.search(m[0])):
            out += " "
        out += m
    return out


def lignes(mots):
    """`(texte, boîte)` des lignes assez sûres, dans l'ordre de lecture."""
    groupes = {}
    for m in mots:
        groupes.setdefault(m.ligne, []).append(m)
    out = []
    for g in groupes.values():
        if np.mean([m.conf for m in g]) < CONFIANCE_MIN:
            continue
        out.append((_joindre([m.texte for m in g]), _union([m.boite for m in g])))
    return out


def blocs(lignes_lues):
    """Regroupe les lignes voisines (même hauteur, empilées, recouvrement)."""
    out = []
    for texte, b in lignes_lues:
        x, y, w, h = b
        for bl in out:
            px, py, pw, ph = bl.lignes[-1]
            # Écart négatif toléré : les boîtes PP-OCR débordent sur la ligne voisine.
            if (abs(h - ph) <= 0.3 * max(h, ph) and -0.3 * ph < y - (py + ph) < 0.8 * ph
                    and min(x + w, px + pw) > max(x, px)):
                bl.lignes.append(b)
                bl.texte = _joindre([bl.texte, texte])
                bl.boite = _union(bl.lignes)
                break
        else:
            out.append(Bloc(texte, b, [b]))
    return out


def _couper(texte, police, largeur):
    """Retour à la ligne glouton (par mots, ou par caractères sans espace)."""
    unites = texte.split() if " " in texte.strip() else list(texte.strip())
    sep = " " if " " in texte.strip() else ""
    out, cur = [], ""
    for u in unites:
        essai = cur + sep + u if cur else u
        if cur and police.getlength(essai) > largeur:
            out.append(cur)
            cur = u
        else:
            cur = essai
    if cur:
        out.append(cur)
    return out


def placer(bloc, largeur_image, fichier=None):
    """Taille, lignes et cadre `(x, y, w)` de la traduction, ou `None` si
    elle ne tient pas au-dessus du plancher."""
    fichier = fichier or _fichier_police()
    x, y, w, h = bloc.boite
    hl = float(np.median([b[3] for b in bloc.lignes]))
    # Taille dont les glyphes « Hg » ont la hauteur des lignes lues.
    g100 = _police(fichier, 100).getbbox("Hg")
    k = (g100[3] - g100[1]) / 100
    s0 = max(int(hl / k), 1)
    n0 = len(bloc.lignes)
    pas0 = (bloc.lignes[-1][1] - bloc.lignes[0][1]) / (n0 - 1) if n0 > 1 else hl * 1.2
    lmax = min(w * ELARGIR, largeur_image)
    plancher = max(PLANCHER * s0, PLANCHER_PX)
    s = s0
    while s >= plancher:
        police = _police(fichier, s)
        texte_l = _couper(bloc.traduction, police, lmax)
        pas = max(pas0, hl * 1.15) * s / s0
        haut = (len(texte_l) - 1) * pas + k * s
        larg = max(police.getlength(t) for t in texte_l)
        if larg <= lmax and haut <= h + 0.1 * hl:
            if n0 == 1:  # étiquette : élargie autour de son centre
                x1 = x + w / 2 - larg / 2
            else:        # paragraphe : aligné à gauche
                x1 = x
            x1 = min(max(x1, 0), largeur_image - larg)
            return {"taille": s, "lignes": texte_l, "pas": pas, "x": x1,
                    "y": y + (h - haut) / 2, "haut_glyphe": k * s}
        s = int(s * 0.94) if s > 20 else s - 1
    return None


def _couleur(bgr, mask, boite):
    """Couleur (RGB) des lettres : pixels du masque les plus loin du fond."""
    x, y, w, h = boite
    roi = bgr[y:y + h, x:x + w].reshape(-1, 3).astype(np.float32)
    m = mask[y:y + h, x:x + w].reshape(-1) > 0
    if m.sum() < 4 or (~m).sum() < 4:
        return (0, 0, 0)
    fond = np.median(roi[~m], axis=0)
    lettres = roi[m]
    d = np.linalg.norm(lettres - fond, axis=1)
    c = np.median(lettres[d >= np.percentile(d, 70)], axis=0)
    return tuple(int(v) for v in c[::-1])


def _contour(bgr, mask, boite):
    """Fond chargé ou trait traversant : la traduction reçoit un contour."""
    sl, zone = zones_par_boite(mask, [boite])[0]  # recadré : pas de masque pleine page
    if not zone.any():
        return False
    f = indicateurs(bgr[sl], zone, mask[sl])
    return f["traits"] > 0 or f["texture"] > T_TEX


def _lire(lecteur, bgr, delai):
    if hasattr(lecteur, "lire_image"):
        return lecteur.lire_image(bgr, delai)
    with tempfile.TemporaryDirectory() as dossier:
        chemin = os.path.join(dossier, "image.png")
        cv2.imwrite(chemin, bgr)
        return lecteur.lire(chemin, delai)


_LECTEUR = None
_VERROU = threading.Lock()


def _ppocr():
    global _LECTEUR
    with _VERROU:  # un seul chargement des poids, même sous requêtes simultanées
        if _LECTEUR is None:
            from .ppocr import PPOCR
            _LECTEUR = PPOCR()
    return _LECTEUR


def traduire_image(data, traduire, lecteur=None, delai_s=DELAI_S, fichier_police=None):
    """Image traduite (`ImageTraduite`) à partir des octets reçus.

    `traduire(textes)` renvoie une traduction par texte. `ImageRefusee` si
    l'image n'est pas acceptée, `LectureEchouee` si le lecteur manque ou
    échoue.
    """
    fin = time.monotonic() + delai_s
    im = verifier(data)
    lecteur = lecteur or _ppocr()
    if lecteur.manquant():
        raise LectureEchouee("lecteur absent")
    fmt = im.format
    try:
        rgba = ImageOps.exif_transpose(im).convert("RGBA")
    except Exception:  # fichier tronqué ou corrompu
        raise ImageRefusee("type")
    a = np.asarray(rgba.getchannel("A"))
    a = None if a.min() == 255 else a
    # Profil couleur gardé, sauf CMJN (converti en RVB, le profil ne vaut plus).
    icc = im.info.get("icc_profile") if im.mode != "CMYK" else None
    rgb = rgba.convert("RGB")
    bgr = cv2.cvtColor(np.asarray(rgb), cv2.COLOR_RGB2BGR)
    W = bgr.shape[1]

    tous = blocs(lignes(_lire(lecteur, bgr, max(fin - time.monotonic(), 1.0))))
    if tous:
        for b, t in zip(tous, traduire([b.texte for b in tous])):
            b.traduction = _joindre((t or "").split())  # retours à la ligne du traducteur

    places = []
    for b in tous:
        x, y, w, h = b.boite
        if not b.traduction or b.traduction == b.texte:
            continue
        # Lettres posées sur de la transparence : l'effacement ne les retirerait pas.
        if a is not None and a[y:y + h, x:x + w].min() < 255:
            continue
        p = placer(b, W, fichier_police)
        if p is not None:
            places.append((b, p))

    if places:
        boites = [l for b, _ in places for l in b.lignes]
        mask = masque_couleur(bgr, boites)
        styles = [(_couleur(bgr, mask, b.boite), _contour(bgr, mask, b.boite)) for b, _ in places]
        reste = max(fin - time.monotonic(), 1.0)
        efface, _ = effacer(bgr, boites, budget_s=reste, mask=mask, limite_s=reste)
        dessin = Image.fromarray(cv2.cvtColor(efface, cv2.COLOR_BGR2RGB))
        crayon = ImageDraw.Draw(dessin)
        fichier = fichier_police or _fichier_police()
        for (b, p), (couleur, contour) in zip(places, styles):
            police = _police(fichier, p["taille"])
            haut = police.getbbox("Hg")[1]
            opposee = (255, 255, 255) if sum(couleur) < 384 else (0, 0, 0)
            for i, t in enumerate(p["lignes"]):
                crayon.text((p["x"], p["y"] + i * p["pas"] - haut), t, font=police, fill=couleur,
                            stroke_width=max(1, round(p["taille"] / 14)) if contour else 0,
                            stroke_fill=opposee)
            b.remplace = True
    else:  # rien de dessiné : l'original, sans ré-encodage
        return ImageTraduite(data, FORMATS[fmt], tous)

    sortie = io.BytesIO()
    extra = {"icc_profile": icc} if icc else {}
    if FORMATS[fmt] == "image/jpeg":
        dessin.save(sortie, "JPEG", quality=92, **extra)
        return ImageTraduite(sortie.getvalue(), "image/jpeg", tous)
    if a is not None:
        dessin.putalpha(Image.fromarray(a))
    dessin.save(sortie, "PNG", **extra)
    return ImageTraduite(sortie.getvalue(), "image/png", tous)
