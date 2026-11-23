"""Banc d'effacement avec vérité terrain (OCR v2, étude §8).

Chaque cas est fabriqué deux fois, sans texte (vérité) et avec texte ; on
efface avec `effacer`, on compare au vrai fond. 12 cas x 4 variantes = 108
zones. Images générées à l'exécution (textures comprises), aucun fichier sous
droits. Repris de `cas.py` / `mesures.py` du banc fourni, sans scikit-image.

    backend/venv/Scripts/python.exe backend/tests/banc_effacement.py
    ... --sans-ajuster   moindres carrés en une passe (comparaison)
"""
import os
import sys
import time

import racine  # noqa: F401
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.services.ocr_v2 import erase
from app.services.ocr_v2.erase import METHODES, effacer
from app.services.ocr_v2.mask import masque_couleur

FONTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")
W, H = 480, 320
VARIANTES = [(0, 0), (10, -8), (-12, 10), (16, 6)]
PLAFOND_DB = 50.0

# Seuils (étude §8).
PERTE_MAX_DB = 1.5
FOND_SIMPLE_MIN_DB = 40.0


def _police(taille, gras=True):
    return ImageFont.truetype(os.path.join(FONTS, "montserrat-Bold.ttf" if gras else "montserrat-Regular.ttf"), taille)


# ── Fonds (BGR float32) ──────────────────────────────────────────────────────

def _plein(c):
    return np.ones((H, W, 3), np.float32) * np.array(c, np.float32)


def fond_degrade_lineaire(rng):
    x = np.linspace(0, 1, W)[None, :, None]
    y = np.linspace(0, 1, H)[:, None, None]
    t = 0.6 * x + 0.4 * y
    return np.array([230, 120, 40], np.float32) * (1 - t) + np.array([60, 200, 250], np.float32) * t


def fond_degrade_radial(rng):
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.clip(np.sqrt((xx - W * 0.35) ** 2 + (yy - H * 0.4) ** 2) / 260, 0, 1)[..., None]
    return np.array([250, 250, 255], np.float32) * (1 - d) + np.array([120, 40, 90], np.float32) * d


def _taches(rng, sigma, amplitude):
    t = cv2.GaussianBlur(rng.normal(0, 1, (H, W)).astype(np.float32), (0, 0), sigma)
    return t / (np.abs(t).max() + 1e-6) * amplitude


def fond_papier(rng):
    grain = rng.normal(0, 4, (H, W)).astype(np.float32)
    return _plein((228, 238, 242)) + (_taches(rng, 25, 10) + grain)[..., None]


def fond_brique(rng):
    # Rangées décalées d'une demi-brique, joints clairs, teinte et grain par brique.
    f = _plein((175, 190, 215))
    hb, lb, joint = 22, 56, 3
    for r, y in enumerate(range(0, H, hb)):
        for x in range(-(r % 2) * lb // 2, W, lb):
            teinte = np.array([60, 80, 150], np.float32) * rng.uniform(0.8, 1.15)
            f[y + joint:y + hb, max(x + joint, 0):max(x + lb, 0)] = teinte
    return f + rng.normal(0, 9, (H, W, 1)).astype(np.float32)


def fond_herbe(rng):
    # Brins : bruit étiré verticalement, sur un vert irrégulier.
    brins = cv2.GaussianBlur(rng.normal(0, 1, (H, W)).astype(np.float32), (0, 0), sigmaX=1.0, sigmaY=6.0)
    brins = brins / (np.abs(brins).max() + 1e-6)
    g = 0.55 + 0.35 * brins + _taches(rng, 30, 0.12)
    return np.stack([g * 60, g * 170, g * 80], -1)


def fond_photo(rng):
    # Scène floue à plusieurs échelles (taches de couleur + détails fins).
    f = np.zeros((H, W, 3), np.float32)
    for sigma, amp in ((40, 70), (12, 30), (3, 12)):
        f += np.stack([_taches(rng, sigma, amp) for _ in range(3)], -1)
    return f + np.array([70, 100, 140], np.float32)


def fond_quadrillage(rng):
    f = _plein((235, 250, 250))
    f[:, ::12] = (200, 215, 160)
    f[::12, :] = (200, 215, 160)
    return f


FONDS = {
    "uni": lambda r: _plein((245, 225, 200)), "degrade_lin": fond_degrade_lineaire,
    "degrade_radial": fond_degrade_radial, "papier_scan": fond_papier, "brique": fond_brique,
    "herbe": fond_herbe, "photo": fond_photo, "quadrillage": fond_quadrillage,
    "sombre": lambda r: _plein((80, 45, 30)),
    "schema_fleche": lambda r: _plein((255, 255, 255)), "schema_boite": lambda r: _plein((255, 255, 255)),
    "tableau": lambda r: _plein((255, 255, 255)),
}

# (texte, x, y, taille, couleur BGR)
ETIQUETTES = {
    "uni":            [("Pressure valve", 40, 60, 22, (40, 40, 40)), ("Inlet", 300, 200, 26, (40, 40, 40))],
    "degrade_lin":    [("Flow rate", 50, 70, 26, (255, 255, 255)), ("Output stage", 230, 220, 24, (20, 20, 20))],
    "degrade_radial": [("Core temperature", 60, 100, 24, (30, 30, 30)), ("Cooling", 280, 230, 24, (250, 250, 250))],
    "papier_scan":    [("The pump must be checked", 30, 50, 18, (35, 35, 35)),
                       ("before each start-up and", 30, 78, 18, (35, 35, 35)),
                       ("after maintenance work.", 30, 106, 18, (35, 35, 35))],
    "brique":         [("Main entrance", 70, 90, 30, (255, 255, 255)), ("Exit", 300, 220, 34, (255, 255, 255))],
    "herbe":          [("North field", 60, 80, 30, (255, 255, 255)), ("Zone B", 290, 210, 32, (20, 20, 20))],
    "photo":          [("Fresh coffee", 120, 40, 32, (255, 255, 255)), ("Hot", 60, 230, 30, (255, 255, 255))],
    "quadrillage":    [("Load curve", 60, 70, 24, (150, 40, 20)), ("Sample 3", 280, 200, 24, (150, 40, 20))],
    "sombre":         [("Warning", 60, 70, 34, (255, 255, 255)), ("High voltage", 210, 200, 28, (200, 230, 255))],
    "schema_fleche":  [("Signal input", 150, 108, 22, (30, 30, 30)), ("Feedback loop", 170, 228, 22, (30, 30, 30))],
    "schema_boite":   [("Controller", 60, 52, 24, (255, 255, 255)), ("Sensor", 304, 128, 24, (30, 30, 30))],
    "tableau":        [("Voltage", 22, 22, 20, (20, 20, 20)), ("Current", 182, 22, 20, (20, 20, 20)),
                       ("12 V max", 22, 92, 20, (20, 20, 20)), ("Nominal", 342, 92, 20, (20, 20, 20))],
}
NOMS = list(ETIQUETTES)


def _dessiner_traits(nom, fond):
    """Dessine les traits du schéma dans le fond ; renvoie leur masque."""
    traits = np.zeros((H, W), np.uint8)
    noir = (40, 40, 40)

    def ligne(p1, p2, ep):
        cv2.line(fond, p1, p2, noir, ep, cv2.LINE_AA)
        cv2.line(traits, p1, p2, 255, ep, cv2.LINE_AA)

    if nom == "schema_fleche":
        ligne((20, 120), (440, 120), 2)  # flèche droite sous « Signal input »
        pointe = np.array([[440, 112], [460, 120], [440, 128]])
        cv2.fillPoly(fond, [pointe], noir, cv2.LINE_AA)
        cv2.fillPoly(traits, [pointe], 255, cv2.LINE_AA)
        ligne((60, 120), (60, 240), 2)
        ligne((60, 240), (420, 240), 2)
        ligne((420, 240), (420, 120), 2)
        ligne((240, 40), (240, 290), 1)  # trait vertical fin qui croise les deux
    elif nom == "schema_boite":
        cv2.rectangle(fond, (40, 40), (220, 90), (150, 90, 30), -1)
        for p1, p2 in (((40, 40), (220, 40)), ((40, 90), (220, 90)), ((40, 40), (40, 90)), ((220, 40), (220, 90))):
            ligne(p1, p2, 2)
        cv2.circle(fond, (345, 205), 60, noir, 2, cv2.LINE_AA)
        cv2.circle(traits, (345, 205), 60, 255, 2, cv2.LINE_AA)
        ligne((130, 90), (300, 170), 2)
    elif nom == "tableau":
        for x in (10, 170, 330, 470):
            ligne((x, 10), (x, 160), 1)
        for y in (10, 60, 75, 125, 160):
            ligne((10, y), (470, y), 1)
    return traits


def generer(nom, graine=0, decalage=(0, 0)):
    rng = np.random.default_rng(graine)
    fond = np.ascontiguousarray(FONDS[nom](rng).astype(np.float32))
    traits = _dessiner_traits(nom, fond)
    image, boites = fond.copy(), []
    lettres = np.zeros((H, W), bool)
    dx, dy = decalage
    for texte, x, y, taille, col in ETIQUETTES[nom]:
        c = Image.new("L", (W, H), 0)
        ImageDraw.Draw(c).text((x + dx, y + dy), texte, font=_police(taille, not nom.startswith("papier")), fill=255)
        a = np.asarray(c, np.float32)[..., None] / 255.0
        image = image * (1 - a) + np.array(col, np.float32) * a
        ys, xs = np.nonzero(a[..., 0])
        lettres |= a[..., 0] > 0
        x0, y0 = max(xs.min() - 4, 0), max(ys.min() - 4, 0)
        boites.append((int(x0), int(y0), int(min(xs.max() + 4, W - 1) - x0 + 1), int(min(ys.max() + 4, H - 1) - y0 + 1)))
    bruit = rng.normal(0, 2.0, (H, W, 1)).astype(np.float32)  # même bruit sur l'image et la vérité
    return {"nom": nom, "fond": np.clip(fond + bruit, 0, 255).astype(np.uint8),
            "image": np.clip(image + bruit, 0, 255).astype(np.uint8),
            "boites": boites, "traits": traits > 127, "lettres": lettres}


# ── Mesures ──────────────────────────────────────────────────────────────────

def rect(boite, pad=2):
    x, y, w, h = boite
    z = np.zeros((H, W), bool)
    z[max(y - pad, 0):y + h + pad, max(x - pad, 0):x + w + pad] = True
    return z


def psnr_zone(res, fond, zone):
    mse = np.mean((res[zone].astype(np.float64) - fond[zone].astype(np.float64)) ** 2)
    return min(PLAFOND_DB, 99.0 if mse < 1e-9 else 10 * np.log10(255 ** 2 / mse))


def ssim(a, b):
    """SSIM moyen (fenêtre gaussienne 1,5, constantes usuelles), canaux moyennés."""
    a, b = a.astype(np.float64), b.astype(np.float64)
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    flou = lambda m: cv2.GaussianBlur(m, (7, 7), 1.5)  # noqa: E731
    ma, mb = flou(a), flou(b)
    va, vb, cab = flou(a * a) - ma ** 2, flou(b * b) - mb ** 2, flou(a * b) - ma * mb
    s = ((2 * ma * mb + c1) * (2 * cab + c2)) / ((ma ** 2 + mb ** 2 + c1) * (va + vb + c2))
    return float(s.mean())


def traits_conserves(res, fond, traits, zone):
    t = traits & zone
    if not t.any():
        return None
    return float(np.mean(np.abs(res[t].astype(int) - fond[t].astype(int)).max(1) < 60))


# ── Banc ─────────────────────────────────────────────────────────────────────

def mesurer():
    """Une ligne par zone : PSNR du choix, de chaque méthode (oracle), SSIM, traits."""
    lignes = []
    for nom in NOMS:
        for v, dec in enumerate(VARIANTES):
            cas = generer(nom, graine=100 + v, decalage=dec)
            img, fond = cas["image"], cas["fond"]
            mask = masque_couleur(img, cas["boites"])
            t = time.perf_counter()
            out, choix = effacer(img, cas["boites"], mask=mask)
            duree = time.perf_counter() - t
            par_methode = {m: f(img, mask) for m, f in METHODES.items()}
            for b, (boite, c) in enumerate(zip(cas["boites"], choix)):
                z = rect(boite)
                sl = (slice(max(boite[1] - 2, 0), boite[1] + boite[3] + 2),
                      slice(max(boite[0] - 2, 0), boite[0] + boite[2] + 2))
                lignes.append(dict(
                    cas=nom, variante=v, boite=b, choix=c, duree=duree / len(choix),
                    psnr=psnr_zone(out, fond, z), avant=psnr_zone(img, fond, z),
                    oracle=max(psnr_zone(r, fond, z) for r in par_methode.values()),
                    ssim=ssim(out[sl], fond[sl]), traits=traits_conserves(out, fond, cas["traits"], z)))
    return lignes


def main():
    if "--sans-ajuster" in sys.argv:
        def une_passe(A, v):
            coef, *_ = np.linalg.lstsq(A, v, rcond=None)
            return coef, v - A @ coef
        erase._ajuster = une_passe

    debut = time.monotonic()
    lignes = mesurer()
    print(f"{'cas':<15}{'dB':>6}{'oracle':>8}{'perte':>7}{'SSIM':>6}{'traits':>8}  choix")
    for nom in NOMS:
        ls = [l for l in lignes if l["cas"] == nom]
        tr = [l["traits"] for l in ls if l["traits"] is not None]
        choix = sorted({str(l["choix"]).split()[0] for l in ls})
        print(f"{nom:<15}{np.mean([l['psnr'] for l in ls]):6.1f}{np.mean([l['oracle'] for l in ls]):8.1f}"
              f"{np.mean([l['oracle'] - l['psnr'] for l in ls]):7.2f}{np.mean([l['ssim'] for l in ls]):6.3f}"
              f"{(f'{100 * np.mean(tr):.0f} %' if tr else '-'):>8}  {', '.join(choix)}")
    perte = float(np.mean([l["oracle"] - l["psnr"] for l in lignes]))
    print(f"{len(lignes)} zones, perte moyenne {perte:.2f} dB, "
          f"{np.mean([l['duree'] for l in lignes]):.2f} s/zone, {time.monotonic() - debut:.0f} s")

    echecs = []
    if len(lignes) != 108:
        echecs.append(f"{len(lignes)} zones au lieu de 108")
    if perte > PERTE_MAX_DB:
        echecs.append(f"perte {perte:.2f} dB > {PERTE_MAX_DB}")
    for nom in ("uni", "sombre", "degrade_lin", "degrade_radial"):
        db = np.mean([l["psnr"] for l in lignes if l["cas"] == nom])
        if db < FOND_SIMPLE_MIN_DB:
            echecs.append(f"{nom} {db:.1f} dB < {FOND_SIMPLE_MIN_DB}")
    fleche = [l["traits"] for l in lignes if l["cas"] == "schema_fleche" and l["boite"] == 0]
    if min(fleche) < 1.0:
        echecs.append(f"flèche droite conservée à {100 * min(fleche):.1f} %")
    print("ÉCHEC : " + " ; ".join(echecs) if echecs else "OK banc d'effacement")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
