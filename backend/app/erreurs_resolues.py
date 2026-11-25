"""Erreurs du journal CORRIGÉES par une version livrée.

Quand une PR corrige une erreur vue dans `/admin/logs`, elle ajoute ici une
entrée. Au démarrage suivant — c'est-à-dire au déploiement qui embarque le
correctif — les occurrences en attente qui correspondent passent à `handled` :
l'admin n'a plus à trier à la main ce que le code a déjà réglé, et la purge
(`services/error_log_menage`) les efface une fois leur délai écoulé.

Seules les occurrences ANTÉRIEURES au démarrage sont touchées. Si l'erreur
revient avec la nouvelle version, l'occurrence neuve reste `new` : la rechute
se voit, au lieu d'être masquée par la déclaration.

Champs :
  source      `frontend`, `backend`, `api` ou une source métier (`deepseek_solde`…)
  motif       expression régulière cherchée (re.search) dans le message
  corrige_en  version du projet qui livre le correctif (backend/version.py)
  note        pourquoi c'est réglé, en une ligne
"""
from __future__ import annotations

ERREURS_RESOLUES: list[dict[str, str]] = [
    {
        "source": "frontend",
        "motif": r"^ResizeObserver loop",
        "corrige_en": "1.2.0",
        "note": "avertissement bénin du navigateur, filtré à la source "
                "(frontend/src/lib/errorReporting.ts, BENIGN)",
    },
]
