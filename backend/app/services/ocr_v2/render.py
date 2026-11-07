"""Rendu d'un scan : couche de texte stylée, mesurée sur les pixels (étude §7.1).

Le scan devient une page PDF « native » : fond effacé + texte dans la police,
la taille, la graisse, la pente et la couleur lues sur l'image. Le moteur PDF
la traduit ensuite comme n'importe quel PDF : seule la détection diffère d'un
document natif.

- Police : chaque candidate est rendue sur quelques mots du scan, à leur
  place ; on garde celle dont l'image ressemble le plus (serif ou non, chasse).
- Taille : hauteur des hampes (b, d, h, k, l) divisée par celle de la police
  choisie, moyennée par paragraphe puis ramenée aux corps fréquents.
- Gras, mot par mot : encre par longueur de trait (indépendant du flou).
- Italique, par ligne : cisaillement qui redresse le mieux les fûts.
- Largeur : chaque segment occupe la largeur mesurée (espacement `Tc`).
"""
import functools
import re

import cv2
import fitz
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from engines.pdf import polices

# Repli quand la police n'est pas encore connue (Inter et Helvetica).
HAMPE = 0.77
CAP = 0.73
# Polices de bureau et leurs clones libres, puis les familles du dépôt.
CANDIDATES = ("Arimo", "Tinos", "Carlito", "Caladea", "Cousine", "Gelasio",
              "Inter", "Roboto", "Open Sans", "Lato", "Noto Sans",
              "Source Sans 3", "Montserrat", "PT Serif", "Noto Serif",
              "Merriweather")
ECHANTILLON = 16
STYLES = {(0, 0): "Regular", (1, 0): "Bold", (0, 1): "Italic", (1, 1): "BoldItalic"}


def inclinaison(gris):
    """Angle (degrés, ±2) qui rend les lignes horizontales."""
    enc = cv2.adaptiveThreshold(gris, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 31, 15)
    petit = cv2.resize(enc, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    h, w = petit.shape
    best_a, best_v = 0.0, -1.0
    for a in np.arange(-2, 2.001, 0.05):
        r = cv2.warpAffine(petit, cv2.getRotationMatrix2D((w / 2, h / 2), a, 1), (w, h))
        v = float(np.var(r.sum(1, dtype=np.float64)))
        if v > best_v:
            best_a, best_v = float(a), v
    return best_a


def redresser(bgr):
    """`(image redressée, angle)` ; l'image est rendue telle quelle sous 0,1°
    (un pas de mesure : bruit de l'estimation)."""
    a = inclinaison(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY))
    if abs(a) < 0.1:
        return bgr, 0.0
    h, w = bgr.shape[:2]
    R = cv2.getRotationMatrix2D((w / 2, h / 2), a, 1)
    # Coins découverts : couleur du bord de page, pas de traînées recopiées.
    bord = np.concatenate([bgr[0], bgr[-1], bgr[:, 0], bgr[:, -1]])
    fond = tuple(float(v) for v in np.median(bord, 0))
    return cv2.warpAffine(bgr, R, (w, h), borderMode=cv2.BORDER_CONSTANT, borderValue=fond), a


def encre(lab_roi):
    """Pixels d'encre : écart au fond (médiane du bord), seuil d'Otsu."""
    bord = np.concatenate([lab_roi[0], lab_roi[-1], lab_roi[:, 0], lab_roi[:, -1]])
    d = np.linalg.norm(lab_roi - np.median(bord, 0), axis=2)
    d8 = np.clip(d / max(d.max(), 1) * 255, 0, 255).astype(np.uint8)
    s, _ = cv2.threshold(d8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return ((d > max(s / 255 * d.max(), 18)) * 255).astype(np.uint8)


def longueur_trait(ink):
    """Longueur du squelette, extrémités comprises.

    L'amincissement raccourcit chaque bout de trait (0,2 épaisseur, calé sur
    deux documents : 0,1 à 0,3 justes) : sans correction, un mot court à fûts
    droits (« Il », « a ») paraît gras.
    """
    sk = (cv2.ximgproc.thinning(ink) > 0).astype(np.uint8)
    sq = int(sk.sum())
    if not sq:
        return 0.0
    voisins = cv2.filter2D(sk, -1, np.ones((3, 3), np.float32), borderType=cv2.BORDER_CONSTANT) - sk
    bouts = int(((voisins == 1) & (sk > 0)).sum())
    return sq + bouts * 0.2 * (ink > 0).sum() / sq


def masse(gris_roi, ink):
    """Encre intégrée (1 - gris/papier) / longueur du squelette.

    Le flou étale un trait sans changer son intégrale, et le rapport au papier
    annule l'éclairage : la mesure ne dépend ni du seuil ni de la zone de page.
    """
    sq = longueur_trait(ink)
    if not sq:
        return 0.0
    g = gris_roi.astype(np.float32)
    bord = np.concatenate([g[0], g[-1], g[:, 0], g[:, -1]])
    zone = cv2.dilate(ink, np.ones((5, 5), np.uint8)) > 0
    return float(np.clip(1 - g / max(np.median(bord), 1), 0, 1)[zone].sum() / sq)


def pente(ink):
    """Cisaillement qui redresse le mieux les fûts.

    Pas de 0,05 ; un italique (~0,2 réel) se mesure 0,1 à 0,15 une fois flou, un romain 0.
    """
    h, w = ink.shape
    f = (ink > 0).astype(np.float32)
    best_s, best = 0.0, -1.0
    for s in np.linspace(-0.4, 0.4, 17):
        M = np.float32([[1, s, -min(s, 0) * h], [0, 1, 0]])
        r = cv2.warpAffine(f, M, (w + int(abs(s) * h) + 2, h))
        sc = float((r.sum(0) ** 2).sum())
        if sc > best:
            best_s, best = float(s), sc
    return best_s


@functools.lru_cache(None)
def _ttf(fichier):
    from fontTools.ttLib import TTFont
    f = TTFont(fichier, lazy=True)
    return f, f.getBestCmap(), f["head"].unitsPerEm


def _bornes(fichier, c):
    """`(boîte d'encre, avance)` du glyphe de `c`, en unités de la police ; `None` s'il manque."""
    from fontTools.pens.boundsPen import BoundsPen
    f, cmap, _ = _ttf(fichier)
    g = cmap.get(ord(c))
    if g is None:
        return None
    gs = f.getGlyphSet()
    p = BoundsPen(gs)
    gs[g].draw(p)
    return p.bounds, gs[g].width


@functools.lru_cache(None)
def hauteurs(fichier):
    """`{"hampe", "cap"}` : sommet des hampes et des capitales / corps."""
    upm = _ttf(fichier)[2]

    def haut(lettres, defaut):
        hs = [b[0][3] for b in map(functools.partial(_bornes, fichier), lettres) if b and b[0]]
        return max(hs) / upm if hs else defaut
    return {"hampe": haut("bdhkl", HAMPE), "cap": haut("HEI", CAP)}


def approches(fichier, premier, dernier):
    """Approche gauche du premier glyphe et droite du dernier, en em."""
    upm = _ttf(fichier)[2]
    a, b = _bornes(fichier, premier), _bornes(fichier, dernier)
    ag = a[0][0] / upm if a and a[0] else 0.0
    ad = (b[1] - b[0][2]) / upm if b and b[0] else 0.0
    return ag, ad


def paragraphes(mesures):
    """Lignes consécutives au même pas d'interligne et d'emprise voisine -> un paragraphe."""
    paras = []
    for m in mesures:
        p = paras[-1] if paras else None
        if p:
            d = p[-1]
            t = float(np.median([x["taille_px"] for x in p]))
            pas = m["base"] - d["base"]
            if (0.9 * t < pas < 2.3 * t and abs(m["taille_px"] - t) < 0.3 * t
                    and m["x0"] < d["x1"] and d["x0"] < m["x1"]):
                p.append(m)
                continue
        paras.append([m])
    return paras


def arrondir(pt):
    """Corps usuels : entiers dès 7 pt, demi-points en dessous."""
    return float(round(pt)) if pt >= 7 else round(pt * 2) / 2


def tailles(mesures, S, tol=0.15):
    """Taille par paragraphe (moyenne pondérée par les caractères, l'erreur
    d'un pixel ~0,5 pt s'y compense), rattachée aux corps fréquents de la page."""
    paras = paragraphes(mesures)
    n = [[sum(len(w["t"]) for w in m["mots"]) for m in p] for p in paras]
    est = [float(np.average([m["taille_px"] / S for m in p], weights=k)) for p, k in zip(paras, n)]
    poids = [sum(k) for k in n]
    centres = []   # [taille, membres], du plus lourd au plus léger
    for i in sorted(range(len(paras)), key=lambda i: -poids[i]):
        c = min(centres, key=lambda c: abs(c[0] - est[i]), default=None)
        if c is None or abs(c[0] - est[i]) > tol * c[0]:
            centres.append([est[i], [i]])
        else:
            c[1].append(i)
            c[0] = float(np.average([est[j] for j in c[1]], weights=[poids[j] for j in c[1]]))
    for c in centres:
        for i in c[1]:
            for m in paras[i]:
                m["taille"] = arrondir(c[0])


def _mesurer(bgr, mots):
    """Une mesure par ligne lue ; `None` pour une ligne sans encre mesurable."""
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    gris = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    H, W = gris.shape
    lignes = {}
    for m in mots:
        lignes.setdefault(m.ligne, []).append(m)
    mesures = []
    for groupe in lignes.values():
        groupe = sorted(groupe, key=lambda m: m.boite[0])
        hmot = float(np.median([m.boite[3] for m in groupe]))
        marge = max(2, int(round(0.15 * hmot)))
        X0 = max(min(m.boite[0] for m in groupe) - marge, 0)
        X1 = min(max(m.boite[0] + m.boite[2] for m in groupe) + marge, W)
        Y0 = max(min(m.boite[1] for m in groupe) - marge, 0)
        Y1 = min(max(m.boite[1] + m.boite[3] for m in groupe) + marge, H)
        ink_l = encre(lab[Y0:Y1, X0:X1]) if X1 - X0 > 2 and Y1 - Y0 > 2 else None
        if ink_l is None or not ink_l.any():
            mesures.append((groupe, None))
            continue
        prof = (ink_l > 0).sum(1)
        base = Y0 + np.where(prof >= 0.35 * prof.max())[0].max()   # sous 35 % : jambages (g, p)
        haut = Y0 + np.where(prof >= 0.08 * prof.max())[0].min()   # sous 8 % : accents (É, Ô)
        on = ink_l > 0
        mm, hs = [], []
        for m in groupe:
            x, _, w, _ = m.boite
            c0, c1 = max(x - X0, 0), min(x + w - X0 + 1, X1 - X0)
            sub = np.ascontiguousarray(ink_l[:, c0:c1])
            mm.append({"x": float(x), "x1": float(x + w), "t": m.texte, "c": (c0, c1),
                       "masse": masse(gris[Y0:Y1, X0 + c0:X0 + c1], sub),
                       "pente": pente(sub) if len(m.texte) >= 3 else None})
            # Sommet mesuré mot par mot sur les mots à hampe : une ligne longue
            # avec peu de hampes passe sous le seuil de 8 % du profil de ligne.
            if any(c in "bdhkl" for c in m.texte) and not any(c in "ÀÂÉÈÊËÎÏÔÙÛÇ" for c in m.texte):
                pw = (sub > 0).sum(1)
                if pw.max():
                    hs.append(base - (Y0 + np.where(pw >= 0.08 * pw.max())[0].min()) + 1)
        ps = [mo["pente"] for mo in mm if mo["pente"] is not None]
        mesures.append((groupe, {
            "base": float(base), "Y0": Y0, "X0": X0, "x0": X0, "x1": X1, "ink": ink_l,
            "haut_px": float(np.median(hs)) if hs else float(base - haut + 1),
            "sorte": "hampe" if hs else "cap",
            "couleur": np.median(bgr[Y0:Y1, X0:X1][on], 0),
            "italique": bool(ps) and float(np.median(ps)) > 0.07, "mots": mm}))
    return mesures


def _echantillon(mesures):
    """Mots longs, droits et maigres : la forme de la police régulière."""
    mots = [(m, mo) for m in mesures if not m["italique"] for mo in m["mots"]
            if len(mo["t"]) >= 4 and sum(c.isalpha() for c in mo["t"]) >= 0.75 * len(mo["t"])]
    if not mots:
        return []
    rel = [mo["masse"] / m["haut_px"] for m, mo in mots]
    seuil = float(np.median(rel)) * 1.1
    mots = [x for x, r in zip(mots, rel) if r <= seuil]
    return sorted(mots, key=lambda x: -len(x[1]["t"]))[:ECHANTILLON]


def _trait(masque):
    """Squelette adouci : le dessin des lettres sans leur épaisseur, que le
    flou et le rééchantillonnage du scan grossissent (et qui ferait gagner
    la police la plus grasse)."""
    sk = cv2.ximgproc.thinning(masque.astype(np.uint8) * 255) > 0
    return cv2.GaussianBlur(sk.astype(np.float32), (0, 0), 1.0)


def _recalage(a, b, r=1):
    """Meilleur produit `a·b` à ±r px près : la ligne de base et le bord
    estimés sur un scan rééchantillonné sont justes à un pixel près."""
    h, w = a.shape
    return max(float((a[max(dy, 0):h + min(dy, 0), max(dx, 0):w + min(dx, 0)]
                      * b[max(-dy, 0):h + min(-dy, 0), max(-dx, 0):w + min(-dx, 0)]).sum())
               for dy in range(-r, r + 1) for dx in range(-r, r + 1))


@functools.lru_cache(512)
def _police(fichier, taille):
    return ImageFont.truetype(fichier, size=max(taille, 1.0))


@functools.lru_cache(None)
def _fitz_font(fichier):
    return fitz.Font(fontfile=fichier)


def ressemblance(fichier, echantillon):
    """Recouvrement (Dice des squelettes adoucis, à 1 px près) entre le scan et la police
    rendue à la place de chaque mot, à deux tailles."""
    ratio = hauteurs(fichier)
    scores, poids = [], []
    for m, mo in echantillon:
        px = m["haut_px"] / ratio[m["sorte"]]
        h, w = m["ink"].shape
        # Une boîte de lecteur OCR peut rogner 1 à 2 px d'encre au bord du mot.
        c0, c1 = max(mo["c"][0] - 2, 0), min(mo["c"][1] + 2, w)
        marge = int(px)
        # Le scan ne garde que ce mot : une police trop large déborde sur du vide.
        scan = np.zeros((h, w + 2 * marge), np.float32)
        scan[:, marge + c0:marge + c1] = m["ink"][:, c0:c1] > 0
        cols = np.where(scan.any(0))[0]
        if not len(cols):
            continue
        a = _trait(scan > 0)
        # Deux tailles : celle des hampes (juge la hauteur des lettres) et celle
        # calée sur la largeur d'encre du mot (juge leur dessin, sans le décalage
        # de ±4 % qu'apporte 1 px d'erreur sur 25 px de hampe). Seule, chacune
        # confond plus souvent des empattements voisins (PT Serif / Merriweather).
        x0, _, x1, _ = _police(fichier, px).getbbox(mo["t"], anchor="ls")
        cale = px * float(np.clip((cols[-1] - cols[0] + 1) / (x1 - x0), 0.8, 1.25)) if x1 > x0 else px
        total = 0.0
        for taille in (px, cale):
            police = _police(fichier, taille)
            x_encre = police.getbbox(mo["t"], anchor="ls")[0]
            rendu = Image.new("L", (scan.shape[1], h), 0)
            ImageDraw.Draw(rendu).text((cols[0] - x_encre, m["base"] - m["Y0"]), mo["t"],
                                       font=police, fill=255, anchor="ls")
            b = _trait(np.asarray(rendu) > 127)
            den = float((a * a).sum() + (b * b).sum())
            total += 2 * _recalage(a, b) / den if den else 0.0
        scores.append(total / 2)
        poids.append(len(mo["t"]))
    return float(np.average(scores, weights=poids)) if scores else 0.0


def candidates(noms=CANDIDATES):
    """`(nom, fichier régulier)` des candidates déjà sur disque : aucun
    téléchargement pendant un envoi."""
    r = polices.resolveur()
    vus, out = set(), []
    for nom in noms:
        if not r.possede(nom, 400, False):
            continue
        p, couche = r.resoudre(nom)
        if p and couche == "identique" and p not in vus:
            vus.add(p)
            out.append((nom, p))
    return out


def choisir_police(mesures, familles=None):
    """`(nom, fichier régulier)` de la candidate la plus ressemblante, ou `None`."""
    familles = candidates() if familles is None else familles
    echantillon = _echantillon(mesures)
    if not familles:
        return None
    if not echantillon:
        return familles[0]
    return max(familles, key=lambda nf: ressemblance(nf[1], echantillon))


def ligne_simple(page, groupe, scale):
    """Écriture v1 (Helvetica à la taille de la boîte) d'une ligne non mesurée."""
    text = " ".join(w.texte for w in groupe)
    x0 = min(w.boite[0] for w in groupe) * scale
    y0 = min(w.boite[1] for w in groupe) * scale
    x1 = max(w.boite[0] + w.boite[2] for w in groupe) * scale
    y1 = max(w.boite[1] + w.boite[3] for w in groupe) * scale
    size = min((y1 - y0) / 0.8, (x1 - x0) / max(0.1, fitz.get_text_length(text, fontsize=1)))
    page.insert_text((x0, y1 - 0.1 * (y1 - y0)), text, fontname="helv", fontsize=size)


def ecrire(page, bgr, mots, dpi, familles=None):
    """Écrit sur `page` (mêmes proportions que `bgr`) le texte des `mots` lus,
    dans le style mesuré sur `bgr` (image d'origine, non effacée, redressée).

    Retourne le nom de la police choisie (`None` : écriture v1)."""
    S = dpi / 72
    lu = _mesurer(bgr, [w for w in mots if w.texte.strip()])
    mesures = [m for _, m in lu if m]
    choix = choisir_police(mesures, familles) if mesures else None
    if not choix:
        for groupe, _ in lu:
            ligne_simple(page, groupe, 1 / S)
        return None
    nom, regulier = choix
    ratio = hauteurs(regulier)
    for m in mesures:
        m["taille_px"] = m["haut_px"] / ratio[m["sorte"]]
    tailles(mesures, S)
    # Gras : encre par longueur de trait, rapportée au corps (le trait croît
    # avec lui). Le trait régulier vaut ~0,094 em ; une page assez fournie donne
    # sa propre référence (30e centile, ~0,083 em en PT Serif), sauf si tout est gras.
    tous = [(m, mo, mo["masse"] / (m["taille"] * S)) for m in mesures for mo in m["mots"]]
    ref = min(float(np.percentile([r for *_, r in tous], 30)), 0.094) if len(tous) >= 20 else 0.094
    for m, mo, rel in tous:
        mo["gras"] = bool(rel > ref * 1.3)
    for m in mesures:
        # Ponctuation isolée (« : ») : trop courte pour être mesurée, elle suit le mot précédent.
        for k, mo in enumerate(m["mots"]):
            if sum(c.isalnum() for c in mo["t"]) < 2 and len(m["mots"]) > 1:
                mo["gras"] = m["mots"][k - 1 if k else 1]["gras"]

    r = polices.resolveur()
    base = re.sub(r"[^0-9A-Za-z]", "", nom)
    fichiers, noms = {}, {}

    def variante(gras, ital):
        k = (int(gras), int(ital))
        if k not in fichiers:
            p = regulier
            # Variante déjà sur disque et de la même famille, sinon la régulière :
            # aucun téléchargement pendant un envoi, aucune police d'une autre famille.
            if k != (0, 0) and r.possede(nom, 700 if gras else 400, bool(ital)):
                q, couche = r.resoudre(nom, bool(gras), bool(ital))
                p = q if q and couche == "identique" else regulier
            fichiers[k] = p
            noms[k] = f"{base}-{STYLES[k]}"
            page.insert_font(fontname=noms[k], fontfile=p)
        return fichiers[k], noms[k]

    doc = page.parent
    for groupe, m in lu:
        if m is None:
            ligne_simple(page, groupe, 1 / S)
            continue
        runs = []
        for mo in m["mots"]:
            if runs and runs[-1][0] == mo["gras"]:
                runs[-1][2].append(mo["t"])
                runs[-1][3] = mo["x1"]
            else:
                runs.append([mo["gras"], mo["x"], [mo["t"]], mo["x1"]])
        c = np.array(m["couleur"][::-1]) / 255
        c = tuple(float(v) for v in (c if c.max() - c.min() > 0.15 else np.zeros(3)))   # gris de scan -> noir
        for gras, x, ts, x1 in runs:
            fichier, nom_f = variante(gras, m["italique"])
            texte = " ".join(ts)
            nat = _fitz_font(fichier).text_length(texte, m["taille"])
            # Le scan donne les bords de l'encre ; la police place les lettres
            # par leur chasse, qui déborde l'encre des deux approches latérales.
            ag, ad = approches(fichier, texte[0], texte[-1])
            x -= ag * m["taille"] * S
            # Chaque segment occupe la largeur mesurée : une ligne plus courte ou
            # plus longue que celle du natif ne se coupe pas au même endroit une
            # fois traduite. `Tc` étire sans changer la taille lue par le moteur.
            tc = ((x1 - x) / S + ad * m["taille"] - nat) / max(len(texte), 1)
            # Espace final comme un traitement de texte : le moteur compte
            # dans la largeur du paragraphe l'espace qui clôt chaque ligne native.
            if x1 == runs[-1][3]:
                texte += " "
            page.insert_text((x / S, m["base"] / S), texte, fontname=nom_f, fontsize=m["taille"], color=c)
            xr = page.get_contents()[-1]
            flux = doc.xref_stream(xr)
            i = flux.rfind(b" Tf")
            if i >= 0:
                doc.update_stream(xr, flux[:i + 3] + f" {tc:.4f} Tc".encode() + flux[i + 3:])
    return nom
