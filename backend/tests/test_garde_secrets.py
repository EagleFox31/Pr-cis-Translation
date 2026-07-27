"""Le garde-fou de production : aucun secret public ne doit pouvoir démarrer.

LE DÉFAUT VERROUILLÉ ICI
------------------------
Tous les secrets avaient une valeur par défaut et l'application démarrait avec
elles sans un mot. Trois sont PUBLIQUES — elles figurent dans `.env.example`,
donc dans le dépôt, donc dans tout clone :

  • `JWT_SECRET`        → quiconque lit le dépôt forge un jeton d'accès admin ;
  • `FRONTEND_API_KEY`  → n'importe quelle page déclenche nos conversions ;
  • `DATABASE_URL`      → base `postgres:postgres`, sans mot de passe propre.

CE QUI EST MESURÉ (et pourquoi de cette façon)
----------------------------------------------
1. ACCORD `.env.example` ↔ garde. Ce n'est pas la valeur du gabarit qui est
   testée — la tester des deux côtés serait aveugle — mais le fait que TOUT
   gabarit publié dans `.env.example` soit refusé par le garde. Changer le
   gabarit sans mettre le garde à jour fait échouer cette suite, au lieu de
   laisser passer un secret connu de tous.

2. ACCORD entre modules : le secret que le garde inspecte est bien l'objet que
   `core/security.py` utilise pour SIGNER. Deux lectures `os.getenv` séparées
   se seraient tues.

3. Le comportement de bout en bout, dans de VRAIS processus fils avec un
   environnement distinct — parce que `config` lit l'environnement à l'import,
   et qu'un rechargement de module en cours de test ne prouverait pas ce que
   fait un démarrage réel.

    backend/venv/Scripts/python.exe backend/tests/test_garde_secrets.py
"""
from __future__ import annotations

import os
import subprocess
import sys

import racine  # noqa: F401  -- met backend/ sur le chemin

from app import config                                        # noqa: E402

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_checks: list[tuple[bool, str]] = []


def check(cond: bool, label: str, detail: str = "") -> None:
    _checks.append((bool(cond), label))
    marque = "OK  " if cond else "ÉCHEC"
    print(f"  {marque} {label}" + (f"   [{detail}]" if detail and not cond else ""))


# ── Un montage d'application dans un processus neuf ──────────────────────────

_MONTAGE = (
    "import os, sys;"
    "sys.path.insert(0, r'%s');"
    "from app import create_app;"
    "create_app();"
    "print('DEMARRE')" % BACKEND
)


def monter(**env: str) -> tuple[int, str]:
    """Monte l'application dans un processus fils. Rend (code, sortie).

    L'environnement du fils est reconstruit à partir de zéro pour les clés qui
    nous intéressent : `load_dotenv` n'écrase jamais une variable déjà posée,
    donc ce que l'on pose ici gagne sur le `backend/.env` de la machine.
    """
    e = dict(os.environ)
    e["PRECIS_NO_BANNER"] = "1"
    e.update(env)
    p = subprocess.run([sys.executable, "-c", _MONTAGE], env=e,
                       capture_output=True, text=True, timeout=180)
    return p.returncode, (p.stdout + p.stderr)


# Un jeu de secrets SOLIDES : rien d'un gabarit, longueur suffisante.
SOLIDES = {
    "JWT_SECRET": "K7f2Qm9xTz4Rb1Nv8Lw3Yd6Hs0Pj5Ac2Ge7Uk4Mn1Vr8Xt3Zq6Bw9",
    "FRONTEND_API_KEY": "cle_frontend_reelle_9f2b71ac4e",
    "DATABASE_URL": "postgresql+asyncpg://precis:m0tDeP4sseReel@localhost:5432/precis",
    "DEEPSEEK_API_KEY": "sk-4f9b2c7e1a8d3506b9f2e4c7a1d8b503",
    "EMAIL_ENABLED": "false",
}
PUBLIC = "https://precis-translator.com"
LOCAL = "http://localhost:5173"


def main() -> int:
    # ── 1. Accord : les gabarits de `.env.example` sont TOUS refusés ─────────
    print("\n1. Accord entre .env.example et le garde")
    exemple = {}
    with open(os.path.join(BACKEND, ".env.example"), encoding="utf-8") as fh:
        for ligne in fh:
            ligne = ligne.strip()
            if not ligne or ligne.startswith("#") or "=" not in ligne:
                continue
            cle, _, val = ligne.partition("=")
            exemple[cle.strip()] = val.strip()

    for cle in ("JWT_SECRET", "FRONTEND_API_KEY", "DATABASE_URL",
                "DEEPSEEK_API_KEY"):
        val = exemple.get(cle)
        check(val is not None, f"{cle} est bien documentée dans .env.example")
        if val is not None:
            check(config._est_gabarit(val),
                  f"le gabarit publié pour {cle} est REFUSÉ par le garde", val)

    # ── 2. Accord entre modules : le garde inspecte le secret qui signe ──────
    print("\n2. Le secret contrôlé est celui qui signe")
    from app.core import security
    check(security.JWT_SECRET is config.JWT_SECRET,
          "core/security.py signe avec le JWT_SECRET de config (même objet)")
    check(security.ACCESS_TOKEN_EXPIRY_MINUTES == config.JWT_EXPIRY_MINUTES,
          "l'expiration vient aussi de config")
    from app.core import database
    check(database.DATABASE_URL is config.DATABASE_URL,
          "core/database.py se connecte à l'URL de config (même objet)")

    # ── 3. Un secret solide n'est jamais pris pour un gabarit ───────────────
    print("\n3. Un vrai secret passe")
    check(not config._est_gabarit(SOLIDES["JWT_SECRET"]),
          "un secret aléatoire de 52 caractères est accepté")
    check(config._est_gabarit(""), "une valeur VIDE est refusée (secret absent)")
    check(config._est_gabarit("x" * 60 + "_here"),
          "un marqueur de gabarit est vu même noyé dans une longue valeur")

    # ── 4. Détection de production : le signal qu'on ne peut pas oublier ────
    print("\n4. Démarrage réel, dans des processus distincts")

    code, sortie = monter(ALLOWED_ORIGINS=PUBLIC, PRECIS_ENV="",
                          JWT_SECRET=config.DEFAUT_JWT_SECRET,
                          FRONTEND_API_KEY=config.DEFAUT_FRONTEND_API_KEY,
                          DATABASE_URL=config.DEFAUT_DATABASE_URL,
                          DEEPSEEK_API_KEY="your_deepseek_api_key_here")
    check(code != 0 and "Configuration de production refusée" in sortie,
          "origine PUBLIQUE + secrets par défaut  ->  REFUS de démarrer",
          sortie[-400:])
    check("JWT_SECRET" in sortie and "FRONTEND_API_KEY" in sortie,
          "le refus NOMME chaque réglage fautif")

    code, sortie = monter(ALLOWED_ORIGINS=PUBLIC, PRECIS_ENV="", **SOLIDES)
    check(code == 0 and "DEMARRE" in sortie,
          "origine PUBLIQUE + secrets solides  ->  démarre", sortie[-400:])

    code, sortie = monter(ALLOWED_ORIGINS=LOCAL, PRECIS_ENV="production",
                          **SOLIDES)
    check(code == 0 and "DEMARRE" in sortie,
          "PRECIS_ENV=production + secrets solides  ->  démarre", sortie[-400:])

    code, sortie = monter(ALLOWED_ORIGINS=LOCAL, PRECIS_ENV="production",
                          JWT_SECRET="trop-court", **{
                              k: v for k, v in SOLIDES.items()
                              if k != "JWT_SECRET"})
    check(code != 0 and "caractères" in sortie,
          "PRECIS_ENV=production + JWT_SECRET trop court  ->  REFUS",
          sortie[-400:])

    code, sortie = monter(ALLOWED_ORIGINS=LOCAL, PRECIS_ENV="",
                          JWT_SECRET=config.DEFAUT_JWT_SECRET,
                          FRONTEND_API_KEY=config.DEFAUT_FRONTEND_API_KEY,
                          DATABASE_URL=config.DEFAUT_DATABASE_URL,
                          DEEPSEEK_API_KEY="your_deepseek_api_key_here")
    check(code == 0 and "DEMARRE" in sortie,
          "développement local + secrets par défaut  ->  démarre (avertit seulement)",
          sortie[-400:])

    # ── Verdict ─────────────────────────────────────────────────────────────
    passed = sum(1 for ok, _ in _checks if ok)
    total = len(_checks)
    print(f"\n{passed}/{total} contrôles")
    if passed != total:
        print("ÉCHECS :", [lbl for ok, lbl in _checks if not ok])
        return 1
    print("OK — aucun secret public ne peut atteindre la production")
    return 0


if __name__ == "__main__":
    sys.exit(main())
