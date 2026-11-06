"""Détection : lire les mots d'une image et leurs boîtes (étude §4).

Le lecteur est derrière une interface, `Recognizer`, pour remplacer Tesseract
par PP-OCRv6 (étude §5.4) sans toucher à `ocr.py`. Tesseract reste le lecteur
par défaut et donne les mêmes résultats qu'avant cette interface.
"""
from __future__ import annotations

import csv
import io
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Protocol


class LectureEchouee(RuntimeError):
    """Le lecteur a planté ou dépassé son délai."""


@dataclass(frozen=True)
class Mot:
    texte: str
    boite: tuple[int, int, int, int]  # (x, y, w, h) en pixels
    conf: float  # 0-100
    ligne: tuple  # mots d'une même ligne : même clé


class Recognizer(Protocol):
    def manquant(self) -> str | None:
        """`None` si le lecteur est prêt, sinon `"programme"` ou `"langues"`."""

    def rotation(self, chemin: str) -> int:
        """Rotation (0, 90, 180, 270) qui remet l'image d'aplomb ; 0 si inconnue."""

    def lire(self, chemin: str, delai: float) -> list[Mot]:
        """Mots non vides de l'image, dans l'ordre de lecture."""


class Tesseract:
    def __init__(self, langues=("fra", "eng")):
        self.langues = langues

    @staticmethod
    def _run(args, timeout):
        try:
            return subprocess.run(args, capture_output=True, text=True,
                                  timeout=timeout, check=True,
                                  env={**os.environ, "OMP_THREAD_LIMIT": "1"})
        except (subprocess.SubprocessError, OSError) as exc:
            raise LectureEchouee(str(exc)) from exc

    def manquant(self):
        if not shutil.which("tesseract"):
            return "programme"
        try:
            installees = self._run(["tesseract", "--list-langs"], 5).stdout.splitlines()
        except LectureEchouee:
            return "programme"
        if not {*self.langues, "osd"}.issubset(set(installees)):
            return "langues"
        return None

    def rotation(self, chemin):
        # OSD détecte notamment les scans posés sur le côté. Un échec OSD sur
        # une page courte n'empêche pas la reconnaissance du texte horizontal.
        try:
            osd = self._run(["tesseract", chemin, "stdout", "--psm", "0"], 10)
        except LectureEchouee:
            return 0
        trouve = re.search(r"Rotate:\s*(90|180|270)\b", osd.stdout)
        return int(trouve[1]) if trouve else 0

    def lire(self, chemin, delai):
        result = self._run(["tesseract", chemin, "stdout", "-l", "+".join(self.langues),
                            "--psm", "3", "tsv"], delai)
        return [Mot(row["text"].strip(), tuple(int(row[k]) for k in ("left", "top", "width", "height")),
                    float(row["conf"]), tuple(row[k] for k in ("block_num", "par_num", "line_num")))
                # QUOTE_NONE : un « " » lu ne doit pas avaler les lignes suivantes.
                for row in csv.DictReader(io.StringIO(result.stdout), delimiter="\t", quoting=csv.QUOTE_NONE)
                if row.get("level") == "5" and (row.get("text") or "").strip()]


# Fiabilité d'un scan (étude OCR v2 §7.6) : une ligne douteuse reste en image,
# jamais traduite. Seuils fixés sur le livret « Code de la Route ».
SAUT_LIGNE = 2.5   # blanc (en hauteurs de mot) qui sépare deux colonnes
CONF_BOUT = 60     # mot rogné en bout de ligne sous ce score
CONF_MIETTE = 80   # miette de 1-2 signes rognée en bout sous ce score
CONF_LIGNE = 75    # moyenne exigée d'un fragment gardé
CONF_MOT = 50      # mot sous ce score : coupe la ligne, reste en image


def _recouvre(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return min(ax + aw, bx + bw) > max(ax, bx) and min(ay + ah, by + bh) > max(ay, by)


def completer(mots, autres):
    """Ajoute à `mots` ceux d'une seconde lecture (`autres`) qui ne recouvrent aucun mot déjà lu."""
    ajout = [Mot(m.texte, m.boite, m.conf, ("+",) + tuple(m.ligne))
             for m in autres if not any(_recouvre(m.boite, d.boite) for d in mots)]
    return list(mots) + ajout


def _douteux(m):
    """Bruit de bout de ligne : score bas, aucun signe, ou miette de 1-2 signes peu sûre."""
    signes = sum(c.isalnum() for c in m.texte)
    return m.conf < CONF_BOUT or not signes or (signes <= 2 and m.conf < CONF_MIETTE)


def lignes_fiables(mots):
    """Mots lus avec confiance : chaque ligne est coupée à ses grands blancs et
    à ses mots douteux ; seuls les fragments sûrs sont gardés.

    Retourne `(mots gardés, nombre de fragments écartés)`."""
    groupes = {}
    for m in mots:
        groupes.setdefault(m.ligne, []).append(m)
    lignes = []
    for cle, g in groupes.items():
        g = sorted(g, key=lambda m: m.boite[0])
        morceau = [g[0]]
        for a, b in zip(g, g[1:]):
            if b.boite[0] - (a.boite[0] + a.boite[2]) > SAUT_LIGNE * max(a.boite[3], b.boite[3]):
                lignes.append((cle, morceau))
                morceau = []
            morceau.append(b)
        lignes.append((cle, morceau))
    garde, ecartees = [], 0
    for k, (cle, ligne) in enumerate(lignes):
        # Un mot mal lu coupe la ligne : il reste en image et ses voisins sûrs
        # restent traduisibles. Un fragment ainsi isolé doit compter 2 mots.
        morceaux, courant = [], []
        for m in ligne:
            if m.conf < CONF_MOT:
                morceaux.append(courant)
                courant = []
            else:
                courant.append(m)
        morceaux.append(courant)
        coupee = len(morceaux) > 1
        for j, morceau in enumerate(morceaux):
            while morceau and _douteux(morceau[0]):
                morceau = morceau[1:]
            while morceau and _douteux(morceau[-1]):
                morceau = morceau[:-1]
            if not any(c.isalnum() for m in morceau for c in m.texte):
                continue
            if (sum(c.isalnum() for m in morceau for c in m.texte) < 2
                    or (coupee and len(morceau) < 2)
                    or sum(m.conf for m in morceau) / len(morceau) < CONF_LIGNE):
                ecartees += 1
                continue
            garde += [Mot(m.texte, m.boite, m.conf, tuple(cle) + (k, j)) for m in morceau]
    return garde, ecartees
