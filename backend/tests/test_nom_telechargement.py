"""Téléchargement : tout nom de fichier doit produire un en-tête HTTP valide.

Un en-tête est encodé en latin-1 ; « Rapport — final.pdf » (tiret long), un
nom arabe ou chinois faisaient échouer le téléchargement (500).

Exécution :  backend/.venv/Scripts/python.exe backend/tests/test_nom_telechargement.py
"""
from __future__ import annotations
from urllib.parse import unquote

import racine  # noqa: F401  -- met backend/ sur le chemin

from app.api.documents import _piece_jointe  # noqa: E402

NOMS = [
    "Rapport annuel 2026 — version finale_TRADUIT.pdf",
    "تقرير_TRADUIT.docx",
    "报告_TRADUIT.pptx",
    'Devis "urgent" \\ client.xlsx',
    "Présentation été.pdf",
    "simple.pdf",
]

echecs = 0
for nom in NOMS:
    entete = _piece_jointe(nom)
    try:
        entete.encode("latin-1")
        ascii_ok = entete.isascii()
        exact = unquote(entete.split("filename*=UTF-8''", 1)[1]) == nom
        repli = entete.split('filename="', 1)[1].split('"', 1)[0]
        ok = ascii_ok and exact and repli and '"' not in repli
    except Exception as exc:  # noqa: BLE001
        ok, entete = False, f"{entete!r} ({exc})"
    print(("OK   " if ok else "ÉCHEC"), nom)
    echecs += not ok

print(f"\n{len(NOMS) - echecs}/{len(NOMS)} réussis")
raise SystemExit(1 if echecs else 0)
