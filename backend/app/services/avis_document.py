"""Messages de fin de traduction gardés avec le document.

Les avis (pages lues par OCR, objets laissés en langue d'origine, termes
harmonisés…) partaient une seule fois vers l'écran qui avait lancé la
traduction. Un utilisateur parti puis revenu par « Mes documents » ne les
voyait jamais (docs/etude-coherence-apercu.md, §8).

Ils sont rangés à côté de la traduction (`<traduction>.avis.json`), comme les
choix des pages scannées : ils disparaissent avec elle. On garde les DONNÉES,
pas la phrase : l'écran l'écrit dans la langue de l'interface.

Un avis par type : une reprise qui renvoie le même type remplace l'ancien au
lieu de l'empiler ; une passe qui n'a plus rien à signaler le retire. Au mieux : un fichier illisible ne signale rien et ne fait
jamais échouer une traduction ou la liste des documents.
"""
from __future__ import annotations

import json
import logging
import os
import threading

from app.services.progressive_preview import ecrire_atomiquement

logger = logging.getLogger(__name__)

TYPES = ("ocr", "objets", "coherence")

_verrou = threading.Lock()


def chemin(translation_path: str) -> str:
    return translation_path + ".avis.json"


def lire(translation_path: str | None) -> list[dict]:
    """Avis enregistrés, dans l'ordre où ils sont apparus."""
    if not translation_path:
        return []
    try:
        with open(chemin(translation_path), encoding="utf-8") as f:
            brut = json.load(f)
    except (OSError, ValueError):
        return []
    if not isinstance(brut, list):
        return []
    return [a for a in brut if isinstance(a, dict) and a.get("type") in TYPES]


def pour_document(avis: list[dict], statut: str, demarre: bool) -> list[dict]:
    """Messages à montrer pour un document dans cet état. Le fichier d'avis est
    partagé par tous les envois du même fichier : sans ce tri, un document
    encore en file affichait « Termes harmonisés… L'aperçu est à jour »,
    hérité d'une traduction précédente.

    - terminé : tous ; en erreur ou pas encore commencé : aucun ;
    - commencé mais pas fini (en cours, pause, annulé…) : pas d'harmonisation,
      qui n'a lieu qu'à la fin du traitement."""
    if statut == "done":
        return avis
    if statut == "error" or not demarre:
        return []
    return [a for a in avis if a.get("type") != "coherence"]


def ajouter(translation_path: str | None, type_: str, donnees: dict | None) -> None:
    """Enregistre l'avis `type_` ; `donnees` None le retire (plus rien à dire)."""
    if not translation_path or type_ not in TYPES:
        return
    try:
        with _verrou:
            avant = lire(translation_path)
            avis = [a for a in avant if a.get("type") != type_]
            if donnees is None and len(avis) == len(avant):
                return
            if donnees is not None:
                avis.append({"type": type_, **donnees})
            ecrire_atomiquement(chemin(translation_path),
                                json.dumps(avis, ensure_ascii=False).encode("utf-8"))
    except Exception as e:
        logger.warning("Avis %s non enregistré : %s", type_, e)


def retirer(translation_path: str | None, type_: str) -> None:
    ajouter(translation_path, type_, None)
