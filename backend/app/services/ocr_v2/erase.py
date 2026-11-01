"""Effacement du texte : méthode de remplissage choisie zone par zone (étude §6).

Aucune méthode ne gagne partout (aplat sur fond uni, harmonique sur dégradé,
FSR sur texture, structurel sous une flèche). On choisit par le « masque
fantôme » : la forme du masque est recopiée à côté, sur des pixels de fond
connus ; chaque méthode y reconstruit ce fond, et celle qui s'en approche le
plus est appliquée au vrai trou. Quand le budget de temps est épuisé, ou
qu'aucune position fantôme n'est libre, une règle sur le fond prend le relais.
"""
import time

import cv2
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spl

from .mask import anneau, composantes, masque_couleur

# Marge autour d'une zone pour les méthodes qui travaillent sur un recadrage.
MARGE = 24
# Fantôme : ~0,6 s par zone. Au-delà de ce budget par image, la règle (0,05 s).
BUDGET_S = 8.0


def _ajuster(A, v):
    """Moindres carrés en deux passes : `(coef, résidus gardés)`.

    Quelques pixels d'anticrénelage ou de trait restés dans la couronne
    tirent le fond vers leur couleur (lettre fantôme rosée sous un trait
    rouge) et font passer un dégradé pour une texture. La seconde passe les
    écarte (au-delà de 3 écarts robustes) ; une vraie texture n'y perd presque rien.
    """
    coef, *_ = np.linalg.lstsq(A, v, rcond=None)
    res = v - A @ coef
    ecart = np.abs(res - np.median(res))
    garde = ecart <= max(3 * 1.4826 * np.median(ecart), 1.0)
    if garde.sum() > A.shape[1]:
        coef, *_ = np.linalg.lstsq(A[garde], v[garde], rcond=None)
        res = (v - A @ coef)[garde]
    return coef, res


# ── Méthodes de remplissage : f(image, mask) -> image ────────────────────────

def m_aplat(image, mask):
    """Couleur médiane de la couronne : parfait sur fond uni."""
    out = image.copy()
    for z in composantes(mask):
        a = anneau(z.astype(np.uint8) * 255, 6, exclure=mask)
        if a.any():
            out[z] = np.median(image[a], axis=0)
    return out


def m_plan(image, mask):
    """Plan affine ajusté sur la couronne : dégradés linéaires."""
    out = image.astype(np.float32)
    for z in composantes(mask):
        a = anneau(z.astype(np.uint8) * 255, 6, exclure=mask)
        ya, xa = np.nonzero(a)
        if len(ya) < 10:
            continue
        A = np.c_[xa, ya, np.ones_like(xa)].astype(np.float32)
        yz, xz = np.nonzero(z)
        B = np.c_[xz, yz, np.ones_like(xz)].astype(np.float32)
        for ch in range(3):
            coef, _ = _ajuster(A, image[ya, xa, ch].astype(np.float32))
            out[yz, xz, ch] = B @ coef
    return np.clip(out, 0, 255).astype(np.uint8)


def m_harmonique(image, mask):
    """Équation de Laplace, bord imposé : la surface la plus lisse qui raccorde
    exactement le bord. Meilleure méthode sur dégradé non linéaire."""
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        return image.copy()
    out = image.astype(np.float64)
    H, W = mask.shape
    idx = -np.ones(mask.shape, np.int64)
    idx[ys, xs] = np.arange(len(ys))
    k = np.arange(len(ys))
    voisins = np.zeros(len(ys))
    b = np.zeros((len(ys), 3))
    rows, cols = [], []
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        yy, xx = ys + dy, xs + dx
        dedans = (yy >= 0) & (yy < H) & (xx >= 0) & (xx < W)
        voisins += dedans
        j = np.full(len(ys), -1)
        j[dedans] = idx[yy[dedans], xx[dedans]]
        inconnu = j >= 0
        rows.append(k[inconnu]); cols.append(j[inconnu])
        connu = dedans & ~inconnu
        b[connu] += out[yy[connu], xx[connu]]
    rows = np.concatenate(rows + [k]); cols = np.concatenate(cols + [k])
    vals = np.concatenate([-np.ones(len(rows) - len(k)), voisins])
    resoudre = spl.factorized(sp.csc_matrix((vals, (rows, cols)), shape=(len(ys), len(ys))))
    for ch in range(3):
        out[ys, xs, ch] = resoudre(b[:, ch])
    return np.clip(out, 0, 255).astype(np.uint8)


def m_telea(image, mask):
    return cv2.inpaint(image, mask, 3, cv2.INPAINT_TELEA)


def m_fsr(image, mask):
    """Frequency Selective Reconstruction (opencv-contrib) : meilleure méthode
    sans IA sur texture et quadrillage. Son masque est INVERSE (0 = à refaire)."""
    out = image.copy()
    for z in composantes(mask):
        ys, xs = np.nonzero(z)
        y0, y1 = max(ys.min() - MARGE, 0), min(ys.max() + MARGE + 1, image.shape[0])
        x0, x1 = max(xs.min() - MARGE, 0), min(xs.max() + MARGE + 1, image.shape[1])
        crop = image[y0:y1, x0:x1].copy()
        valide = (mask[y0:y1, x0:x1] == 0).astype(np.uint8) * 255
        dst = np.zeros_like(crop)
        cv2.xphoto.inpaint(crop, valide, dst, cv2.xphoto.INPAINT_FSR_FAST)
        sel = z[y0:y1, x0:x1]
        out[y0:y1, x0:x1][sel] = dst[sel]
    return out


def _pixels_traits(gris, mask):
    """Pixels qui s'écartent du fond LOCAL : un dégradé n'est pas un trait.

    Les lettres sont bouchées avant la médiane : sinon, près d'un texte dense,
    elle tire vers la couleur des lettres et le fond voisin passe pour un trait.
    """
    ref = cv2.inpaint(gris, (mask > 0).astype(np.uint8), 3, cv2.INPAINT_TELEA)
    return np.abs(gris.astype(np.float32) - cv2.medianBlur(ref, 21).astype(np.float32)) > 40


def _droites(struct):
    """Droites distinctes (angle, distance) trouvées par Hough dans `struct`."""
    segs = cv2.HoughLinesP(struct.astype(np.uint8) * 255, 1, np.pi / 180, 12,
                           minLineLength=8, maxLineGap=3)
    droites = []
    for xa, ya, xb, yb in ([] if segs is None else segs.reshape(-1, 4).tolist()):
        th = np.arctan2(yb - ya, xb - xa) % np.pi
        rho = np.array([-np.sin(th), np.cos(th)]) @ np.array([xa, ya], float)
        if not any(min(abs(t - th), np.pi - abs(t - th)) < np.radians(4) and abs(r - rho) < 4
                   for t, r in droites):
            droites.append((th, rho))
    return droites


def m_structurel(image, mask):
    """Fond par plan robuste + prolongement des traits rectilignes qui entrent
    et ressortent de la zone. Restitue une flèche droite ; échoue sur les courbes."""
    out = image.copy()
    gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    for z in composantes(mask):
        ys, xs = np.nonzero(z)
        y0, y1 = max(ys.min() - MARGE, 0), min(ys.max() + MARGE + 1, image.shape[0])
        x0, x1 = max(xs.min() - MARGE, 0), min(xs.max() + MARGE + 1, image.shape[1])
        zc = z[y0:y1, x0:x1]
        connu = mask[y0:y1, x0:x1] == 0
        struct = _pixels_traits(gris[y0:y1, x0:x1], ~connu) & connu
        crop = image[y0:y1, x0:x1].astype(np.float32)
        sous = out[y0:y1, x0:x1]
        yz, xz = np.nonzero(zc)

        a = anneau(zc.astype(np.uint8) * 255, 6) & connu & ~struct
        ya, xa = np.nonzero(a)
        if len(ya) >= 10:
            A = np.c_[xa, ya, np.ones_like(xa)].astype(np.float32)
            B = np.c_[xz, yz, np.ones_like(xz)].astype(np.float32)
            for ch in range(3):
                coef, _ = _ajuster(A, crop[ya, xa, ch])
                sous[yz, xz, ch] = np.clip(B @ coef, 0, 255)

        sy, sx = np.nonzero(struct)
        P = np.c_[sx, sy].astype(float)
        Z = np.c_[xz, yz].astype(float)
        for th, rho in _droites(struct):
            proches = np.abs(P @ np.array([-np.sin(th), np.cos(th)]) - rho) < 3
            if proches.sum() < 8:
                continue
            # Hough arrondit la position : sur un trait épais, la bande de 3 px
            # peut manquer un bord. On réajuste sur une bande élargie autour de
            # la première droite, sinon le trait reconstruit est décalé d'un pixel.
            for _ in range(2):
                vx, vy, cx, cy = cv2.fitLine(P[proches].astype(np.float32), cv2.DIST_HUBER, 0, 0.01, 0.01).ravel()
                proches = np.abs((P - [cx, cy]) @ np.array([-vy, vx])) < 4
            u = np.array([vx, vy]); nrm = np.array([-vy, vx]); c0 = np.array([cx, cy])
            t_s = (P[proches] - c0) @ u
            t_z = (Z - c0) @ u
            # Le trait doit exister des DEUX côtés de la zone.
            if not ((t_s < t_z.min()).sum() >= 4 and (t_s > t_z.max()).sum() >= 4):
                continue
            epaisseur = max(1.0, 2 * np.percentile(np.abs((P[proches] - c0) @ nrm), 90) + 0.5)
            sel = (np.abs((Z - c0) @ nrm) <= epaisseur / 2) & (t_z >= t_s.min() - 1)
            sous[yz[sel], xz[sel]] = np.median(image[y0:y1, x0:x1][sy[proches], sx[proches]], axis=0)
    return out


METHODES = {
    "aplat": m_aplat, "plan": m_plan, "harmonique": m_harmonique,
    "telea": m_telea, "fsr": m_fsr, "structurel": m_structurel,
}


# ── Règle corrigée : repli rapide quand le fantôme n'est pas possible ────────

def _residu_poly(lab, ya, xa, degre):
    x = xa.astype(np.float32) / 100; y = ya.astype(np.float32) / 100
    cols = [np.ones_like(x), x, y] + ([x * x, y * y, x * y] if degre == 2 else [])
    A = np.stack(cols, 1)
    r = []
    for ch in range(3):
        v = lab[ya, xa, ch].astype(np.float32)
        r.append(np.std(_ajuster(A, v)[1]))
    return float(np.mean(r))


def traits_traversants(image, zone, mask):
    """Nombre de droites qui entrent ET ressortent de la zone."""
    ys, xs = np.nonzero(zone)
    y0, y1 = max(ys.min() - MARGE, 0), min(ys.max() + MARGE + 1, image.shape[0])
    x0, x1 = max(xs.min() - MARGE, 0), min(xs.max() + MARGE + 1, image.shape[1])
    gris = cv2.cvtColor(image[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    struct = _pixels_traits(gris, mask[y0:y1, x0:x1]) & (mask[y0:y1, x0:x1] == 0)
    # Un fond texturé produit des « traits » partout.
    if struct.mean() > 0.12:
        return 0
    yz, xz = np.nonzero(zone[y0:y1, x0:x1])
    sy, sx = np.nonzero(struct)
    P = np.c_[sx, sy].astype(float)
    Z = np.c_[xz, yz].astype(float)
    n = 0
    for th, rho in _droites(struct):
        nrm = np.array([-np.sin(th), np.cos(th)]); u = np.array([np.cos(th), np.sin(th)])
        proches = np.abs(P @ nrm - rho) < 3
        dz = np.abs(Z @ nrm - rho)
        if proches.sum() < 8 or not (dz < 2).any():
            continue
        t_s = P[proches] @ u; t_z = Z[dz < 2] @ u
        if (t_s < t_z.min()).sum() >= 4 and (t_s > t_z.max()).sum() >= 4:
            n += 1
    return n


def indicateurs(image, zone, mask):
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    a = anneau(zone.astype(np.uint8) * 255, 8, exclure=mask)
    ya, xa = np.nonzero(a)
    # Résidu SANS les pixels de traits : distingue un schéma sur fond calme
    # d'une texture où tout ressemble à des traits.
    y2, x2 = np.nonzero(a & ~_pixels_traits(gris, mask))
    return {
        "residu_hors_traits": _residu_poly(lab, y2, x2, 1) if len(y2) > 20 else 99.0,
        "residu_plan": _residu_poly(lab, ya, xa, 1) if len(ya) > 6 else 99.0,
        "residu_quad": _residu_poly(lab, ya, xa, 2) if len(ya) > 6 else 99.0,
        "texture": float(np.mean(cv2.Laplacian(gris, cv2.CV_32F)[a] ** 2)) if len(ya) else 0.0,
        "traits": traits_traversants(image, zone, mask),
    }


# Indicateur `texture` au-delà duquel le fond est chargé.
T_TEX = 300


def regle_corrigee(f, t_plan=2.0, t_quad=2.0, t_tex=T_TEX, t_calme=2.0):
    """Le résidu d'un modèle de fond (et non la variance brute) décide."""
    if f["traits"] > 0 and f["residu_hors_traits"] < t_calme:
        return "structurel"
    if f["residu_plan"] < t_plan:
        return "plan"
    if f["residu_quad"] < t_quad:
        return "harmonique"
    if f["texture"] > t_tex:
        return "fsr"
    return "harmonique"


# ── Masque fantôme ───────────────────────────────────────────────────────────

def _occupe(mask):
    return cv2.dilate(mask, np.ones((7, 7), np.uint8)) > 0


def positions_fantomes(zone, mask, n=4, occupe=None):
    """Décalages où la forme de la zone tombe entièrement sur du fond connu."""
    ys, xs = np.nonzero(zone)
    h = ys.max() - ys.min() + 1; w = xs.max() - xs.min() + 1
    H, W = mask.shape
    if occupe is None:
        occupe = _occupe(mask)
    candidats = [(0, -(h + 6)), (0, h + 6), (-(w + 6), 0), (w + 6, 0),
                 (0, -2 * (h + 6)), (0, 2 * (h + 6)), (-(w // 2 + 6), -(h + 6)), (w // 2 + 6, h + 6)]
    ok = []
    for dx, dy in candidats:
        y2, x2 = ys + dy, xs + dx
        if y2.min() < 2 or x2.min() < 2 or y2.max() >= H - 2 or x2.max() >= W - 2:
            continue
        if occupe[y2, x2].any():
            continue
        ok.append((dx, dy))
        if len(ok) == n:
            break
    return ok


def erreur_fantome(pre_efface, zone, methode, positions):
    """Erreur quadratique moyenne de `methode` sur les copies fantômes.

    `pre_efface` : image dont le vrai texte est déjà grossièrement retiré, pour
    qu'une lettre voisine ne soit pas prise pour du fond.
    """
    f = METHODES[methode]
    ys, xs = np.nonzero(zone)
    H, W = zone.shape
    m = 30
    errs = []
    for dx, dy in positions:
        y0, y1 = max(ys.min() + dy - m, 0), min(ys.max() + dy + m + 1, H)
        x0, x1 = max(xs.min() + dx - m, 0), min(xs.max() + dx + m + 1, W)
        crop = pre_efface[y0:y1, x0:x1]
        g = np.zeros(crop.shape[:2], np.uint8)
        g[ys + dy - y0, xs + dx - x0] = 255
        d = f(crop, g)[g > 0].astype(np.float32) - crop[g > 0].astype(np.float32)
        errs.append(np.mean(d ** 2))
    return float(np.mean(errs)) if errs else np.inf


def choisir_par_fantome(pre_efface, zone, mask, methodes=tuple(METHODES), occupe=None):
    pos = positions_fantomes(zone, mask, occupe=occupe)
    if not pos:
        return None
    erreurs = {m: erreur_fantome(pre_efface, zone, m, pos) for m in methodes}
    return min(erreurs, key=erreurs.get)


# ── Point d'entrée ───────────────────────────────────────────────────────────

def _recadrage(boite, marge):
    """Tranches de la boîte `(x, y, w, h)` élargie de `marge` (la zone y tient)."""
    x, y, w, h = boite
    return slice(max(y - marge, 0), y + h + marge), slice(max(x - marge, 0), x + w + marge)


def zones_par_boite(mask, boites, marge=3):
    """Pour chaque boîte : `(tranches, zone)`, la zone (pixels du masque propres à
    la boîte, vide si rien n'y a été trouvé) étant donnée dans le recadrage.

    Un masque pleine page par mot coûterait des centaines de Mo sur une page dense.
    """
    zones = []
    for boite in boites:
        x, y, w, h = boite
        sl = _recadrage(boite, MARGE + 8)
        r = mask[sl] > 0
        rect = np.zeros(r.shape, bool)
        y0, x0 = sl[0].start, sl[1].start
        rect[max(y - marge, 0) - y0:y + h + marge - y0, max(x - marge, 0) - x0:x + w + marge - x0] = True
        zones.append((sl, r & rect))
    return zones


def effacer(image, boites, budget_s=BUDGET_S, mask=None, limite_s=None):
    """Efface le texte des boîtes `(x, y, w, h)` de l'image BGR `uint8`.

    Renvoie `(image_effacee, choix)` : `choix[i]` est la méthode appliquée à la
    boîte i, suivie de « (règle) » si le fantôme n'a pas décidé, ou `None` si
    aucun pixel de lettre n'y a été trouvé. Passé `limite_s` (masque compris),
    les zones restantes sont remplies par Telea sans analyse (« (délai) ») : le
    temps reste borné.

    La règle, peu coûteuse, passe d'abord sur toutes les zones ; le fantôme,
    bien plus cher, n'affine ensuite que pendant `budget_s` (et avant `limite_s`). Un délai serré profite
    ainsi au plus de zones possible.
    """
    debut = time.perf_counter()
    if mask is None:
        mask = masque_couleur(image, boites)
    pre_efface = occupe = None
    zones = zones_par_boite(mask, boites)
    choix = []
    for sl, z in zones:
        if not z.any():
            choix.append(None)
        elif limite_s is not None and time.perf_counter() - debut >= limite_s:
            choix.append("telea (délai)")
        else:
            choix.append(regle_corrigee(indicateurs(image[sl], z, mask[sl])) + " (règle)")
    debut_fantome = time.perf_counter()
    for i, (sl, z) in enumerate(zones):
        # Un trait qui traverse la zone n'apparaît pas aux positions fantômes
        # (décalées hors de la zone) : seule la règle le voit, elle prime.
        if choix[i] in (None, "telea (délai)", "structurel (règle)"):
            continue
        maintenant = time.perf_counter()
        if (maintenant - debut_fantome >= budget_s
                or limite_s is not None and maintenant - debut >= limite_s):
            break
        if pre_efface is None:
            pre_efface, occupe = m_telea(image, mask), _occupe(mask)
        zone = np.zeros(mask.shape, bool)
        zone[sl] = z
        choix[i] = choisir_par_fantome(pre_efface, zone, mask, occupe=occupe) or choix[i]

    # Chaque zone est remplie sur un recadrage où tout le masque reste inconnu :
    # une zone voisine ne sert jamais de « fond connu ». Le coût suit la taille
    # des zones, pas celle de la page.
    # Les zones laissées au délai sont remplies d'une seule passe sur la page :
    # même résultat que zone par zone, sans refaire les recadrages qui se
    # chevauchent.
    out = image.copy()
    if pre_efface is None and "telea (délai)" in choix:
        pre_efface = m_telea(image, mask)
    for (sl, z), c in zip(zones, choix):
        if c is None:
            continue
        rempli = pre_efface[sl] if c == "telea (délai)" else METHODES[c.split()[0]](image[sl], mask[sl])
        out[sl][z] = rempli[z]
    return out, choix
