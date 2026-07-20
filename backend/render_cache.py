"""
Cache disque du RENDU complet d'une traduction.

Le modèle « on ne conserve pas le rendu, on le reconstruit à la demande »
était honnête mais aveugle au coût : mesuré sur un document de 285 pages,
280 s le rendu complet, ~12 s la moindre page seule. Chaque changement de page
de l'aperçu relançait 12 s de calcul, et le téléchargement d'un document déjà
traduit repayait les 280 s entières. Or le worker de traduction PRODUIT déjà
ce rendu complet — on le jetait (fichier transitoire, GC 30 min).

Ce module le conserve, sous une clé qui dit la vérité :

    <translation>.render.<ENGINE_VERSION>.pdf   à côté de pages.json

- **À côté de la traduction** : le magasin par empreinte gère déjà la vie et
  la purge de ce dossier — le rendu suit sa traduction, y compris à la
  suppression.
- **`ENGINE_VERSION` dans le NOM** : un correctif de moteur rend le fichier
  simplement introuvable, jamais resservi périmé. C'est la leçon chèrement
  apprise du cache précédent (cf. pdf_engine_v2/version.py) : la sortie ne
  dépend pas que de l'entrée, elle dépend du code qui la produit.
- **mtime(cache) >= mtime(traduction)** : une traduction complétée après coup
  (pages payées en plus) invalide le rendu sans qu'on y pense.

La reconstruction à la demande reste le REPLI : un cache absent dégrade en
lenteur, jamais en erreur.
"""
from __future__ import annotations

import logging
import os
import sys
import threading

# `pdf_engine_v2` vit à la RACINE du dépôt, pas dans backend/ — même détour
# que dans app.py (l.373), reproduit ici pour que le module s'importe aussi
# seul (tests, scripts).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
from pdf_engine_v2.version import ENGINE_VERSION

logger = logging.getLogger(__name__)


def cache_path_for(translation_path: str) -> str:
    return f"{translation_path}.render.{ENGINE_VERSION}.pdf"


def cache_valid(translation_path: str) -> str | None:
    """Chemin du rendu en cache s'il est utilisable, sinon None."""
    cp = cache_path_for(translation_path)
    try:
        if (os.path.isfile(cp)
                and os.path.getmtime(cp) >= os.path.getmtime(translation_path)):
            return cp
    except OSError:
        pass
    return None


def store_render(data: bytes, translation_path: str) -> None:
    """Écrit le rendu ATOMIQUEMENT — un lecteur ne voit jamais un demi-PDF."""
    cp = cache_path_for(translation_path)
    tmp = cp + ".tmp"
    try:
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, cp)
    except OSError as e:
        # Le cache est un confort : son échec se journalise, il n'interrompt
        # jamais la requête qui a déjà son résultat en main.
        logger.warning("Cache de rendu non écrit (%s) : %s", cp, e)
        try:
            os.remove(tmp)
        except OSError:
            pass


# ── Construction en arrière-plan ─────────────────────────────────────────────
#
# Pour les documents traduits AVANT ce cache (leur rendu de job a été jeté),
# la première visite paie encore la page seule (~12 s). On lance alors UNE
# construction complète en tâche de fond : quelques minutes plus tard, tout le
# document navigue et se télécharge instantanément.

_building: set[str] = set()
_building_lock = threading.Lock()


def ensure_background_build(original_path: str, translation_path: str,
                            ext: str, target_lang: str) -> None:
    """Construit le rendu complet dans un thread, une seule fois à la fois.

    Le garde-fou `_building` évite qu'une navigation rapide (une requête par
    page) empile dix constructions du même document de 285 pages.
    """
    cp = cache_path_for(translation_path)
    with _building_lock:
        if cp in _building:
            return
        _building.add(cp)

    def _run():
        try:
            # Import TARDIF et par attribut : `app` importe les routes qui
            # nous importent (cycle sinon), et les tests substituent
            # `app.render_translation_bytes` — passer par l'attribut au moment
            # de l'appel respecte leur substitution.
            import app as _app
            data = _app.render_translation_bytes(
                original_path, translation_path, ext, target_lang)
            store_render(data, translation_path)
            logger.info("Rendu complet mis en cache : %s", cp)
        except Exception as e:
            logger.warning("Construction du rendu en cache échouée (%s) : %s",
                           cp, e)
        finally:
            with _building_lock:
                _building.discard(cp)

    threading.Thread(target=_run, daemon=True,
                     name=f"render-cache-{os.path.basename(cp)}").start()
