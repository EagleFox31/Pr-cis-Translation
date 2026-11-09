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
import contextlib
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
import pyphen
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
MEME_CORPS = 0.06        # libellés non alignés d'une figure : même corps à 6 % près
MEME_COULEUR = 80        # distance RVB entre deux lignes d'un même bloc
GRANDIR = 0.8            # au-delà d'une ligne de plus, pas de corps plus petit
TOLERE = 0.90           # réduction invisible préférée à une ligne de plus
CENTRE_CASE = 0.25      # écart (× hauteur de ligne) entre texte d'origine et milieu de sa case
CASE_PART = 0.97        # part de fond qu'une rangée doit garder pour agrandir la case
CASE_UNIE = 0.9          # case unie à 90 % : pas de contour autour de la traduction
CASE_MARGE = 0.06        # marge intérieure au plus 6 % de la largeur de la case
GRANDIR_LIGNES = 4       # hauteur gagnée au plus, en lignes lues
GRAS = {True: 0.095, False: 0.142}  # épaisseur du trait / hauteur d'encre, japonais ou non
# (Yu Gothic : 0,07 normal, 0,12 gras ; latin : 0,14 au plus normal, 0,15 au moins gras)
GOUTTIERE = 0.5          # × hauteur de ligne, gardée avant l'encre voisine
MEME_BORD = 0.5          # × hauteur de ligne : deux blocs alignés à gauche
MARGE_EFFACE = 0.2       # × hauteur de ligne, de chaque côté
SEUIL_ENCRE = 40         # écart au fond qui compte comme encre
PART_ENCRE = 0.3         # × contraste d'un texte pâle : son bord adouci compte encore
ENCRE_MIN = 10           # sous cet écart, bruit de compression
MUR = 10                 # écart au fond qui fait un mur de case (contour gris très pâle : 13)
OUVERT = 12             # côté sans mur : la case gagne au plus 12 lignes (ou la largeur du texte)
FLOTTANT = 2             # marges de plus de 2 lignes des deux côtés : étiquette dans le vide
AXE_CASE = 0.10          # case fermée des 4 côtés : texte à 10 % de largeur de son axe = centré dessus
FOND_MIN = 0.5           # moins de 50 % de fond derrière les lettres : fond chargé, pas de case
# Puce ou numéro en tête de ligne. « 1 - », « 1- » (tiret suivi d'une espace)
# et « 1－ » (tiret pleine chasse) numérotent ; « 3-days » reste un mot.
_PUCE = re.compile(r"^\s*([0-9０-９]+[.)．）、]|[0-9０-９]{1,3}\s*[－―—ー]"
                   r"|[0-9０-９]{1,3}\s*[-–]\s|[・•\-–—－―*]|[①-⑳])")
_FIN_PHRASE = re.compile(r"[。．.!?！？:：」』）)]\s*$")
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


def _trait(bgr, haut, bas):
    """Vrai si un trait horizontal (bord de case d'un tableau) sépare deux
    lignes empilées : une rangée de pixels, entre elles, presque toute à l'encre
    sur la largeur qu'elles partagent."""
    (px, py, pw, ph), (x, y, w, h) = haut, bas
    x0, x1 = max(x, px), min(x + w, px + pw)
    y0, y1 = max(min(py + ph, y) - 2, 0), max(py + ph, y) + 3
    bande = bgr[y0:y1, x0:x1].astype(np.int16)
    if bande.size == 0 or x1 - x0 < 8:
        return False
    fond = np.median(bgr[py:y + h, x0:x1].reshape(-1, 3), axis=0)
    encre = np.abs(bande - fond).max(axis=2) > SEUIL_ENCRE
    return bool((encre.mean(axis=1) > 0.8).any())


def blocs(lignes_lues, couleurs=None, puces=(), bgr=None):
    """Regroupe les lignes voisines (même hauteur et couleur, empilées,
    recouvrement) ; une ligne qui commence par une puce, lue ou dessinée
    (`puces` : boîtes de lignes), ouvre un bloc. Un trait dessiné entre deux
    lignes (`bgr` fourni) les sépare : titre d'un tableau et case en dessous."""
    out, teintes = [], []
    for n, (texte, b) in enumerate(lignes_lues):
        x, y, w, h = b
        c = np.array(couleurs[n], float) if couleurs else None
        for bl, tb in zip([] if _PUCE.match(texte) or b in puces else out, teintes):
            px, py, pw, ph = bl.lignes[-1]
            # Fin de phrase reportée seule sous la ligne (« …がで » / « きる。 ») :
            # la boîte d'un texte court varie plus en hauteur, on tolère le double.
            suite = (w < 0.5 * pw and abs(x - px) <= MEME_BORD * ph
                     and not _FIN_PHRASE.search(bl.texte))
            # Titre court derrière une puce dessinée (« ◆結果 ») et paragraphe
            # repris sous la puce : deux blocs, le titre ne se fond pas dans le texte.
            titre = (len(bl.lignes) == 1 and bl.lignes[0] in puces and w > 2 * pw
                     and x < px - MEME_BORD * ph)
            if titre:
                continue
            # Deux lignes centrées l'une sur l'autre (case d'un tableau, étiquette
            # sur deux lignes) : la boîte varie avec les jambages (« 3-days » /
            # « Before »), on tolère le double aussi. Pas en CJK : sans jambages,
            # un écart de hauteur y sépare un titre de sa légende.
            centrees = (abs(x + w / 2 - px - pw / 2) <= MEME_BORD * ph
                        and not _CJK.search(texte + bl.texte))
            tol = (2 if suite or centrees else 1) * MEME_HAUTEUR
            # Écart négatif toléré : les boîtes PP-OCR débordent sur la ligne voisine.
            if (abs(h - ph) <= tol * max(h, ph) and -0.3 * ph < y - (py + ph) < 0.8 * ph
                    and min(x + w, px + pw) > max(x, px)
                    and (c is None or np.linalg.norm(c - tb) <= MEME_COULEUR)
                    and (bgr is None or not _trait(bgr, bl.lignes[-1], b))):
                bl.lignes.append(b)
                bl.texte = _joindre([bl.texte, texte])
                bl.boite = _union(bl.lignes)
                break
        else:
            out.append(Bloc(texte, b, [b]))
            teintes.append(c)
    return out


@functools.lru_cache(maxsize=None)
def _dictionnaire(langue):
    """Césures de la langue cible (`pyphen`), ou `None` si elle n'en a pas."""
    code = pyphen.language_fallback((langue or "").replace("-", "_")) if langue else None
    return pyphen.Pyphen(lang=code) if code else None


def _couper(texte, police, largeur, casser=False, syllabes=None):
    """Retour à la ligne glouton, par mots. Un texte sans espace se coupe par
    caractères s'il est CJK ; un mot latin reste entier (le corps baisse à la
    place), sauf `casser` : dernier recours quand même le plancher ne suffit pas.
    `syllabes` : `(dictionnaire, largeur de la case)` ; un mot plus large que
    sa case s'y coupe aux syllabes, avec un trait d'union (« environ- / nementaux »)."""
    t = texte.strip()
    if " " in t:
        unites, sep = t.split(), " "
    elif _CJK.search(t) or casser:
        unites, sep = list(t), ""
    else:
        unites, sep = [t], ""
    out, cur = [], ""
    for u in unites:
        morceaux = [u]
        if syllabes and not casser and police.getlength(u) > syllabes[1]:
            bornes = [0, *syllabes[0].positions(u), len(u)]
            morceaux = [u[a:b] for a, b in zip(bornes, bornes[1:])]
        for k, m in enumerate(morceaux):
            essai = cur + (sep if k == 0 else "") + m if cur else m
            # Une coupure possible après ce morceau : son trait d'union doit tenir.
            trait = "-" if k < len(morceaux) - 1 else ""
            if cur and police.getlength(essai + trait) > largeur:
                out.append(cur + ("-" if k else ""))
                cur = m
            else:
                cur = essai
    if cur:
        out.append(cur)
    return out


def _equilibrer(texte, police, largeur, casser=False, n_min=1, syllabes=None):
    """Même coupure que `_couper`, au même nombre de lignes, mais à la largeur
    la plus étroite qui le permet : lignes de longueur voisine, jamais un mot
    seul sur la dernière (« … de la / cause »). `n_min` : au moins ce nombre
    de lignes si les mots le permettent (corps réduit, coupure d'origine gardée)."""
    def couper(lg):
        return _couper(texte, police, lg, casser, syllabes)

    out = couper(largeur)
    if len(out) < n_min:
        bas, haut = 1.0, float(largeur)  # plus grande largeur qui donne n_min lignes
        while haut - bas > 1:
            m = (bas + haut) / 2
            if len(couper(m)) >= n_min:
                bas = m
            else:
                haut = m
        essai = couper(bas)
        if len(essai) == n_min:
            out, largeur = essai, bas
    if len(out) < 2:
        return out
    bas, haut = 1.0, float(largeur)
    while haut - bas > 1:
        m = (bas + haut) / 2
        if len(couper(m)) == len(out):
            haut = m
        else:
            bas = m
    essai = couper(haut)
    return essai if len(essai) == len(out) else out


def conteneur(bgr, efface, lignes_bloc, autres=()):
    """Place libre autour du texte : `(case, uni, encre, part)`.

    `case` `(x0, y0, x1, y1)` : on part du cœur des lignes et on agrandit le
    rectangle de chaque côté tant que la nouvelle rangée garde au moins
    `CASE_PART` de la couleur de fond (la plus fréquente derrière les
    lettres). Un écart de `MUR` suffit à faire un mur : le contour gris pâle
    d'une case blanche arrête la croissance. Un côté sans mur s'arrête à
    `OUVERT` lignes (`GRANDIR_LIGNES` en hauteur), au bord de l'image, ou à
    mi-distance d'un autre texte lu (`autres` : boîtes de lignes) : deux
    étiquettes voisines se partagent le vide qui les sépare.
    `encre` `(x0, y0, x1, y1)` : lettres mesurées sur l'image, et non sur la
    boîte lue, qui mord souvent sur les bords de la case.
    `uni` : part de fond dans la case ; `part` : part de fond dans les lignes
    (faible : fond chargé, photo, dégradé)."""
    H, W = bgr.shape[:2]
    ex, ey, ew, eh = efface
    px = np.concatenate([bgr[int(ly):int(ly + lh), int(lx):int(lx + lw)].reshape(-1, 3)
                         for lx, ly, lw, lh in lignes_bloc]).astype(np.int16)
    q = px // 16
    cle = q[:, 0] * 256 + q[:, 1] * 16 + q[:, 2]
    fond = np.median(px[cle == np.bincount(cle).argmax()], axis=0)
    hl = float(np.median([l[3] for l in lignes_bloc]))
    m = int(hl)
    ok = np.abs(bgr.astype(np.int16) - fond).max(axis=2) <= MUR
    # Fond qui varie lentement (dégradé) : comparé au fond local, il reste du
    # fond tant qu'il ne s'écarte pas de plus de SEUIL_ENCRE ; un trait fin,
    # même pâle, tranche sur son voisinage et reste un mur.
    gx, gy = int(ew + 2 * m + OUVERT * hl) + 2, int(eh + 2 * m + GRANDIR_LIGNES * hl) + 2
    gx0, gy0, gx1, gy1 = max(ex - gx, 0), max(ey - gy, 0), min(ex + ew + gx, W), min(ey + eh + gy, H)
    reg = bgr[gy0:gy1, gx0:gx1]
    r = max(1, int(hl // 6))
    petit = cv2.resize(reg, (max((gx1 - gx0) // r, 1), max((gy1 - gy0) // r, 1)), interpolation=cv2.INTER_AREA)
    lisse = cv2.resize(cv2.medianBlur(petit, max(3, int(2 * hl / r)) | 1), (gx1 - gx0, gy1 - gy0),
                       interpolation=cv2.INTER_LINEAR).astype(np.int16)
    reg = reg.astype(np.int16)
    ok[gy0:gy1, gx0:gx1] |= ((np.abs(reg - lisse).max(axis=2) <= MUR)
                             & (np.abs(reg - fond).max(axis=2) <= SEUIL_ENCRE))
    z = ok[ey:ey + eh, ex:ex + ew]
    # Dans la zone du texte, seule une rangée (colonne) d'encre d'un bord à
    # l'autre est un trait ; le reste est du texte, compté comme fond.
    f = np.ones_like(z)
    tr, tc = z.mean(axis=1) < 0.15, z.mean(axis=0) < 0.15
    # Un trait sort de la zone : la barre d'un « H » ou d'un « l », pleine
    # hauteur dans une zone serrée, s'arrête à son bord.
    sort_h = np.zeros(eh, bool)
    for c in (ex - 1, ex + ew):
        if 0 <= c < W:
            sort_h |= ~ok[ey:ey + eh, c]
    sort_v = np.zeros(ew, bool)
    for r in (ey - 1, ey + eh):
        if 0 <= r < H:
            sort_v |= ~ok[r, ex:ex + ew]
    tr, tc = tr & sort_h, tc & sort_v
    f[tr, :], f[:, tc] = z[tr, :], z[:, tc]
    # Lettres : taches d'encre qui touchent les lignes lues, même si elles
    # débordent de la boîte lue (première lettre rognée), mais pas plus hautes
    # que 1,6 ligne ni plus larges que leur ligne : ni bordure, ni trait.
    rx0, ry0 = max(ex - m, 0), max(ey - m, 0)
    rx1, ry1 = min(ex + ew + m, W), min(ey + eh + m, H)
    encre_z = ~ok[ry0:ry1, rx0:rx1]
    zz = encre_z[ey - ry0:ey - ry0 + eh, ex - rx0:ex - rx0 + ew]
    zz[tr, :], zz[:, tc] = False, False
    n, lab, st, _ = cv2.connectedComponentsWithStats(encre_z.astype(np.uint8), connectivity=8)
    garde = np.zeros(n, bool)
    for lx, ly, lw, lh in lignes_bloc:
        sl = lab[max(int(ly) - ry0, 0):int(ly + lh) - ry0, max(int(lx) - rx0, 0):int(lx + lw) - rx0]
        for k in np.unique(sl[sl > 0]):
            garde[k] |= st[k, cv2.CC_STAT_HEIGHT] <= 1.6 * hl and st[k, cv2.CC_STAT_WIDTH] <= lw + 2 * hl
    lettres = garde[lab]
    # Part de fond derrière les lettres, halo compris (JPEG) : seul le fond
    # entre les lettres dit si la case est unie ou chargée.
    hors = ok[ry0:ry1, rx0:rx1].copy()
    pres = cv2.dilate(lettres.astype(np.uint8), np.ones((5, 5), np.uint8)) == 0
    dans = np.zeros_like(hors)
    for lx, ly, lw, lh in lignes_bloc:
        dans[max(int(ly) - ry0, 0):int(ly + lh) - ry0, max(int(lx) - rx0, 0):int(lx + lw) - rx0] = True
    sel = dans & pres
    part = float(hors[sel].mean()) if sel.any() else 0.0
    ok[ey:ey + eh, ex:ex + ew] = f
    ok[ry0:ry1, rx0:rx1] |= cv2.dilate(lettres.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    ys, xs = np.nonzero(lettres)
    if len(xs):
        encre = (rx0 + int(xs.min()), ry0 + int(ys.min()), rx0 + int(xs.max()) + 1, ry0 + int(ys.max()) + 1)
    else:
        u = _union(lignes_bloc)
        encre = (int(u[0]), int(u[1]), int(u[0] + u[2]), int(u[1] + u[3]))
    lx0, ly0, lx1, ly1 = encre
    ouvert = max(lx1 - lx0, OUVERT * hl)
    ax0, ax1 = 0, W  # côtés : bord de l'image ou mi-distance d'un voisin de rangée
    by0, by1 = ly0 - GRANDIR_LIGNES * hl, ly1 + GRANDIR_LIGNES * hl
    for ax, ay, aw, ah in autres:
        if min(ay + ah, ly1) > max(ay, ly0):  # même rangée
            if ax >= lx1:
                ax1 = min(ax1, (lx1 + ax) / 2)
            elif ax + aw <= lx0:
                ax0 = max(ax0, (ax + aw + lx0) / 2)
        elif min(ax + aw, lx1) > max(ax, lx0):  # même colonne
            if ay >= ly1:
                by1 = min(by1, (ly1 + ay) / 2)
            elif ay + ah <= ly0:
                by0 = max(by0, (ay + ah + ly0) / 2)
    ax0, ax1 = max(min(int(np.ceil(ax0)), lx0), 0), min(max(int(ax1), lx1), W)
    bx0, bx1 = max(ax0, int(np.ceil(lx0 - ouvert))), min(ax1, int(lx1 + ouvert))
    by0, by1 = max(min(int(np.ceil(by0)), ly0), 0), min(max(int(by1), ly1), H)
    x0, x1 = lx0, lx1
    y0 = int(lignes_bloc[0][1] + lignes_bloc[0][3] / 2)
    y1 = int(lignes_bloc[-1][1] + lignes_bloc[-1][3] / 2) + 1
    bouge = True
    while bouge:
        bouge = False
        if x0 > bx0 and ok[y0:y1, x0 - 1].mean() >= CASE_PART:
            x0, bouge = x0 - 1, True
        if x1 < bx1 and ok[y0:y1, x1].mean() >= CASE_PART:
            x1, bouge = x1 + 1, True
        if y0 > by0 and ok[y0 - 1, x0:x1].mean() >= CASE_PART:
            y0, bouge = y0 - 1, True
        if y1 < by1 and ok[y1, x0:x1].mean() >= CASE_PART:
            y1, bouge = y1 + 1, True
    # Murs en haut et en bas (case, bande, rangée de tableau) : la limite
    # `OUVERT` ne vaut que dans le vide ; la case suit la bande tant que ses
    # deux murs continuent, jusqu'à son mur de côté ou à un voisin.
    ferme = by0 < y0 and y1 < by1
    if ferme:
        def suit(c):
            return ok[y0:y1, c].mean() >= CASE_PART and not ok[y0 - 1, c] and not ok[y1, c]
        while x1 < ax1 and suit(x1):
            x1 += 1
        while x0 > ax0 and suit(x0 - 1):
            x0 -= 1
    # Close des quatre côtés : murs en haut et en bas, et sur les côtés un mur
    # plutôt que la mi-distance d'un voisin ou le bord de l'image.
    clos = ferme and ax0 < x0 and x1 < ax1
    return (x0, y0, x1, y1), float(ok[y0:y1, x0:x1].mean()), encre, part, ferme, clos


def _case(bgr, bloc, efface, autres=()):
    """Place offerte autour du bloc : `(cadre, libre, uni)` à passer à
    `placer()`, ou `None` sur un fond chargé (photo, dégradé), où la place
    se cherche par l'encre voisine (`cadre()`, `_libre()`).

    Alignement : bords des lignes s'ils varient assez ; sinon marges dans la
    case ; seul dans une case close, à `AXE_CASE` de son axe, il s'y centre.
    Une étiquette posée dans le vide (marges de plus de `FLOTTANT`
    lignes des deux côtés) garde son centre."""
    c, uni, encre, part, ferme, clos = conteneur(bgr, efface, bloc.lignes, autres)
    if part < FOND_MIN:
        return None
    ix0, iy0, ix1, iy1 = encre
    if c[0] > ix0 or c[1] > iy0 or c[2] < ix1 or c[3] < iy1:
        return None  # la case n'a pas pu s'étendre autour des lettres
    ls = bloc.lignes
    x, y, w, h = bloc.boite
    hl = float(np.median([l[3] for l in ls]))
    flottant = False
    mg, md = ix0 - c[0], c[2] - ix1
    large = c[2] - c[0]
    # Seul dans une case close et presque centré : l'écart est une marge
    # parasite, la traduction se centre sur l'axe de la case (comme le PDF).
    axe = clos and len(ls) == 1 and abs(mg - md) / 2 <= AXE_CASE * large
    if len(ls) > 1 and np.ptp([l[2] for l in ls]) >= 0.5 * hl:
        ecarts = [np.ptp([l[0] for l in ls]), np.ptp([l[0] + l[2] / 2 for l in ls]),
                  np.ptp([l[0] + l[2] for l in ls])]
        sens = ("gauche", "centre", "droite")[int(np.argmin(ecarts))]
    elif axe:
        sens = "centre"
    elif flottant := len(ls) == 1 and min(mg, md) > FLOTTANT * hl:
        sens = "centre"
    else:
        sens = ("centre" if abs(mg - md) <= max(0.5 * hl, 0.15 * large)
                else "gauche" if mg < md else "droite")
        # Paragraphe qui remplit sa case : marges égales mais sans portée.
        if len(ls) > 1 and sens == "centre" and mg + md < 0.2 * large:
            sens = "gauche"
    p = max(1, min(mg, md, 0.5 * hl, CASE_MARGE * large))
    x0, x1 = c[0] + p, c[2] - p
    if sens == "centre" and not axe and (flottant or abs(mg - md) > max(0.5 * hl, 0.15 * large)):
        # Centre propre du texte, et autant de place de chaque côté.
        cx, demi = (ix0 + ix1) / 2, min(mg, md) - p + (ix1 - ix0) / 2
        x0, x1 = cx - demi, cx + demi
    elif sens == "gauche":
        x0 = ix0  # retrait d'origine gardé
    elif sens == "droite":
        x1 = ix1
    py =max(1, min(iy0 - c[1], c[3] - iy1, 0.3 * hl))
    sens = {"centre": True, "gauche": False}.get(sens, sens)
    # Case fermée en haut et en bas, où l'original était centré : son milieu
    # sert au centrage vertical. Un libellé posé sur un trait, sous une autre
    # boîte, n'est pas au milieu de cet intervalle : il garde sa hauteur.
    centre_v = ferme and abs((iy0 + iy1) / 2 - (c[1] + c[3]) / 2) <= CENTRE_CASE * hl
    return (x0, x1, sens), (c[1] + py, c[3] - py), uni, (c[1] + c[3]) / 2 if centre_v else None


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


def placer(bloc, largeur_image, fichier=None, libre=None, cadre=None, taille_max=None, n_min=1,
           milieu=None, dico=None):
    """Taille, lignes et cadre `(x, y, w)` de la traduction, ou `None` si
    elle ne tient pas au-dessus du plancher. `libre` : rangées `(haut, bas)`
    vides autour du bloc, où il peut grandir vers le bas ; `cadre` :
    `(x0, x1, centre)` donné par `cadre()` ; `taille_max` : taille commune
    d'une liste ; `n_min` : lignes gardées quand le corps baisse ; `milieu` :
    milieu vertical d'une case fermée, où un texte centré pose le milieu de
    ses capitales (du haut des capitales à la ligne de base), comme en PAO :
    sans jambage, il ne remonte pas. `dico` : césures de la langue cible."""
    fichier = fichier or _fichier_police()
    x, y, w, h = bloc.boite
    hl = float(np.median([b[3] for b in bloc.lignes]))
    # Taille dont les glyphes « Hg » ont la hauteur des lignes lues.
    g100 = _police(fichier, 100).getbbox("Hg")
    k = (g100[3] - g100[1]) / 100
    c100 = _police(fichier, 100).getbbox("H")
    kc = (c100[3] - g100[1]) / 100  # haut des capitales → ligne de base
    s0 = s_h = max(int(hl / k), 1)
    n0 = len(bloc.lignes)
    # Jamais plus grand que l'original : pour une source latine, la largeur
    # lue mesure le corps mieux que la hauteur de boîte (gonflée de ~30 %).
    if not _CJK.search(bloc.texte):
        p100 = _police(fichier, 100)
        lu = p100.getlength(bloc.texte) - (n0 - 1) * p100.getlength(" ")
        if lu > 0:
            s0 = max(min(s0, int(100 * sum(l[2] for l in bloc.lignes) / lu)), 1)
    pas0 = (bloc.lignes[-1][1] - bloc.lignes[0][1]) / (n0 - 1) if n0 > 1 else hl * 1.2
    if cadre is None:
        cadre = (*colonnes(bloc, largeur_image), n0 == 1)
    x0, x1, sens = cadre
    centre, droite = sens is True, sens == "droite"
    lmax = x1 - x0
    plancher = max(min(PLANCHER * s0, LISIBLE_PX), PLANCHER_PX)
    # Ordre : le nombre de lignes d'origine sur toute la largeur (au besoin
    # avec une réduction de corps de 10 % au plus, qui ne se voit pas, quand
    # une ligne de plus se verrait), puis une ligne de plus, puis seulement
    # une réduction de corps. Dernier passage :
    # un mot latin trop long même au plancher est coupé plutôt que de laisser
    # l'original. Au-delà d'une ligne de plus, le texte ne descend pas sous
    # `GRANDIR` × le corps : une traduction bien plus longue reste en original
    # plutôt que tassée en petit sur de nombreuses lignes. Dès la ligne de
    # plus, un mot plus large que la case s'y coupe aux syllabes plutôt que
    # de faire baisser le corps de tout le texte.
    passes = [(max(n0, n_min), TOLERE * min(s0, taille_max or s0), False)]
    passes += ([(n0 + 1, plancher, False), (None, GRANDIR * s0, False)] if libre
               else [(None, plancher, False)])
    if not _CJK.search(bloc.traduction):
        passes.append((n0 + 1 if libre else None, plancher, True))
    for i_passe, (nmax, seuil, casser) in enumerate(passes):
        s = min(s0, taille_max or s0)
        if casser:  # couper un mot : seulement au plancher
            s = min(s, int(np.ceil(plancher)))
        while s >= max(plancher, seuil):
            police = _police(fichier, s)
            texte_l = _equilibrer(bloc.traduction, police, lmax, casser, n_min,
                                  (dico, lmax) if dico and i_passe else None)
            # Interligne rapporté au corps lu, sinon la 2ᵉ ligne descend trop bas.
            pas = max(pas0, hl * 1.15) * s / s_h
            haut = (len(texte_l) - 1) * pas + k * s
            larg = max(police.getlength(t) for t in texte_l)
            ok_n = nmax is None or len(texte_l) <= nmax
            tient = ok_n and larg <= lmax and haut <= h + 0.1 * hl
            # Étiquette centrée dans sa boîte ; sinon la première ligne reste à sa place.
            optique = (len(texte_l) - 1) * pas + kc * s
            y1 = y + (h - haut) / 2 if centre and tient else y + (bloc.lignes[0][3] - k * s) / 2
            if centre and tient and milieu is not None:
                y1 = milieu - optique / 2
            elif centre and tient and _CJK.search(bloc.texte):
                # Encre CJK ≈ carré du corps : son milieu reçoit le milieu
                # « haut des capitales → ligne de base », pas celui des jambages.
                y1 = y + h / 2 - optique / 2
            if tient and libre and libre[1] - libre[0] >= haut:
                y1 = min(max(y1, libre[0]), libre[1] - haut)
            # Mot coupé aux syllabes : seulement dans la hauteur lue, jamais
            # en débordant vers le bas (« Pièces / com- / mandées » sous la case).
            coupe = dico and i_passe and not casser and any(
                m not in bloc.traduction.split() for t in texte_l for m in t.split())
            if coupe and libre and haut > libre[1] - libre[0]:
                tient = False  # boîte lue plus haute que l'intérieur de la case
            if (not tient and not coupe and libre and ok_n and larg <= lmax
                    and haut <= min(libre[1] - libre[0], h + GRANDIR_LIGNES * hl)):
                if centre:
                    m = milieu if milieu is not None else (libre[0] + libre[1]) / 2
                    y1 = min(max(m - optique / 2, libre[0]), libre[1] - haut)
                else:
                    y1 = min(max(y1, libre[0]), libre[1] - haut)
                tient = True
            if tient:
                xt = (x0 + x1) / 2 - larg / 2 if centre else x1 - larg if droite else x
                xt = min(max(xt, x0), x1 - larg)
                # Chaque ligne centrée pour elle-même, ou calée à gauche ou à droite.
                xs = [xt + (larg - police.getlength(t)) * (0.5 if centre else 1 if droite else 0)
                      for t in texte_l]
                return {"taille": s, "lignes": texte_l, "pas": pas, "x": xt, "xs": xs, "y": y1,
                        "haut_glyphe": k * s, "larg": larg, "haut": haut, "fichier": fichier,
                        "milieu": milieu, "dico": dico}
            s = s - 1 if i_passe == 0 or s <= 20 else int(s * 0.94)
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
    ecart = np.abs(bande - np.median(bande.reshape(-1, 3), axis=0)).max(axis=2)
    # Texte pâle (gris 207 sur blanc : 48 d'écart) : son bord adouci passe sous
    # SEUIL_ENCRE ; le seuil suit alors le contraste de la ligne lue.
    contraste = float(ecart[:, x - x0:x - x0 + w].max()) if w > 0 else 0.0
    encre = (ecart > max(ENCRE_MIN, min(SEUIL_ENCRE, PART_ENCRE * contraste))).any(axis=0)
    lim = int(round(0.5 * hb))
    while x1 < min(x + w + lim, l) and encre[x1]:
        x1 += 1
    while x0 > max(x - lim, 0) and encre[x0 - 1]:
        x0 -= 1
    return (x0, y0, x1 - x0, y1 - y0)


def _symboles(lus, bgr):
    """Puces dessinées (◆, ●, ■…) que l'OCR ne lit pas, collées à gauche d'une
    ligne : `{boîte de la ligne: bord droit du symbole}`. Le symbole reste tel
    quel dans l'image ; la ligne ouvre un bloc, son effacement s'arrête avant
    lui et la traduction part du début du texte d'origine sans jamais le couvrir."""
    boites = [b for _, b in lus]
    out = {}
    for t, b in lus:
        x, y, w, h = (int(round(v)) for v in b)
        x0 = max(x - 2 * h, 0)
        z = bgr[y:y + h, x0:x].astype(np.int16)
        if _PUCE.match(t) or z.size == 0:
            continue
        m = (np.abs(z - np.median(z.reshape(-1, 3), axis=0)).max(axis=2) > SEUIL_ENCRE).astype(np.uint8)
        k, _, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
        trouve = None
        for sx, sy, sw, sh, a in st[1:k]:
            ecart = (x - x0) - (sx + sw)
            # Forme pleine, à peu près carrée, centrée sur la ligne, détachée
            # du premier glyphe (écart 0 = glyphe rogné par la boîte lue).
            pleine = (0.4 * h <= sh <= h and 0.6 <= sw / sh <= 1.6
                      and a >= 0.45 * sw * sh and abs(sy + sh / 2 - h / 2) <= 0.2 * h)
            # Tiret dessiné (« – Texte », « 1 – Texte » sans tiret lu) : barre
            # horizontale fine et pleine, à mi-hauteur de la ligne.
            tiret = (sh <= 0.2 * h and 0.25 * h <= sw <= h and sw >= 2 * sh
                     and a >= 0.6 * sw * sh and abs(sy + sh / 2 - h / 2) <= 0.25 * h)
            if 2 <= ecart <= 0.6 * h and sx > 0 and (pleine or tiret):
                trouve = x0 + int(sx + sw)
        if trouve is not None and not any(
                o is not b and o[0] < x and o[0] + o[2] > trouve
                and o[1] < y + h and o[1] + o[3] > y for o in boites):
            out[b] = trouve
    return out


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


def _hauteur_encre(masque, boites):
    """Hauteur médiane des lettres mesurées dans les lignes `boites` (0 sans
    encre). La boîte lue d'un texte CJK court est gonflée (問診 : 59 px lus
    pour 42 px de lettres, comme ses voisins de 50 px lus)."""
    hs = []
    for x, y, w, h in boites:
        r = np.flatnonzero(masque[y:y + h, x:x + w].any(axis=1))
        if r.size:
            hs.append(r[-1] - r[0] + 1)
    return float(np.median(hs)) if hs else 0.0


def _freres(places, W, teintes, encres=None):
    """Des frères (même hauteur d'origine et même couleur, n'importe où dans
    la figure : liste, cases d'un tableau, nœuds d'un organigramme) prennent
    une seule taille, celle du plus contraint ; `(bloc, placement)`. Un titre
    ou une légende d'une autre taille garde la sienne.

    Même hauteur : celle des lignes lues, ou à défaut celle des lettres
    mesurées (`encres`, une par place), que l'OCR ne gonfle pas."""
    famille = list(range(len(places)))
    encres = encres or [0.0] * len(places)

    def racine(i):
        while famille[i] != i:
            famille[i] = i = famille[famille[i]]
        return i

    for i, (bi, pi, *_) in enumerate(places):
        for j in range(i):
            bj, pj = places[j][0], places[j][1]
            # Hauteur de ligne, pas de bloc : deux paragraphes d'une case n'ont
            # pas le même nombre de lignes mais le même corps.
            hi = float(np.median([l[3] for l in bi.lignes]))
            hj = float(np.median([l[3] for l in bj.lignes]))
            # Alignés : même corps à `MEME_HAUTEUR` près ; ailleurs dans la
            # figure, à `MEME_CORPS` près, sans quoi des tailles voisines
            # s'enchaînent de proche en proche jusqu'au titre.
            (xa, ya, wa, ha), (xb, yb, wb, hb) = bi.boite, bj.boite
            tol = MEME_BORD * min(hi, hj)
            alignes = (min(abs(xa - xb), abs(xa + wa / 2 - xb - wb / 2), abs(xa + wa - xb - wb)) <= tol
                       or min(abs(ya - yb), abs(ya + ha / 2 - yb - hb / 2)) <= tol)
            marge = MEME_HAUTEUR if alignes else MEME_CORPS
            ei, ej = encres[i], encres[j]
            if ((abs(hi - hj) <= marge * max(hi, hj)
                 or (ei > 0 and ej > 0 and abs(ei - ej) <= marge * max(ei, ej)))
                    and np.linalg.norm(np.subtract(teintes[i], teintes[j], dtype=float)) <= MEME_COULEUR):
                famille[racine(i)] = racine(j)
    out = []
    for i, (b, p, cb, libre) in enumerate(places):
        t = min(q[1]["taille"] for j, q in enumerate(places) if racine(j) == racine(i))
        if t < p["taille"]:  # plus petit : tient dans la même place, sur autant de lignes
            p = placer(b, W, p["fichier"], libre, cb, taille_max=t, n_min=len(p["lignes"]),
                       milieu=p.get("milieu"), dico=p.get("dico")) or p
        out.append((b, p))
    return out


def _contour(bgr, mask, boite):
    """Fond chargé (texture, photo) : la traduction reçoit un contour. Jamais
    pour un simple trait : l'original n'a pas de liseré."""
    sl, zone = zones_par_boite(mask, [boite])[0]  # recadré : pas de masque pleine page
    if not zone.any():
        return False
    f = indicateurs(bgr[sl], zone, mask[sl])
    return f["texture"] > T_TEX


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


def lire_image(data, lecteur=None, delai_s=DELAI_S, tour=None):
    """Lignes lues (OCR seul, sans traduction ni rendu) : vide si l'image n'a
    pas de texte. `traduire_image(..., lus=...)` les reprend sans relire."""
    _, _, bgr, lecteur = _preparer(data, lecteur)
    with tour() if tour else contextlib.nullcontext():
        return lignes(_lire(lecteur, bgr, delai_s))


def _pareil(a: str, b: str) -> bool:
    """Même texte à la casse, aux espaces et à la ponctuation finale près."""
    n = lambda t: " ".join(t.split()).casefold().rstrip(".!?:;,。！？")
    return n(a) == n(b)


def traduire_image(data, traduire, lecteur=None, delai_s=DELAI_S, fichier_police=None, lus=None,
                   tour=None, langue=None):
    """Image traduite (`ImageTraduite`) à partir des octets reçus.

    `traduire(textes)` renvoie une traduction par texte. `lus` : lignes déjà
    lues par `lire_image`, pour ne pas refaire l'OCR. `ImageRefusee` si
    l'image n'est pas acceptée, `LectureEchouee` si le lecteur manque ou
    échoue. `tour()`, s'il est donné, encadre la seule reconnaissance (le
    guichet OCR n'est pas retenu pendant l'appel réseau de traduction).
    `langue` : langue cible (« fr »…), pour couper aux syllabes un mot plus
    large que sa case.
    """
    dico = _dictionnaire(langue)
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
        with tour() if tour else contextlib.nullcontext():
            # Le délai court à partir du tour obtenu, pas de l'attente au guichet.
            fin = time.monotonic() + delai_s
            t = time.monotonic()
            lus = lignes(_lire(lecteur, bgr, max(fin - t, 1.0)))
            d["lecture"] = time.monotonic() - t
    puces = _symboles(lus, bgr)
    zones = {b: _elargie(b, bgr) for _, b in lus}
    for b, bord in puces.items():  # le symbole dessiné n'est pas effacé
        zx, zy, zw, zh = zones[b]
        x1 = max(zx + zw, bord + 2)
        zones[b] = (max(zx, bord + 1), zy, x1 - max(zx, bord + 1), zh)
    m0 = masque_couleur(bgr, list(zones.values()), halo=False) if lus else None
    tous = blocs(lus, [_couleur(bgr, m0, b) for _, b in lus], puces, bgr)
    if tous:
        t = time.monotonic()
        for b, tr in zip(tous, traduire([b.texte for b in tous])):
            # Retours à la ligne du traducteur retirés, ponctuation CJK rendue latine.
            b.traduction = _ponctuation_latine(_joindre((tr or "").split()))
        d["traduction"] = time.monotonic() - t

    places, poses, unies, encres = [], [], set(), []
    for b in tous:
        x, y, w, h = b.boite
        # Déjà dans la langue cible (le traducteur l'a rendu tel quel) : laissé intact.
        if not b.traduction or _pareil(b.traduction, b.texte):
            continue
        # Lettres posées sur de la transparence : l'effacement ne les retirerait pas.
        if a is not None and a[y:y + h, x:x + w].min() < 255:
            continue
        efface = _union([zones[l] for l in b.lignes])
        # Case dessinée autour du texte : sa place et son alignement ; sinon
        # l'encre voisine et le vide autour du bloc.
        case = _case(bgr, b, efface, [l for _, l in lus if l not in b.lignes])
        cb = case[0] if case else cadre(bgr, b, tous)
        if b.lignes[0] in puces:  # après la puce dessinée, aligné à gauche, sans la couvrir
            x0 = max(x, b.lignes[0][0])
            cb = (x0, max(cb[1], x0 + w), False)
        if case:
            libre = case[1]
            if case[2] >= CASE_UNIE:
                unies.add(b.boite)
        else:
            libre = _libre(bgr, b, [l for _, l in lus], cb[0], cb[1], efface, poses)
        z = [zones[l] for l in b.lignes]
        encre = masque_couleur(bgr, z, dilatation=0, halo=False)
        gras = _gras(encre, z, bool(_CJK.search(b.texte)))
        fichier = fichier_police or _police_couvrante(_fichier_police(gras), b.traduction, gras)
        p = placer(b, W, fichier, libre, cb, milieu=case[3] if case else None, dico=dico)
        if p is not None:
            places.append((b, p, cb, libre))
            encres.append(_hauteur_encre(encre, z))
            poses.append((p["x"], p["y"], p["x"] + p["larg"], p["y"] + p["haut"]))
    places = _freres(places, W, [_couleur(bgr, m0, b.boite) for b, *_ in places], encres)

    if places:
        boites = [zones[l] for b, _ in places for l in b.lignes]
        mask = masque_couleur(bgr, boites)
        # Couleur et contour se mesurent sur le cœur des lettres : le halo
        # (bord adouci, pour l'effacement) tirerait la teinte vers le fond.
        coeur = masque_couleur(bgr, boites, halo=False)
        # Case unie : la traduction s'y lit sans contour.
        styles = [(_couleur(bgr, coeur, b.boite),
                   b.boite not in unies and _contour(bgr, coeur, b.boite)) for b, _ in places]
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
                crayon.text((p["xs"][i], p["y"] + i * p["pas"] - haut), t, font=police, fill=couleur,
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
