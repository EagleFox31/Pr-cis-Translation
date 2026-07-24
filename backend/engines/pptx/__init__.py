"""Moteur PPTX — OOXML PresentationML.

Le detail du contrat de balises de runs est dans `app/services/runtags.py` ;
la regeneration des apercus d'objets OLE Excel est dans `engine.py`.
"""
from .engine import PPTXTranslatorEngine

__all__ = ["PPTXTranslatorEngine"]
