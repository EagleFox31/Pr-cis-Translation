"""Banc de non-régression du rendu des images traduites (étude qualité images).

Rejoue des images réelles avec des lectures OCR et des traductions FIGÉES :
seul le rendu (regroupement, mise en page, effacement, pose) varie d'un essai à
l'autre. Chaque défaut signalé par un utilisateur entre ici comme cas.

Le corpus reste hors du dépôt (images de tiers) : `backend/translations/_banc_images`.

    python backend/tests/banc_images.py --figer --originaux DIR
        construit le corpus : pour chaque entrée du cache d'images, l'original
        (DIR/<sha10>.img), sa lecture OCR, et les traductions déjà obtenues.
    python backend/tests/banc_images.py              rejoue, planches + indicateurs
    python backend/tests/banc_images.py --reference  garde ces indicateurs comme référence
    python backend/tests/banc_images.py --live       traduit les textes absents de la mémoire

Indicateurs (plus bas = mieux, sauf occupation) :
  coupes    blocs dont une ligne coupe un mot latin en deux
  ecarts    rangées ou colonnes de blocs pareils posés à des corps différents (> 15 %)
  occup     occupation médiane de la place permise par le texte posé (%)
  restes    pixels d'encre source laissés juste au-dessus ou au-dessous d'une zone effacée
  manque    textes sans traduction en mémoire (rendu incomplet)
"""
import argparse
import hashlib
import io
import json
import os
import re
import sys

import racine  # noqa: F401
import cv2
import numpy as np
from PIL import Image

from app.services import cache_images
from app.services.ocr_v2 import image as img

BANC = os.path.join(os.path.dirname(cache_images.DOSSIER), "_banc_images")
LANGUE = "fr"
ECART_MAX = 1.15
SEUIL_ENCRE = 40
_LATIN = re.compile(r"[A-Za-zÀ-ÿ]")


class _SansLecteur:
    """Lecteur factice : les lectures sont figées, l'OCR ne tourne pas."""

    def manquant(self):
        return False


def _charger(chemin, defaut):
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return defaut


def _ecrire(chemin, donnees):
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(donnees, f, ensure_ascii=False, indent=1)


# ── Constitution du corpus ──────────────────────────────────────────────────

def figer(originaux):
    memoire = _charger(os.path.join(BANC, "memoire.json"), {})
    trad = memoire.setdefault(LANGUE, {})
    n = 0
    for dossier, _, fichiers in os.walk(cache_images.DOSSIER):
        for nom in sorted(fichiers):
            if not nom.endswith(f"-{LANGUE}-v{cache_images.VERSION}.json"):
                continue
            sha = nom.split("-")[0]
            source = os.path.join(originaux, sha[:10] + ".img")
            if not os.path.exists(source):
                print(f"original absent : {sha[:10]}")
                continue
            with open(source, "rb") as f:
                data = f.read()
            if hashlib.sha256(data).hexdigest() != sha:
                print(f"empreinte différente : {sha[:10]}")
                continue
            cas = os.path.join(BANC, "cas", sha[:10])
            os.makedirs(cas, exist_ok=True)
            with open(os.path.join(cas, "source.img"), "wb") as f:
                f.write(data)
            if not os.path.exists(os.path.join(cas, "lus.json")):
                lus = img.lire_image(data, delai_s=600)
                _ecrire(os.path.join(cas, "lus.json"), [[t, list(map(int, b))] for t, b in lus])
            for b in _charger(os.path.join(dossier, nom), {}).get("blocs", []):
                if b.get("traduction"):
                    trad.setdefault(b["texte"], b["traduction"])
            n += 1
    _ecrire(os.path.join(BANC, "memoire.json"), memoire)
    print(f"{n} cas figés, {len(trad)} traductions en mémoire.")


# ── Indicateurs ─────────────────────────────────────────────────────────────

def _coupe(b, p):
    """Une ligne posée contient un morceau de mot latin (mot coupé)."""
    if not _LATIN.search(b.traduction) or img._CJK.search(b.traduction):
        return False
    mots = set(b.traduction.split())
    return any(m not in mots for ligne in p["lignes"] for m in ligne.split())


def _ecarts(poses):
    """Groupes alignés (même rangée ou même colonne, hauteur lue proche) posés
    à des corps qui diffèrent de plus de ECART_MAX."""
    n = 0
    for axe in (1, 0):  # rangée (y), puis colonne (x)
        vus = set()
        for i, (bi, pi) in enumerate(poses):
            if i in vus:
                continue
            groupe = [i]
            for j in range(i + 1, len(poses)):
                bj = poses[j][0]
                hi, hj = bi.boite[3], bj.boite[3]
                if (abs(hi - hj) <= img.MEME_HAUTEUR * max(hi, hj)
                        and abs(bi.boite[axe] - bj.boite[axe]) <= 0.5 * min(hi, hj)):
                    groupe.append(j)
            vus.update(groupe)
            tailles = [poses[k][1]["taille"] for k in groupe]
            if len(groupe) > 1 and max(tailles) > ECART_MAX * min(tailles):
                n += 1
    return n


def _occupation(entrees):
    """Part de la place permise (cadre x hauteur libre) que couvre le texte posé."""
    r = []
    for b, p, cb, libre in entrees:
        haut = (libre[1] - libre[0]) if libre else b.boite[3]
        place = max(cb[1] - cb[0], 1) * max(haut, 1)
        r.append(min(p["larg"] * p["haut"] / place, 1.0))
    return 100 * float(np.median(r)) if r else 0.0


def _restes(avant, apres, poses):
    """Encre source inchangée juste au-dessus et au-dessous des zones effacées,
    hors du texte posé : hauts et bas de glyphes oubliés par l'effacement."""
    H = avant.shape[0]
    pose = np.zeros(avant.shape[:2], bool)
    for _, p in poses:
        y0, y1 = int(p["y"]), int(np.ceil(p["y"] + p["haut"])) + 2
        pose[max(y0, 0):y1, max(int(p["x"]), 0):int(np.ceil(p["x"] + p["larg"]))] = True
    n = 0
    for b, _ in poses:
        for lx, ly, lw, lh in b.lignes:
            ex, ey, ew, eh = img._elargie((lx, ly, lw, lh), avant)
            d = max(int(0.5 * lh), 2)
            for r0, r1 in ((max(ey - d, 0), ey), (ey + eh, min(ey + eh + d, H))):
                if r1 <= r0:
                    continue
                bande_av = avant[r0:r1, ex:ex + ew].astype(np.int16)
                bande_ap = apres[r0:r1, ex:ex + ew].astype(np.int16)
                fond = np.median(bande_av.reshape(-1, 3), axis=0)
                encre = np.abs(bande_av - fond).max(axis=2) > SEUIL_ENCRE
                inchange = np.abs(bande_av - bande_ap).max(axis=2) <= 12
                reste = (encre & inchange & ~pose[r0:r1, ex:ex + ew]).astype(np.uint8)
                # Morceaux de glyphe seulement : un bord de cadre ou un trait
                # (plus long qu'une ligne de texte n'est haute) est un graphisme.
                k, _, stats, _ = cv2.connectedComponentsWithStats(reste, connectivity=8)
                n += int(sum(s[cv2.CC_STAT_AREA] for s in stats[1:k]
                             if s[cv2.CC_STAT_WIDTH] < lh and s[cv2.CC_STAT_AREA] >= 3))
    return n


# ── Rejeu ───────────────────────────────────────────────────────────────────

def rejouer(live=False):
    memoire = _charger(os.path.join(BANC, "memoire.json"), {})
    trad = memoire.setdefault(LANGUE, {})
    manque = []

    def traduire(textes):
        absents = [t for t in textes if t not in trad and any(c.isalpha() for c in t)]
        if absents and live:
            from app.services import extension as ext
            for t, tr in zip(absents, ext.traduire_textes(absents, LANGUE)):
                trad[t] = tr
        manque.extend(t for t in textes if t not in trad)
        return [trad.get(t, "") for t in textes]

    espion = {}
    freres = img._freres

    def _freres(places, W, teintes):
        espion["entrees"] = list(places)
        espion["poses"] = out = freres(places, W, teintes)
        return out

    img._freres = _freres
    sorties = os.path.join(BANC, "sorties")
    os.makedirs(sorties, exist_ok=True)
    resultats = {}
    cas_dir = os.path.join(BANC, "cas")
    for cas in sorted(os.listdir(cas_dir)):
        with open(os.path.join(cas_dir, cas, "source.img"), "rb") as f:
            data = f.read()
        lus = [(t, tuple(b)) for t, b in _charger(os.path.join(cas_dir, cas, "lus.json"), [])]
        espion.clear()
        n_manque = len(manque)
        rendu = img.traduire_image(data, traduire, lecteur=_SansLecteur(), delai_s=600, lus=lus,
                                langue=LANGUE)
        poses, entrees = espion.get("poses", []), espion.get("entrees", [])
        avant = cv2.cvtColor(np.asarray(Image.open(io.BytesIO(data)).convert("RGB")), cv2.COLOR_RGB2BGR)
        apres = cv2.cvtColor(np.asarray(Image.open(io.BytesIO(rendu.data)).convert("RGB")), cv2.COLOR_RGB2BGR)
        resultats[cas] = {
            "blocs": len(rendu.blocs),
            "poses": len(poses),
            "coupes": sum(_coupe(b, p) for b, p in poses),
            "ecarts": _ecarts(poses),
            "occup": round(_occupation(entrees), 1),
            "restes": _restes(avant, apres, poses),
            "manque": len(manque) - n_manque,
        }
        planche = np.hstack([avant, apres])
        echelle = min(1.0, 2400 / planche.shape[1])
        planche = cv2.resize(planche, None, fx=echelle, fy=echelle, interpolation=cv2.INTER_AREA)
        cv2.imwrite(os.path.join(sorties, cas + ".jpg"), planche, [cv2.IMWRITE_JPEG_QUALITY, 85])
    img._freres = freres
    if live:
        _ecrire(os.path.join(BANC, "memoire.json"), memoire)
    return resultats


def _total(res):
    t = {k: sum(r[k] for r in res.values()) for k in ("poses", "coupes", "ecarts", "restes", "manque")}
    t["occup"] = round(float(np.median([r["occup"] for r in res.values()])), 1) if res else 0.0
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--figer", action="store_true")
    ap.add_argument("--originaux")
    ap.add_argument("--reference", action="store_true")
    ap.add_argument("--live", action="store_true")
    a = ap.parse_args()
    if a.figer:
        if not a.originaux:
            ap.error("--figer exige --originaux")
        figer(a.originaux)
        return 0
    res = rejouer(a.live)
    ref = _charger(os.path.join(BANC, "reference.json"), {})
    cols = ("poses", "coupes", "ecarts", "occup", "restes", "manque")
    print(f"{'cas':<11}" + "".join(f"{c:>9}" for c in cols))
    for cas, r in res.items():
        print(f"{cas:<11}" + "".join(f"{r[c]:>9}" for c in cols))
    tot = _total(res)
    print(f"{'TOTAL':<11}" + "".join(f"{tot[c]:>9}" for c in cols))
    if ref:
        rt = _total(ref)
        print(f"{'référence':<11}" + "".join(f"{rt[c]:>9}" for c in cols))
    if a.reference:
        _ecrire(os.path.join(BANC, "reference.json"), res)
        print("référence enregistrée.")
    print(f"planches : {os.path.join(BANC, 'sorties')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
