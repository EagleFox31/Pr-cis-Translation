"""Lecteur PP-OCRv6 small en ONNX (étude §4, phasage §11 étape 4).

Détecteur DBNet + reconnaissance CTC, un seul modèle pour le français,
l'anglais et le japonais. Pensé pour les fonds chargés (diapositives, photos,
schémas) où Tesseract ne trouve rien. Les poids (Apache-2.0, fiches
PaddlePaddle sur Hugging Face) sont téléchargés par
`scripts/telecharger_ppocr.py`, jamais versionnés.

Le modèle rend des lignes ; les mots sont découpés aux espaces à partir de la
position de chaque caractère dans la sortie CTC. Le japonais n'a pas
d'espaces : une ligne japonaise reste un seul `Mot`.
"""
from __future__ import annotations

import contextlib
import contextvars
import json
import math
import os
import threading
import time

import cv2
import numpy as np

from app.config import logger
from app.services import memoire

from .detect import LectureEchouee, Mot

DOSSIER = os.environ.get("PPOCR_DIR") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "models", "ppocr")
FICHIERS = ("det.onnx", "rec.onnx", "rec.yml")

# Réglages de `inference.yml` (DBPostProcess) et des défauts PaddleOCR 3.
SEUIL_PIXEL = 0.2
SEUIL_BOITE = 0.45
DILATATION = 1.4
COTE_MIN, COTE_MAX = 64, 4000
# Le modèle de détection consomme des Go sur une image de 4000 px (conteneur
# de 1 Go tué) : au-delà de TUILE px, l'image est analysée par morceaux qui se
# recouvrent de RECOUVREMENT px de chaque côté, et seuls leurs centres sont
# recollés. Multiples de 32, comme les côtés passés au modèle.
TUILE, RECOUVREMENT = 1024, 128
# Quand la mémoire manque, morceaux plus petits : même carte (seuls les centres
# sont gardés), mémoire divisée par 4 à 512 px, au prix de passes plus nombreuses.
TUILES_REDUITES = (768, 512)
# Mémoire demandée par une passe du modèle de détection : ~190 octets par point
# analysé (mesuré sous Docker : +225 Mo pour une tuile de 1024 × 1024), plus
# une marge.
OCTETS_PAR_POINT, MARGE_DETECTION = 220, 64 * 1024 * 1024
# Une seule détection à la fois sur tout le serveur (un seul processus,
# plusieurs fils) : deux grandes images en même temps dépassaient la mémoire.
# Si même les plus petits morceaux ne tiennent pas, la détection attend que la
# mémoire revienne (sans limite de durée : après memoire.ATTENTE_MAX_S, le journal le
# signale mais la détection ne part pas sans marge) : partir sans marge fait
# tuer le serveur et tous les travaux en cours.
ATTENTE_DETECTION_S = None
_VERROU_DETECTION = threading.Lock()
# Côté maximal pour l'image en cours de ce fil (taille affichée dans le
# document), posé par `plafond`. None : seul COTE_MAX s'applique.
_PLAFOND = contextvars.ContextVar("ppocr_plafond", default=None)


@contextlib.contextmanager
def plafond(cote):
    """Analyse au plus à `cote` px de côté les images lues dans ce bloc (None :
    aucun plafond de plus). Une image affichée petite dans un document n'a pas
    besoin d'être analysée en pleine définition."""
    jeton = _PLAFOND.set(cote)
    try:
        yield
    finally:
        _PLAFOND.reset(jeton)
HAUTEUR_REC = 48
LOT_REC = 8


def lire_dictionnaire(chemin):
    """Liste `character_dict` de `inference.yml` (scalaires nus, entre apostrophes ou guillemets)."""
    chars, dedans = [], False
    with open(chemin, encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.rstrip("\r\n")
            if not dedans:
                dedans = ligne.strip() == "character_dict:"
                continue
            item = ligne.lstrip(" ")
            if not item.startswith("- "):
                break
            c = item[2:]
            if len(c) >= 2 and c[0] == c[-1] == "'":
                c = c[1:-1].replace("''", "'")
            elif len(c) >= 2 and c[0] == c[-1] == '"':
                c = json.loads(c)  # échappements YAML entre guillemets, ceux de JSON
            chars.append(c)
    return chars


def _ordonner(pts):
    """Coins dans l'ordre haut-gauche, haut-droit, bas-droit, bas-gauche."""
    pts = pts[np.argsort(pts[:, 0])]
    g, d = pts[:2], pts[2:]
    hg, bg = g[np.argsort(g[:, 1])]
    hd, bd = d[np.argsort(d[:, 1])]
    return np.array([hg, hd, bd, bg], np.float32)


class PPOCR:
    def __init__(self, dossier=DOSSIER):
        self.dossier = dossier
        self._sessions = None
        self._rendre = None
        self._verrou = threading.Lock()

    def manquant(self):
        try:
            import onnxruntime  # noqa: F401
        except ImportError:
            return "programme"
        if not all(os.path.isfile(os.path.join(self.dossier, f)) for f in FICHIERS):
            return "programme"
        return None

    def rotation(self, chemin):
        # Pas de modèle d'orientation de page : les images de l'extension sont
        # d'aplomb ; les PDF scannés passent par Tesseract (OSD).
        return 0

    def _charger(self):
        with self._verrou:
            if self._sessions is None:
                import onnxruntime as ort
                opts = ort.SessionOptions()
                # Un seul fil, comme Tesseract (OMP_THREAD_LIMIT=1) : le serveur a 2 cœurs.
                opts.intra_op_num_threads = 1
                opts.inter_op_num_threads = 1
                # L'arène CPU d'onnxruntime garde pour toujours le pic d'une
                # inférence (des centaines de Mo sur une grande page) : sans
                # elle, la mémoire est rendue après chaque lecture.
                opts.enable_cpu_mem_arena = False
                det, rec = (ort.InferenceSession(os.path.join(self.dossier, f), opts,
                                                 providers=["CPUExecutionProvider"])
                            for f in FICHIERS[:2])
                self._chars = ["", *lire_dictionnaire(os.path.join(self.dossier, FICHIERS[2])), " "]
                self._sessions = (det, rec)
        return self._sessions

    # ── Détection ───────────────────────────────────────────────────────────
    def detecter_image(self, image):
        """Boîtes de texte d'une image BGR, sans lecture (analyse avant lancement)."""
        return self._detecter(self._charger()[0], image)

    def _detecter(self, det, image):
        h, w = image.shape[:2]
        r = max(1.0, COTE_MIN / min(h, w))
        cote_max = min(COTE_MAX, _PLAFOND.get() or COTE_MAX)
        if max(h, w) * r > cote_max:
            r = max(cote_max, COTE_MIN) / max(h, w)
        rh, rw = (max(32, int(round(v * r / 32)) * 32) for v in (h, w))
        carte = self._probabilites(det, cv2.resize(image, (rw, rh)), self._rendre)
        binaire = (carte > SEUIL_PIXEL).astype(np.uint8)
        contours, _ = cv2.findContours(binaire, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        sx, sy = w / rw, h / rh
        boites = []
        for c in contours[:3000]:
            if len(c) < 4:
                continue
            (cx, cy), (bw, bh), angle = cv2.minAreaRect(c)
            if min(bw, bh) < 3:
                continue
            # Score : probabilité moyenne dans le contour (mode « slow » de
            # DBPostProcess, plus juste que le rectangle sur les fonds chargés).
            x0, y0, cw, ch = cv2.boundingRect(c)
            masque = np.zeros((ch, cw), np.uint8)
            cv2.fillPoly(masque, [c.reshape(-1, 2) - (x0, y0)], 1)
            if cv2.mean(carte[y0:y0 + ch, x0:x0 + cw], masque)[0] < SEUIL_BOITE:
                continue
            # Le détecteur rend le cœur du texte : on l'élargit comme `unclip`
            # (décalage = aire × ratio / périmètre).
            marge = bw * bh * DILATATION / (2 * (bw + bh))
            bw, bh = bw + 2 * marge, bh + 2 * marge
            if min(bw, bh) < 5:
                continue
            pts = cv2.boxPoints(((cx, cy), (bw, bh), angle)) * (sx, sy)
            pts[:, 0] = pts[:, 0].clip(0, w - 1)
            pts[:, 1] = pts[:, 1].clip(0, h - 1)
            boites.append(_ordonner(pts))
        # Ordre de lecture : de haut en bas, puis de gauche à droite sur une même ligne.
        boites.sort(key=lambda b: (b[0, 1], b[0, 0]))
        for i in range(len(boites) - 1):
            for j in range(i, -1, -1):
                if abs(boites[j + 1][0, 1] - boites[j][0, 1]) < 10 and boites[j + 1][0, 0] < boites[j][0, 0]:
                    boites[j], boites[j + 1] = boites[j + 1], boites[j]
                else:
                    break
        return boites

    @staticmethod
    def _probabilites(det, image, options=None):
        """Carte de probabilité de texte d'une image BGR aux côtés multiples de 32.

        Recoller les cartes (et non les boîtes) garde d'un seul tenant une ligne
        à cheval sur deux tuiles. Une image qui tient dans une tuile est
        analysée d'un bloc, exactement comme avant.
        """
        rh, rw = image.shape[:2]

        def besoin(t):
            return min(rh, t) * min(rw, t) * OCTETS_PAR_POINT + MARGE_DETECTION

        def passe(morceau):
            x = morceau.astype(np.float32) / 255.0
            x = (x - (0.485, 0.456, 0.406)) / (0.229, 0.224, 0.225)
            x = x.transpose(2, 0, 1)[None].astype(np.float32)
            return det.run(None, {"x": x}, options)[0][0, 0]

        with _VERROU_DETECTION:
            # Plus grands morceaux qui tiennent dans la mémoire libre ; sinon
            # les plus petits, après attente (LibreOffice, rendus, autres
            # travaux libèrent de la place) plutôt que de faire tuer le serveur.
            tailles = (TUILE,) + tuple(t for t in TUILES_REDUITES if t < TUILE)
            libre = memoire.disponible()
            tuile = next((t for t in tailles if libre is None or besoin(t) <= libre), None)
            if tuile is None:
                tuile = tailles[-1]
                memoire.attendre(besoin(tuile), "détection d'image", max_s=ATTENTE_DETECTION_S,
                                 jusqu_a_marge=True)
            if tuile < TUILE:
                logger.info("Mémoire : détection en morceaux de %d px", tuile)
            if max(rh, rw) <= tuile:
                return passe(image)
            carte = np.empty((rh, rw), np.float32)
            pas = tuile - 2 * RECOUVREMENT
            for y in range(0, rh, pas):
                y0 = max(0, min(y - RECOUVREMENT, rh - tuile))
                y1, yc = min(rh, y0 + tuile), min(rh, y + pas)
                for x in range(0, rw, pas):
                    x0 = max(0, min(x - RECOUVREMENT, rw - tuile))
                    x1, xc = min(rw, x0 + tuile), min(rw, x + pas)
                    morceau = passe(image[y0:y1, x0:x1])
                    carte[y:yc, x:xc] = morceau[y - y0:yc - y0, x - x0:xc - x0]
            return carte

    # ── Reconnaissance ──────────────────────────────────────────────────────
    @staticmethod
    def _decouper(image, pts):
        """Redresse la ligne ; renvoie (vignette, coins source dans l'ordre de lecture)."""
        larg = int(max(np.linalg.norm(pts[0] - pts[1]), np.linalg.norm(pts[2] - pts[3])))
        haut = int(max(np.linalg.norm(pts[0] - pts[3]), np.linalg.norm(pts[1] - pts[2])))
        larg, haut = max(larg, 1), max(haut, 1)
        dst = np.array([[0, 0], [larg, 0], [larg, haut], [0, haut]], np.float32)
        vignette = cv2.warpPerspective(image, cv2.getPerspectiveTransform(pts, dst), (larg, haut),
                                       borderMode=cv2.BORDER_REPLICATE, flags=cv2.INTER_CUBIC)
        if haut >= 1.5 * larg:
            # Texte vertical (japonais en colonne) : lu de haut en bas. La
            # rotation anti-horaire amène le haut-droit en haut-gauche.
            vignette = np.ascontiguousarray(np.rot90(vignette))
            pts = np.array([pts[1], pts[2], pts[3], pts[0]], np.float32)
        return vignette, pts

    def _reconnaitre(self, rec, vignettes, fin):
        sorties = [None] * len(vignettes)
        ordre = sorted(range(len(vignettes)), key=lambda i: vignettes[i].shape[1] / vignettes[i].shape[0])
        for k in range(0, len(ordre), LOT_REC):
            if time.monotonic() > fin:
                raise LectureEchouee("délai de lecture dépassé")
            lot = ordre[k:k + LOT_REC]
            ratio = max(320 / HAUTEUR_REC, max(vignettes[i].shape[1] / vignettes[i].shape[0] for i in lot))
            largeur = int(math.ceil(HAUTEUR_REC * ratio))
            x = np.zeros((len(lot), 3, HAUTEUR_REC, largeur), np.float32)
            utiles = []
            for n, i in enumerate(lot):
                v = vignettes[i]
                lw = min(largeur, int(math.ceil(HAUTEUR_REC * v.shape[1] / v.shape[0])))
                r = cv2.resize(v, (lw, HAUTEUR_REC)).astype(np.float32) / 255.0
                x[n, :, :, :lw] = ((r - 0.5) / 0.5).transpose(2, 0, 1)
                utiles.append(lw)
            probas = rec.run(None, {"x": x})[0]
            for n, i in enumerate(lot):
                sorties[i] = (probas[n], largeur, utiles[n])
        return sorties

    def _mots(self, probas, largeur, utile, pts, ligne):
        """Découpe une ligne en mots aux espaces, avec leur boîte d'après la sortie CTC."""
        idx, conf = probas.argmax(1), probas.max(1)
        pas = largeur / len(idx)  # pixels de vignette par pas de temps
        chars = [(t, int(c), float(conf[t])) for t in range(len(idx))
                 if (c := idx[t]) != 0 and (t == 0 or idx[t - 1] != c)]
        groupes, courant = [], []
        for t, c, p in chars:
            if self._chars[c] == " ":
                if courant:
                    groupes.append(courant)
                courant = []
            else:
                courant.append((t, self._chars[c], p))
        if courant:
            groupes.append(courant)
        haut, bas = pts[0], pts[3]
        dx = (pts[1] - pts[0]) / max(1, utile)
        mots = []
        for g in groupes:
            # Bords à mi-chemin d'un pas de temps : un caractère occupe ~2 pas.
            u0 = max(0.0, (g[0][0] - 1) * pas)
            u1 = min(float(utile), (g[-1][0] + 2) * pas)
            coins = np.array([haut + u0 * dx, haut + u1 * dx, bas + u1 * dx, bas + u0 * dx])
            x0, y0 = np.floor(coins.min(0)).astype(int)
            x1, y1 = np.ceil(coins.max(0)).astype(int)
            mots.append(Mot("".join(c for _, c, _ in g), (int(x0), int(y0), int(x1 - x0), int(y1 - y0)),
                            100 * float(np.mean([p for _, _, p in g])), ligne))
        return mots

    def lire(self, chemin, delai):
        image = cv2.imread(chemin, cv2.IMREAD_COLOR)
        if image is None:
            raise LectureEchouee(f"image illisible : {chemin}")
        return self.lire_image(image, delai)

    def lire_image(self, image, delai):
        """Comme `lire`, sur une image BGR déjà décodée (sans passer par le disque)."""
        fin = time.monotonic() + delai
        try:
            det, rec = self._charger()
            boites = self._detecter(det, image)
            if time.monotonic() > fin:
                raise LectureEchouee("délai de lecture dépassé")
            decoupes = [self._decouper(image, b) for b in boites]
            sorties = self._reconnaitre(rec, [v for v, _ in decoupes], fin)
            mots = []
            for n, ((_, pts), (probas, largeur, utile)) in enumerate(zip(decoupes, sorties)):
                mots += self._mots(probas, largeur, utile, pts, (n,))
        except LectureEchouee:
            raise
        except Exception as exc:  # erreur ONNX Runtime, OpenCV, ou dictionnaire trop court
            raise LectureEchouee(str(exc)) from exc
        return [m for m in mots if m.texte.strip()]
