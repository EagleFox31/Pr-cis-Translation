"""Nouveautés : ce qu'un compte n'a pas encore vu, et le jeton de désabonnement.

RÈGLE D'AFFICHAGE (`a_voir`)
    * jamais rien vu (`nouveautes_vues_le` nul) → mode « accueil » : les phares ;
    * sinon → mode « depuis » : les éléments datés APRÈS le jour de la
      dernière consultation ;
    * rien à montrer → mode nul et liste vide : le site n'affiche RIEN
      (ni fenêtre, ni pastille).

JETON DE DÉSABONNEMENT
    Signé HMAC-SHA256 avec `JWT_SECRET` et un préfixe d'usage propre (un jeton
    de ce type ne vaut pour rien d'autre). Il ne contient que l'id du compte :
    sans date d'expiration, le lien d'un vieil e-mail marche toujours, comme
    l'exige un désabonnement en un clic.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime

from app.config import JWT_SECRET
from app.content import nouveautes as catalogue

_USAGE = b"nouveautes-desabonnement:"


def langue_de(valeur: str | None, defaut: str = "fr") -> str:
    """« en-US,en;q=0.9 » → « en » ; toute langue non gérée → `defaut`."""
    code = (valeur or "").split(",")[0].split("-")[0].strip().lower()
    return code if code in catalogue.LANGUES else defaut


def a_voir(vues_le: datetime | None, lang: str, admin: bool = False) -> dict:
    if vues_le is None:
        elements = catalogue.phares(lang)
        mode = "accueil"
    else:
        jour = vues_le.date().isoformat()
        elements = [e for e in catalogue.elements(lang, admin=admin) if e["date"] > jour]
        mode = "depuis"
    if not elements:
        return {"mode": None, "depuis": None, "elements": []}
    return {"mode": mode,
            "depuis": vues_le.isoformat() if vues_le else None,
            "elements": elements}


def _signature(user_id: str) -> str:
    brut = hmac.new(JWT_SECRET.encode(), _USAGE + user_id.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(brut).decode().rstrip("=")


def jeton_desabonnement(user_id: str) -> str:
    return f"{user_id}.{_signature(user_id)}"


def verifier_jeton(jeton: str | None) -> str | None:
    """Id du compte si le jeton est authentique, sinon None."""
    user_id, _, signature = (jeton or "").partition(".")
    if not user_id or not signature:
        return None
    return user_id if hmac.compare_digest(signature, _signature(user_id)) else None
