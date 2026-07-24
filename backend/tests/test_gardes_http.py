"""Les gardes du contrat HTTP : origines autorisées et plafonds de débit.

DEUX DÉFAUTS QUE CETTE SUITE VERROUILLE
---------------------------------------
1. CORS — `allow_origins=["*"]` avec `allow_credentials=True` faisait renvoyer
   à Starlette l'origine de l'appelant, QUELLE QU'ELLE SOIT, accompagnée de
   `Access-Control-Allow-Credentials: true`. La clé d'API étant publique (elle
   voyage dans le bundle), n'importe quelle page pouvait déclencher nos
   conversions LibreOffice — des secondes de CPU chacune.

2. DÉBIT — seule `/health` portait un plafond. Les routes qui ENVOIENT un
   e-mail n'en avaient aucun : notre compte SMTP expédiait autant de messages
   qu'on le lui demandait, vers n'importe quelle adresse. C'est du spam à notre
   nom, et une mise en liste noire du domaine.

`EMAIL_ENABLED=false` est posé AVANT de construire l'application : sans cela,
cette suite enverrait de vrais e-mails. C'est arrivé pendant sa mise au point.

    backend/venv/Scripts/python.exe backend/tests/test_gardes_http.py
"""
from __future__ import annotations

import os
import sys
import uuid

import racine  # noqa: F401  -- met backend/ sur le chemin

# AVANT tout import applicatif : `email.py` lit la variable au chargement.
os.environ["EMAIL_ENABLED"] = "false"

from fastapi.testclient import TestClient                    # noqa: E402

from app import create_app                                   # noqa: E402
from app.config import ALLOWED_ORIGINS                       # noqa: E402


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    def ok(nom, cond, detail=""):
        checks.append((nom, bool(cond), detail))

    # Contexte UNIQUE : hors `with`, chaque requête ouvre puis ferme sa propre
    # boucle et le pool de connexions garde des sockets morts.
    with TestClient(create_app()) as client:

        # ── 1. CORS ──────────────────────────────────────────────────────
        connue = ALLOWED_ORIGINS[0]
        r = client.get("/health", headers={"Origin": connue})
        ok("CORS  une origine déclarée est autorisée",
           r.headers.get("access-control-allow-origin") == connue,
           f"{connue} -> {r.headers.get('access-control-allow-origin')!r}")

        for etrangere in ("https://un-site-malveillant.example",
                          "http://localhost:9999",
                          "null"):
            r = client.get("/health", headers={"Origin": etrangere})
            ok(f"CORS  « {etrangere} » est REFUSÉE",
               r.headers.get("access-control-allow-origin") is None,
               repr(r.headers.get("access-control-allow-origin")))

        # Le préflight doit refuser aussi : c'est LUI que le navigateur
        # interroge avant un POST, et l'autoriser suffirait à ouvrir la porte.
        r = client.options("/api/auth/login", headers={
            "Origin": "https://un-site-malveillant.example",
            "Access-Control-Request-Method": "POST"})
        ok("CORS  le préflight d'une origine étrangère est refusé",
           r.headers.get("access-control-allow-origin") is None,
           repr(r.headers.get("access-control-allow-origin")))

        # ── 2. Plafond de débit ──────────────────────────────────────────
        # `/health` : 10/minute, et aucune base n'est touchée.
        codes = [client.get("/health").status_code for _ in range(14)]
        ok("DÉBIT  /health finit par refuser (429)", 429 in codes,
           f"{codes.count(200)} acceptés, {codes.count(429)} refusés")
        ok("DÉBIT  les premiers appels passent (le plafond n'est pas 0)",
           codes[0] == 200, str(codes[:3]))

        # Une route d'ENVOI D'E-MAIL. L'adresse n'existe pas : la route répond
        # sans rien envoyer, mais le plafond, lui, s'applique quand même —
        # c'est justement ce qui protège contre l'énumération de comptes.
        adresse = f"plafond-{uuid.uuid4().hex[:8]}@exemple.com"
        codes = [client.post("/api/auth/resend-verification",
                             json={"email": adresse}).status_code
                 for _ in range(7)]
        ok("DÉBIT  une route d'envoi d'e-mail est plafonnée (3/minute)",
           429 in codes, str(codes))
        ok("DÉBIT  le refus arrive APRÈS quelques appels, pas au premier",
           codes[0] != 429, str(codes[:2]))

    print()
    n_ok = sum(1 for _, c, _ in checks if c)
    for nom, cond, detail in checks:
        ligne = ("  OK  " if cond else " FAIL ") + f"  {nom}"
        if not cond and detail:
            ligne += f"   [{detail}]"
        print(ligne)
    print(f"\n{n_ok}/{len(checks)}")
    return 0 if n_ok == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
