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
                for row in csv.DictReader(io.StringIO(result.stdout), delimiter="\t")
                if row.get("level") == "5" and (row.get("text") or "").strip()]
