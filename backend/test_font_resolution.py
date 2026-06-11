# -*- coding: utf-8 -*-
"""Test rapide : normalisation + résolution de famille/graisse."""
from pdf_translator_engine import PDFTranslatorEngine

e = PDFTranslatorEngine()
for f in ("SegoeUI-Semilight", "SegoeUI-SemilightItalic", "SegoeUI-Semibold",
          "SegoeUI-Light", "SegoeUI-Black", "SegoeUI-Bold", "SegoeUI",
          "Calibri-Light", "Calibri", "Arial-BoldMT"):
    r = e._resolve_family_font(f)
    print(f"{f:<26} -> cle={e._norm_font(f):<10} resolu={r}")
