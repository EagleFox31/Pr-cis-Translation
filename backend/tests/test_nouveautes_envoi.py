"""E-mail « Nouveautés » : gabarit, désabonnement un clic, envoi sans doublon.

CE QUI EST VÉRIFIÉ
  1. GABARIT     — FR et EN : sujet, élément, date, bouton vers
                   /fonctionnalites ; une section vide n'apparaît pas.
  2. DÉSABONNEMENT — lien visible vers la page (jeton signé), en-têtes
                   `List-Unsubscribe` (API) et `List-Unsubscribe-Post`.
  3. ÉCHAPPEMENT — un titre contenant du HTML n'en injecte pas.
  4. SÉLECTION   — --depuis / --entrees ; id inconnu refusé.
  5. ENVOI       — seuls les abonnés vérifiés, dans leur langue ; une RELANCE
                   N'ENVOIE RIEN ; un échec SMTP n'enregistre pas l'envoi
                   (repris à la relance).

Base PostgreSQL requise (DATABASE_URL, port 5433 en local).

    backend/venv/Scripts/python.exe backend/tests/test_nouveautes_envoi.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from email.header import decode_header, make_header

import racine  # noqa: F401  -- met backend/ sur le chemin

os.environ.setdefault("SMTP_FROM", "bonjour@example.com")

from sqlalchemy import delete, select                    # noqa: E402
from sqlalchemy.ext.asyncio import (                     # noqa: E402
    AsyncSession, async_sessionmaker, create_async_engine,
)
from sqlalchemy.pool import NullPool                     # noqa: E402

from app.core.database import DATABASE_URL               # noqa: E402
from app.core.email import (EmailIndisponible, FRONTEND_URL,  # noqa: E402
                            _message_nouveautes)
from app.models import NouveauteEnvoi, User              # noqa: E402
from app.services.envoi_nouveautes import envoyer_version, selection  # noqa: E402
from app.services.nouveautes import jeton_desabonnement, verifier_jeton  # noqa: E402

_eng = create_async_engine(DATABASE_URL, poolclass=NullPool)
session = async_sessionmaker(_eng, class_=AsyncSession, expire_on_commit=False)


def _partie(msg, sous_type):
    for p in msg.walk():
        if p.get_content_maintype() == "text" and p.get_content_subtype() == sous_type:
            return p.get_payload(decode=True).decode("utf-8")
    return ""


async def run():
    checks = []

    def ok(nom, cond, detail=""):
        checks.append((nom, bool(cond), detail))

    # 1-3. GABARIT
    jeton = jeton_desabonnement("u123")
    cas = (("fr", "Ce qui change dans Précis", "Correctifs", "9 novembre 2026"),
           ("en", "What's new in Précis", "Fixes", "November 9, 2026"))
    for lang, sujet, section, date in cas:
        elems = selection(lang, entrees=["excel-traduit-en-entier"])
        msg = _message_nouveautes("a@example.com", lang, elems, version="1.7.0",
                                  date_version="2026-11-09", jeton=jeton)
        html, texte = _partie(msg, "html"), _partie(msg, "plain")
        sujet_lu = str(make_header(decode_header(msg["Subject"])))
        ok(f"GABARIT {lang} sujet", sujet_lu.startswith(sujet) and "1.7.0" in sujet_lu, sujet_lu)
        ok(f"GABARIT {lang} élément", elems[0]["titre"] in html and elems[0]["titre"] in texte)
        ok(f"GABARIT {lang} section vide omise", section not in html)
        ok(f"GABARIT {lang} bouton", f"{FRONTEND_URL}/fonctionnalites" in html)
        ok(f"GABARIT {lang} date", date in html)
        ok(f"DESAB   {lang} lien page", f"/desabonnement?jeton={jeton}" in html
           and f"/desabonnement?jeton={jeton}" in texte)
    ok("DESAB   List-Unsubscribe", msg["List-Unsubscribe"] ==
       f"<{FRONTEND_URL}/api/nouveautes/desabonnement?jeton={jeton}>", msg["List-Unsubscribe"])
    ok("DESAB   List-Unsubscribe-Post",
       msg["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click")
    ok("DESAB   jeton valide", verifier_jeton(jeton) == "u123")
    ok("STRUCT  related > alternative", msg.get_content_subtype() == "related"
       and msg.get_payload()[0].get_content_subtype() == "alternative")

    piege = [{"type": "nouveaute", "titre": "<script>x</script>", "resume": "a & b"}]
    html = _partie(_message_nouveautes("a@example.com", "fr", piege, version="1",
                                       date_version="2026-11-09", jeton=jeton), "html")
    ok("ECHAPPE HTML neutralisé", "<script>" not in html and "&lt;script&gt;" in html)

    # 4. SÉLECTION
    ok("SELECT  depuis", all(e["date"] > "2026-10-01"
                             for e in selection("fr", depuis="2026-10-01")))
    try:
        selection("fr", entrees=["n-existe-pas"])
        ok("SELECT  id inconnu refusé", False)
    except ValueError:
        ok("SELECT  id inconnu refusé", True)

    # 5. ENVOI — version factice : n'interfère avec aucun envoi réel.
    version = f"t-{uuid.uuid4().hex[:8]}"

    def compte(**kw):
        return User(email=f"env-{uuid.uuid4().hex[:8]}@example.com", **kw)

    comptes = {
        "abonne": compte(email_verified=True, abonne_nouveautes=True, langue="en"),
        "panne": compte(email_verified=True, abonne_nouveautes=True),
        "non_abonne": compte(email_verified=True),
        "non_verifie": compte(abonne_nouveautes=True),
    }
    async with session() as db:
        db.add_all(comptes.values())
        await db.commit()
    nos = {u.email: k for k, u in comptes.items()}
    ids = [u.id for u in comptes.values()]
    recus, panne = [], {"active": True}

    async def faux(email, langue, elements, **kw):
        if email not in nos:
            return                              # autres comptes de la base d'essai
        if nos[email] == "panne" and panne["active"]:
            raise EmailIndisponible("refus SMTP simulé")
        recus.append((nos[email], langue))

    async def lancer():
        await envoyer_version(session, depuis="2026-01-01", version=version,
                              envoyer=faux, journal=lambda _: None, pause=0)

    try:
        try:
            await lancer()
            ok("ENVOI   échec SMTP remonte", False)
        except EmailIndisponible:
            ok("ENVOI   échec SMTP remonte", True)
        panne["active"] = False
        await lancer()
        qui = sorted(r[0] for r in recus)
        ok("ENVOI   abonnés vérifiés seuls, panne reprise", qui == ["abonne", "panne"], recus)
        ok("ENVOI   langue du compte", ("abonne", "en") in recus, recus)
        avant = len(recus)
        await lancer()
        ok("ENVOI   relance : personne ne le reçoit deux fois", len(recus) == avant, recus)
        async with session() as db:
            n = len((await db.execute(select(NouveauteEnvoi.id).where(
                NouveauteEnvoi.version == version,
                NouveauteEnvoi.user_id.in_(ids)))).all())
        ok("ENVOI   journal : 2 envois", n == 2, n)
    finally:
        async with session() as db:
            await db.execute(delete(NouveauteEnvoi).where(NouveauteEnvoi.version == version))
            await db.execute(delete(User).where(User.id.in_(ids)))
            await db.commit()
        await _eng.dispose()

    print()
    for nom, cond, detail in checks:
        print(f"  {'OK  ' if cond else 'ECHEC'}  {nom}"
              + (f"   [{detail}]" if not cond and detail else ""))
    reussis = sum(1 for _, c, _ in checks if c)
    print(f"\n  {reussis}/{len(checks)}\n")
    return reussis == len(checks)


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(run()) else 1)
