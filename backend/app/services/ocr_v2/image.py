"""Image traduite pour l'extension (étude §7 et §7.2).

Lit le texte d'une image, l'efface lettre par lettre et dessine la traduction
à sa place, dans la couleur d'origine. La traduction est injectée
(`traduire(textes) -> textes`) : la route de l'extension y branche le
traducteur et le débit, le module reste testable sans réseau.

- Contrôles avant décodage : type réel, poids, pixels, animation.
- Honnêteté : une ligne lue avec une confiance < 70 n'est pas touchée.
- Blocs : lignes voisines de même hauteur et de même couleur, traduites d'un
  seul tenant ; une puce ouvre un nouveau bloc.
- Mise en place, comme le PDF (§7.4) : gras gardé, bord gauche fixe (une
  étiquette isolée reste centrée), cadre étendu à droite jusqu'à l'encre
  voisine, retour à la ligne vers le bas dans le vide, puis réduction, la
  même pour les frères d'une liste ; sous le plancher, l'original reste et
  la traduction est renvoyée pour l'info-bulle.
- Effacement : la boîte de chaque ligne est élargie, le lecteur la rend plus
  étroite que les glyphes japonais.
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
from .render import longueur_trait

OCTETS_MAX = 10 * 1024 * 1024
PIXELS_MAX = 25_000_000
# Format lu -> type de l'original ; MPO = JPEG de smartphone (image secondaire ignorée).
FORMATS = {"PNG": "image/png", "JPEG": "image/jpeg", "MPO": "image/jpeg",
           "WEBP": "image/webp", "GIF": "image/gif"}
CONFIANCE_MIN = 70
ELARGIR = 1.35
PLANCHER = 0.6
PLANCHER_PX = 9
LISIBLE_PX = 24          # un grand titre peut descendre jusque-là : réduit, il reste lisible
MEME_HAUTEUR = 0.15
MEME_COULEUR = 80        # distance RVB entre deux lignes d'un même bloc
GRANDIR = 0.8            # en dessous, plus de retour à la ligne vers le bas : la réduction suffit
GRANDIR_LIGNES = 4       # hauteur gagnée au plus, en lignes lues
GRAS = {True: 0.095, False: 0.142}  # épaisseur du trait / hauteur d'encre, japonais ou non
# (Yu Gothic : 0,07 normal, 0,12 gras ; latin : 0,14 au plus normal, 0,15 au moins gras)
GOUTTIERE = 0.5          # × hauteur de ligne, gardée avant l'encre voisine
MEME_BORD = 0.5          # × hauteur de ligne : deux blocs alignés à gauche
MARGE_EFFACE = 0.2       # × hauteur de ligne, de chaque côté
SEUIL_ENCRE = 40         # écart au fond qui arrête l'agrandissement
_PUCE = re.compile(r"^\s*([0-9０-９]+[.)．）、]|[・•\-–*]|[①-⑳])")
DELAI_S = 30.0
_CJK = re.compile(r"[぀-ヿ㐀-鿿豈-﫿가-힯]")
_ROBOTO = {False: os.path.join(polices.FONTS_DIR, "roboto-Regular.ttf"),
           True: os.path.join(polices.FONTS_DIR, "roboto-Bold.ttf")}


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
    # Secondes par étape (lecture, traduction, effacement, total) : journal.
    durees: dict = field(default_factory=dict)
    # Faux si une zone a été remplie à la hâte faute de temps : rendu à ne pas garder en cache.
    complet: bool = True

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


@functools.lru_cache(maxsize=2)
def _fichier_police(gras=False):
    """Noto Sans si déjà sur disque (aucun téléchargement), sinon Roboto du dépôt."""
    r = polices.resolveur()
    if r.possede("Noto Sans", 700 if gras else 400, False):
        p, couche = r.resoudre("Noto Sans", bold=gras)
        if p and couche == "identique":
            return p
    return _ROBOTO[gras]


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


# Ponctuation CJK gardée par le traducteur : sans glyphe dans les polices de
# pose latines (carré vide). Remplacée quand la traduction n'a plus de CJK.
_PONCT_CJK = str.maketrans({
    "・": " • ", "、": ", ", "。": ". ", "，": ", ", "．": ". ", "：": ": ", "；": "; ",
    "！": "! ", "？": "? ", "「": " “", "」": "” ", "『": " “", "』": "” ", "【": " [",
    "】": "] ", "〔": " (", "〕": ") ", "（": " (", "）": ") ", "《": " “", "》": "” ",
    "〈": " ‹", "〉": "› ", "～": "~", "〜": "~", "　": " ", "－": "-", "ー": "-"})


def _ponctuation_latine(t):
    """`traduction` sans ponctuation CJK ni formes pleine chasse, si elle ne
    contient plus d'écriture CJK (langue cible latine)."""
    latine = t.translate(_PONCT_CJK)
    if _CJK.search(latine):
        return t
    t = latine
    t = "".join(chr(ord(c) - 0xFEE0) if "！" <= c <= "～" else c for c in t)
    t = re.sub(r"\s+([,.;:!?)\]”›])", r"\1", " ".join(t.split()))
    return re.sub(r"([(\[“‹])\s+", r"\1", t).strip()


def _couvre(fichier, texte):
    """La police a un glyphe pour chaque caractère visible du texte."""
    from .render import _ttf
    cmap = _ttf(fichier)[1]
    return all(ord(c) in cmap for c in texte if not c.isspace())


def _police_couvrante(fichier, texte, gras):
    """`fichier`, ou une police de secours qui a tous les glyphes du texte."""
    for f in (fichier, _fichier_police(gras), _ROBOTO[gras]):
        try:
            if _couvre(f, texte):
                return f
        except Exception:  # police illisible par fontTools : on garde la demandée
            return fichier
    return fichier


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


def blocs(lignes_lues, couleurs=None):
    """Regroupe les lignes voisines (même hauteur et couleur, empilées,
    recouvrement) ; une ligne qui commence par une puce ouvre un bloc."""
    out, teintes = [], []
    for n, (texte, b) in enumerate(lignes_lues):
        x, y, w, h = b
        c = np.array(couleurs[n], float) if couleurs else None
        for bl, tb in zip([] if _PUCE.match(texte) else out, teintes):
            px, py, pw, ph = bl.lignes[-1]
            # Écart négatif toléré : les boîtes PP-OCR débordent sur la ligne voisine.
            if (abs(h - ph) <= MEME_HAUTEUR * max(h, ph) and -0.3 * ph < y - (py + ph) < 0.8 * ph
                    and min(x + w, px + pw) > max(x, px)
                    and (c is None or np.linalg.norm(c - tb) <= MEME_COULEUR)):
                bl.lignes.append(b)
                bl.texte = _joindre([bl.texte, texte])
                bl.boite = _union(bl.lignes)
                break
        else:
            out.append(Bloc(texte, b, [b]))
            teintes.append(c)
    return out


def _couper(texte, police, largeur, casser=False):
    """Retour à la ligne glouton, par mots. Un texte sans espace se coupe par
    caractères s'il est CJK ; un mot latin reste entier (le corps baisse à la
    place), sauf `casser` : dernier recours quand même le plancher ne suffit pas."""
    t = texte.strip()
    if " " in t:
        unites, sep = t.split(), " "
    elif _CJK.search(t) or casser:
        unites, sep = list(t), ""
    else:
        unites, sep = [t], ""
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


def colonnes(bloc, largeur_image):
    """Colonnes `(x0, x1)` que la traduction peut occuper au plus large."""
    x, y, w, h = bloc.boite
    lmax = min(w * ELARGIR, largeur_image)
    x0 = x + w / 2 - lmax / 2 if len(bloc.lignes) == 1 else x
    x0 = min(max(x0, 0), largeur_image - lmax)
    return x0, x0 + lmax


def _encre(bgr, bloc):
    """Colonnes de la bande du bloc où l'image s'écarte du fond."""
    x, y, w, h = bloc.boite
    bande = bgr[y:y + h].astype(np.int16)
    fond = np.median(bande.reshape(-1, 3), axis=0)
    return np.abs(bande - fond).max(axis=2).max(axis=0) > SEUIL_ENCRE


def cadre(bgr, bloc, tous):
    """Colonnes `(x0, x1)` permises et alignement (vrai : centré), comme le
    PDF : un bloc de plusieurs lignes, ou qui partage son bord gauche avec un
    autre, garde ce bord et s'étend à droite jusqu'à l'encre voisine moins
    une gouttière, sinon jusqu'à une marge droite égale à la marge gauche ;
    une étiquette isolée reste centrée, avec autant de place des deux côtés."""
    W = bgr.shape[1]
    x, y, w, h = bloc.boite
    hl = float(np.median([b[3] for b in bloc.lignes]))
    sale = _encre(bgr, bloc)
    d, g = int(round(MARGE_EFFACE * hl)) + 1, GOUTTIERE * hl
    droite = next((c for c in range(min(x + w + d, W), W) if sale[c]), None)
    gauche = next((c for c in range(max(x - d, 0) - 1, -1, -1) if sale[c]), None)
    aligne = len(bloc.lignes) > 1 or any(
        o is not bloc and abs(o.boite[0] - x) <= MEME_BORD * hl for o in tous)
    if aligne:
        x1 = droite - g if droite is not None else W - x
        return x, max(min(x1, W), x + w), False
    cx = x + w / 2
    demi = min(cx - (gauche + g if gauche is not None else 0),
               (droite - g if droite is not None else W) - cx)
    demi = max(demi, w / 2)
    return max(cx - demi, 0), min(cx + demi, W), True


def placer(bloc, largeur_image, fichier=None, libre=None, cadre=None, taille_max=None):
    """Taille, lignes et cadre `(x, y, w)` de la traduction, ou `None` si
    elle ne tient pas au-dessus du plancher. `libre` : rangées `(haut, bas)`
    vides autour du bloc, où il peut grandir vers le bas ; `cadre` :
    `(x0, x1, centre)` donné par `cadre()` ; `taille_max` : taille commune
    d'une liste."""
    fichier = fichier or _fichier_police()
    x, y, w, h = bloc.boite
    hl = float(np.median([b[3] for b in bloc.lignes]))
    # Taille dont les glyphes « Hg » ont la hauteur des lignes lues.
    g100 = _police(fichier, 100).getbbox("Hg")
    k = (g100[3] - g100[1]) / 100
    s0 = max(int(hl / k), 1)
    n0 = len(bloc.lignes)
    pas0 = (bloc.lignes[-1][1] - bloc.lignes[0][1]) / (n0 - 1) if n0 > 1 else hl * 1.2
    if cadre is None:
        cadre = (*colonnes(bloc, largeur_image), n0 == 1)
    x0, x1, centre = cadre
    lmax = x1 - x0
    plancher = max(min(PLANCHER * s0, LISIBLE_PX), PLANCHER_PX)
    # Second passage : une étiquette serrée en largeur peut n'entrer sur deux
    # lignes qu'en dessous du seuil de croissance ; mieux vaut alors grandir
    # plus petit, d'une ligne au plus, que laisser l'original.
    # Dernier passage : un mot latin trop long même au plancher est coupé
    # plutôt que de laisser l'original.
    passes = [(GRANDIR * s0, None), (plancher, n0 + 1)] if libre else [(s0, None)]
    passes = [(*p, False) for p in passes]
    if not _CJK.search(bloc.traduction):
        passes.append((*passes[-1][:2], True))
    for seuil, nmax, casser in passes:
        s = min(s0, taille_max or s0)
        while s >= plancher:
            police = _police(fichier, s)
            texte_l = _couper(bloc.traduction, police, lmax, casser)
            pas = max(pas0, hl * 1.15) * s / s0
            haut = (len(texte_l) - 1) * pas + k * s
            larg = max(police.getlength(t) for t in texte_l)
            tient = larg <= lmax and haut <= h + 0.1 * hl
            # Étiquette centrée dans sa boîte ; sinon la première ligne reste à sa place.
            y1 = y + (h - haut) / 2 if centre and tient else y + (bloc.lignes[0][3] - k * s) / 2
            if (not tient and libre and larg <= lmax and s >= seuil
                    and (nmax is None or len(texte_l) <= nmax)
                    and haut <= min(libre[1] - libre[0], h + GRANDIR_LIGNES * hl)):
                y1, tient = min(max(y1, libre[0]), libre[1] - haut), True
            if tient:
                xt = x + w / 2 - larg / 2 if centre else x
                xt = min(max(xt, x0), x1 - larg)
                return {"taille": s, "lignes": texte_l, "pas": pas, "x": xt, "y": y1,
                        "haut_glyphe": k * s, "larg": larg, "haut": haut, "fichier": fichier}
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


def _gras(mask, boites, cjk=False):
    """Vrai si le trait des lettres est épais pour leur hauteur (§7.4) ; `mask`
    sans dilatation, sinon tous les traits paraissent gras."""
    r = []
    for x, y, w, h in boites:
        ink = ((mask[y:y + h, x:x + w] > 0) * 255).astype(np.uint8)
        rangs = np.nonzero(ink.any(axis=1))[0]
        lg = longueur_trait(ink) if len(rangs) > 1 else 0
        if lg:
            r.append(ink.sum() / 255 / lg / (rangs[-1] - rangs[0] + 1))
    return bool(r) and float(np.median(r)) > GRAS[cjk]


def _elargie(boite, bgr):
    """Boîte de ligne élargie pour l'effacement ; prolongée sur les côtés tant
    que l'encre continue au bord (lettre qui déborde de la boîte lue), au plus
    d'une demi-ligne."""
    h, l = bgr.shape[:2]
    x, y, w, hb = (int(round(v)) for v in boite)
    d = int(round(MARGE_EFFACE * hb))
    x0, y0 = max(x - d, 0), max(y - 2, 0)
    x1, y1 = min(x + w + d, l), min(y + hb + 2, h)
    bande = bgr[y0:y1].astype(np.int16)
    encre = (np.abs(bande - np.median(bande.reshape(-1, 3), axis=0)).max(axis=2) > SEUIL_ENCRE).any(axis=0)
    lim = int(round(0.5 * hb))
    while x1 < min(x + w + lim, l) and encre[x1]:
        x1 += 1
    while x0 > max(x - lim, 0) and encre[x0 - 1]:
        x0 -= 1
    return (x0, y0, x1 - x0, y1 - y0)


def _libre(bgr, bloc, autres, x0, x1, efface, poses=()):
    """Rangées `(haut, bas)` vides autour du bloc entre les colonnes x0..x1 :
    jusqu'à une demi-ligne d'une autre ligne lue (au moins mi-chemin), d'une
    traduction déjà posée (`poses` : `(x0, y0, x1, y1)`), ou d'une encre visible."""
    H = bgr.shape[0]
    x, y, w, h = bloc.boite
    x0, x1 = max(int(x0), 0), min(int(np.ceil(x1)), bgr.shape[1])
    haut, bas = 0, H
    for ax, ay, aw, ah in autres:
        if (ax, ay, aw, ah) in bloc.lignes or min(ax + aw, x1) <= max(ax, x0):
            continue
        if ay >= y + h:
            bas = min(bas, max((y + h + ay) // 2, ay - ah // 2))
        elif ay + ah <= y:
            haut = max(haut, min((ay + ah + y) // 2, ay + ah + ah // 2))
    # Fond : bord de la zone effacée ; encre : rangée qui s'en écarte.
    ex, ey, ew, eh = efface
    bord = np.concatenate([bgr[ey, ex:ex + ew], bgr[min(ey + eh, H - 1), ex:ex + ew]]).astype(np.int16)
    fond = np.median(bord, axis=0)
    sale = np.abs(bgr[:, x0:x1].astype(np.int16) - fond).max(axis=2).max(axis=1) > SEUIL_ENCRE
    for r in range(ey + eh, bas):
        if sale[r]:
            bas = r
            break
    for r in range(ey - 1, haut - 1, -1):
        if sale[r]:
            haut = r + 1
            break
    m = int(0.06 * h)  # respiration contre le bord et la ligne voisine
    for px0, py0, px1, py1 in poses:
        if min(px1, x1) > max(px0, x0):
            if py0 + py1 < 2 * y + h:
                haut = max(haut, int(np.ceil(py1)) + m)
            else:
                bas = min(bas, int(py0) - m)
    return min(haut + m, y), max(bas - m, y + h)


def _freres(places, W, teintes):
    """Des frères (même hauteur, police et couleur, alignés en colonne ou en
    rangée : liste, cases d'un tableau, boutons côte à côte) prennent une seule
    taille, celle du plus contraint ; `(bloc, placement)`."""
    famille = list(range(len(places)))

    def racine(i):
        while famille[i] != i:
            famille[i] = i = famille[famille[i]]
        return i

    def alignes(a, b, tol):
        (xa, ya, wa, ha), (xb, yb, wb, hb) = a, b
        colonne = min(abs(xa - xb), abs(xa + wa / 2 - xb - wb / 2), abs(xa + wa - xb - wb))
        rangee = min(abs(ya - yb), abs(ya + ha / 2 - yb - hb / 2))
        return colonne <= tol or rangee <= tol

    for i, (bi, pi, *_) in enumerate(places):
        for j in range(i):
            bj, pj = places[j][0], places[j][1]
            hi, hj = bi.boite[3], bj.boite[3]
            if (abs(hi - hj) <= MEME_HAUTEUR * max(hi, hj)
                    and alignes(bi.boite, bj.boite, MEME_BORD * min(hi, hj))
                    and pi["fichier"] == pj["fichier"]
                    and np.linalg.norm(np.subtract(teintes[i], teintes[j], dtype=float)) <= MEME_COULEUR):
                famille[racine(i)] = racine(j)
    out = []
    for i, (b, p, cb, libre) in enumerate(places):
        t = min(q[1]["taille"] for j, q in enumerate(places) if racine(j) == racine(i))
        if t < p["taille"]:  # plus petit : tient dans la même place
            p = placer(b, W, p["fichier"], libre, cb, taille_max=t) or p
        out.append((b, p))
    return out


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


def _preparer(data, lecteur):
    im = verifier(data)
    lecteur = lecteur or _ppocr()
    if lecteur.manquant():
        raise LectureEchouee("lecteur absent")
    try:
        rgba = ImageOps.exif_transpose(im).convert("RGBA")
    except Exception:  # fichier tronqué ou corrompu
        raise ImageRefusee("type")
    rgb = rgba.convert("RGB")
    return im, rgba, cv2.cvtColor(np.asarray(rgb), cv2.COLOR_RGB2BGR), lecteur


def lire_image(data, lecteur=None, delai_s=DELAI_S):
    """Lignes lues (OCR seul, sans traduction ni rendu) : vide si l'image n'a
    pas de texte. `traduire_image(..., lus=...)` les reprend sans relire."""
    _, _, bgr, lecteur = _preparer(data, lecteur)
    return lignes(_lire(lecteur, bgr, delai_s))


def _pareil(a: str, b: str) -> bool:
    """Même texte à la casse, aux espaces et à la ponctuation finale près."""
    n = lambda t: " ".join(t.split()).casefold().rstrip(".!?:;,。！？")
    return n(a) == n(b)


def traduire_image(data, traduire, lecteur=None, delai_s=DELAI_S, fichier_police=None, lus=None):
    """Image traduite (`ImageTraduite`) à partir des octets reçus.

    `traduire(textes)` renvoie une traduction par texte. `lus` : lignes déjà
    lues par `lire_image`, pour ne pas refaire l'OCR. `ImageRefusee` si
    l'image n'est pas acceptée, `LectureEchouee` si le lecteur manque ou
    échoue.
    """
    debut = time.monotonic()
    fin = debut + delai_s
    d = {}
    im, rgba, bgr, lecteur = _preparer(data, lecteur)
    fmt = im.format
    a = np.asarray(rgba.getchannel("A"))
    a = None if a.min() == 255 else a
    # Profil couleur gardé, sauf CMJN (converti en RVB, le profil ne vaut plus).
    icc = im.info.get("icc_profile") if im.mode != "CMYK" else None
    H, W = bgr.shape[:2]

    if lus is None:
        t = time.monotonic()
        lus = lignes(_lire(lecteur, bgr, max(fin - t, 1.0)))
        d["lecture"] = time.monotonic() - t
    zones = {b: _elargie(b, bgr) for _, b in lus}
    m0 = masque_couleur(bgr, list(zones.values())) if lus else None
    tous = blocs(lus, [_couleur(bgr, m0, b) for _, b in lus])
    if tous:
        t = time.monotonic()
        for b, tr in zip(tous, traduire([b.texte for b in tous])):
            # Retours à la ligne du traducteur retirés, ponctuation CJK rendue latine.
            b.traduction = _ponctuation_latine(_joindre((tr or "").split()))
        d["traduction"] = time.monotonic() - t

    places, poses = [], []
    for b in tous:
        x, y, w, h = b.boite
        # Déjà dans la langue cible (le traducteur l'a rendu tel quel) : laissé intact.
        if not b.traduction or _pareil(b.traduction, b.texte):
            continue
        # Lettres posées sur de la transparence : l'effacement ne les retirerait pas.
        if a is not None and a[y:y + h, x:x + w].min() < 255:
            continue
        cb = cadre(bgr, b, tous)
        efface = _union([zones[l] for l in b.lignes])
        libre = _libre(bgr, b, [l for _, l in lus], cb[0], cb[1], efface, poses)
        z = [zones[l] for l in b.lignes]
        gras = _gras(masque_couleur(bgr, z, dilatation=0), z, bool(_CJK.search(b.texte)))
        fichier = fichier_police or _police_couvrante(_fichier_police(gras), b.traduction, gras)
        p = placer(b, W, fichier, libre, cb)
        if p is not None:
            places.append((b, p, cb, libre))
            poses.append((p["x"], p["y"], p["x"] + p["larg"], p["y"] + p["haut"]))
    places = _freres(places, W, [_couleur(bgr, m0, b.boite) for b, *_ in places])

    if places:
        boites = [zones[l] for b, _ in places for l in b.lignes]
        mask = masque_couleur(bgr, boites)
        styles = [(_couleur(bgr, mask, b.boite), _contour(bgr, mask, b.boite)) for b, _ in places]
        t = time.monotonic()
        reste = max(fin - t, 1.0)
        efface, choix = effacer(bgr, boites, budget_s=reste, mask=mask, limite_s=reste)
        complet = "telea (délai)" not in choix
        d["effacement"] = time.monotonic() - t
        dessin = Image.fromarray(cv2.cvtColor(efface, cv2.COLOR_BGR2RGB))
        crayon = ImageDraw.Draw(dessin)
        for (b, p), (couleur, contour) in zip(places, styles):
            police = _police(p["fichier"], p["taille"])
            haut = police.getbbox("Hg")[1]
            opposee = (255, 255, 255) if sum(couleur) < 384 else (0, 0, 0)
            for i, t in enumerate(p["lignes"]):
                crayon.text((p["x"], p["y"] + i * p["pas"] - haut), t, font=police, fill=couleur,
                            stroke_width=max(1, round(p["taille"] / 14)) if contour else 0,
                            stroke_fill=opposee)
            b.remplace = True
    else:  # rien de dessiné : l'original, sans ré-encodage
        d["total"] = time.monotonic() - debut
        return ImageTraduite(data, FORMATS[fmt], tous, d)

    sortie = io.BytesIO()
    extra = {"icc_profile": icc} if icc else {}
    if FORMATS[fmt] == "image/jpeg":
        dessin.save(sortie, "JPEG", quality=92, **extra)
        d["total"] = time.monotonic() - debut
        return ImageTraduite(sortie.getvalue(), "image/jpeg", tous, d, complet)
    if a is not None:
        dessin.putalpha(Image.fromarray(a))
    dessin.save(sortie, "PNG", **extra)
    d["total"] = time.monotonic() - debut
    return ImageTraduite(sortie.getvalue(), "image/png", tous, d, complet)
