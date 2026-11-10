"""Connexion de l'extension par le site : code à usage unique + PKCE (S256).

CE QUI EST VÉRIFIÉ, par les vraies routes (TestClient) :
  1. FLUX      — code demandé avec la session du site, échangé contre une
                 session « extension » ; le code n'est gardé qu'en empreinte.
  2. USAGE UNIQUE — un code déjà échangé est refusé (400).
  3. PKCE      — un mauvais verifier est refusé ET consomme le code.
  4. ÉCHÉANCE  — un code périmé est refusé (400), même message que les autres.
  5. FORMAT    — challenge / verifier mal formés : 400 ; sans session : 401 ;
                 e-mail non vérifié : 403.
  6. SORTIES   — la déconnexion de l'extension ne ferme pas le site, et
                 inversement ; la rotation du jeton garde son client.

Base PostgreSQL requise (DATABASE_URL), migration 0023 appliquée.

    backend/venv/Scripts/python.exe backend/tests/test_extension_auth.py
"""
from __future__ import annotations

import asyncio
import hashlib
import sys
import uuid
from datetime import datetime, timedelta, timezone

import racine  # noqa: F401  -- met backend/ sur le chemin

from fastapi.testclient import TestClient                # noqa: E402
from sqlalchemy import delete, select                    # noqa: E402
from sqlalchemy.ext.asyncio import (                     # noqa: E402
    AsyncSession, async_sessionmaker, create_async_engine,
)
from sqlalchemy.pool import NullPool                     # noqa: E402

from app import create_app                               # noqa: E402
from app.core.database import DATABASE_URL               # noqa: E402
from app.core.security import (create_access_token, create_refresh_token,  # noqa: E402
                               revoke_user_tokens)
from app.models import ExtensionAuthCode, RefreshToken, User  # noqa: E402
from app.rate_limit import limiter                       # noqa: E402

_eng = create_async_engine(DATABASE_URL, poolclass=NullPool)
async_session = async_sessionmaker(_eng, class_=AsyncSession, expire_on_commit=False)

# Vecteur de l'annexe B de la RFC 7636.
VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
CHALLENGE = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
AUTRE_VERIFIER = "x" * 43


async def _compte(verifie=True) -> User:
    u = User(email=f"extauth-{uuid.uuid4().hex[:10]}@example.com", email_verified=verifie)
    async with async_session() as db:
        db.add(u)
        await db.commit()
    return u


async def _jeton_site(uid: str) -> str:
    async with async_session() as db:
        return await create_refresh_token(db, uid)


async def _clients(uid: str) -> list[str]:
    async with async_session() as db:
        return sorted((await db.scalars(select(RefreshToken.client).where(
            RefreshToken.user_id == uid))).all())


async def _codes(uid: str) -> int:
    async with async_session() as db:
        return len((await db.scalars(select(ExtensionAuthCode.id).where(
            ExtensionAuthCode.user_id == uid))).all())


async def _code_perime(uid: str, code: str):
    async with async_session() as db:
        db.add(ExtensionAuthCode(
            code_hash=hashlib.sha256(code.encode()).hexdigest(), user_id=uid,
            code_challenge=CHALLENGE,
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=5)))
        await db.commit()


async def _nettoyer(uids):
    async with async_session() as db:
        await db.execute(delete(User).where(User.id.in_(uids)))
        await db.commit()


def _entete(u: User) -> dict:
    return {"Authorization": "Bearer " + create_access_token(u.id, u.email)}


async def run():
    checks: list[tuple[str, bool, str]] = []

    def ok(nom, cond, detail=""):
        checks.append((nom, bool(cond), detail))

    u = await _compte()
    non_verifie = await _compte(verifie=False)
    uids = [u.id, non_verifie.id]
    try:
        with TestClient(create_app()) as client:
            def post(chemin, corps, headers=None):
                if limiter:
                    limiter.reset()
                return client.post(f"/api/extension/auth/{chemin}", json=corps,
                                   headers=headers or {})

            def echange(code, verifier=VERIFIER):
                return post("token", {"code": code, "code_verifier": verifier})

            # 5. Accès et formats
            r = post("code", {"code_challenge": CHALLENGE})
            ok("ACCÈS   sans session → 401", r.status_code == 401, r.status_code)
            r = post("code", {"code_challenge": CHALLENGE}, _entete(non_verifie))
            ok("ACCÈS   e-mail non vérifié → 403", r.status_code == 403, r.status_code)
            for mauvais in ("court", CHALLENGE + "A", CHALLENGE[:-1] + "=", CHALLENGE[:-1] + "+"):
                r = post("code", {"code_challenge": mauvais}, _entete(u))
                ok(f"FORMAT  challenge {mauvais[:8]}… → 400", r.status_code == 400, r.status_code)
            ok("FORMAT  aucun code créé par les refus", await _codes(u.id) == 0)

            # 1. Flux complet
            r = post("code", {"code_challenge": CHALLENGE}, _entete(u))
            ok("FLUX    code délivré", r.status_code == 200 and r.json().get("expires_in") == 60
               and len(r.json().get("code", "")) >= 43, r.text)
            code = r.json()["code"]
            async with async_session() as db:
                ligne = (await db.scalars(select(ExtensionAuthCode).where(
                    ExtensionAuthCode.user_id == u.id))).one()
            ok("FLUX    seule l'empreinte est gardée",
               ligne.code_hash == hashlib.sha256(code.encode()).hexdigest()
               and code not in (ligne.code_hash, ligne.code_challenge))
            r = echange(code)
            corps = r.json() if r.status_code == 200 else {}
            ok("FLUX    échange → session complète",
               r.status_code == 200 and corps.get("access_token") and corps.get("refresh_token")
               and corps.get("user", {}).get("email") == u.email, r.text)
            ok("FLUX    jeton marqué « extension »", await _clients(u.id) == ["extension"],
               await _clients(u.id))
            ok("FLUX    code consommé", await _codes(u.id) == 0)
            jeton_ext = corps.get("refresh_token", "")
            acces = {"Authorization": "Bearer " + corps.get("access_token", "")}
            r = client.get("/api/auth/me", headers=acces)
            ok("FLUX    le jeton d'accès sert", r.status_code == 200, r.status_code)

            # 2. Usage unique
            r = echange(code)
            ok("UNIQUE  code déjà échangé → 400", r.status_code == 400
               and r.json()["detail"] == "Code invalide ou expiré.", r.text)

            # 3. Mauvais verifier : refusé et code consommé
            code2 = post("code", {"code_challenge": CHALLENGE}, _entete(u)).json()["code"]
            r = echange(code2, AUTRE_VERIFIER)
            ok("PKCE    mauvais verifier → 400", r.status_code == 400
               and r.json()["detail"] == "Code invalide ou expiré.", r.text)
            ok("PKCE    code consommé malgré l'échec", await _codes(u.id) == 0)
            r = echange(code2)
            ok("PKCE    le bon verifier ne le ressuscite pas", r.status_code == 400, r.status_code)
            code3 = post("code", {"code_challenge": CHALLENGE}, _entete(u)).json()["code"]
            for mauvais in ("trop-court", "é" * 50, "a" * 129):
                r = echange(code3, mauvais)
                ok(f"PKCE    verifier mal formé ({len(mauvais)} car.) → 400",
                   r.status_code == 400, r.status_code)
            r = echange("inconnu-" + "z" * 40)
            ok("PKCE    code inconnu → 400", r.status_code == 400, r.status_code)

            # 4. Échéance
            perime = "perime-" + uuid.uuid4().hex
            await _code_perime(u.id, perime)
            r = echange(perime)
            ok("ÉCHÉANCE code périmé → 400", r.status_code == 400
               and r.json()["detail"] == "Code invalide ou expiré.", r.text)
            ok("ÉCHÉANCE code périmé supprimé", await _codes(u.id) == 1)  # code3 reste
            await _code_perime(u.id, "perime2-" + uuid.uuid4().hex)
            post("code", {"code_challenge": CHALLENGE}, _entete(u))
            ok("ÉCHÉANCE purge des périmés à la demande suivante", await _codes(u.id) == 2)

            # 6. Sorties séparées
            await _jeton_site(u.id)
            ok("SORTIES deux sessions (site + extension)",
               await _clients(u.id) == ["extension", "site"], await _clients(u.id))
            r = post("deconnexion", {"refresh_token": jeton_ext})
            ok("SORTIES déconnexion extension → ok", r.status_code == 200 and r.json() == {"ok": True})
            ok("SORTIES le site reste connecté", await _clients(u.id) == ["site"],
               await _clients(u.id))
            r = post("deconnexion", {"refresh_token": "inconnu"})
            ok("SORTIES jeton inconnu → ok quand même", r.status_code == 200 and r.json() == {"ok": True})

            code4 = post("code", {"code_challenge": CHALLENGE}, _entete(u)).json()["code"]
            jeton_ext = echange(code4).json()["refresh_token"]
            ok("SORTIES extension reconnectée", await _clients(u.id) == ["extension", "site"])
            r = client.post("/api/auth/logout", headers=_entete(u))
            ok("SORTIES logout du site → 200", r.status_code == 200, r.status_code)
            ok("SORTIES l'extension reste connectée", await _clients(u.id) == ["extension"],
               await _clients(u.id))

            # Rotation : le jeton renouvelé garde son client
            r = client.post("/api/auth/refresh", json={"refresh_token": jeton_ext})
            ok("ROTATION renouvellement → 200", r.status_code == 200, r.text)
            ok("ROTATION le client « extension » est conservé",
               await _clients(u.id) == ["extension"], await _clients(u.id))

            # État du compte changé pendant les 60 s : compte devenu non vérifié
            r = post("code", {"code_challenge": CHALLENGE}, _entete(u))
            code_nv = r.json()["code"]
            async with async_session() as db:
                (await db.get(User, u.id)).email_verified = False
                await db.commit()
            r = echange(code_nv)
            ok("COMPTE  devenu non vérifié → échange refusé", r.status_code == 400, r.status_code)
            async with async_session() as db:
                (await db.get(User, u.id)).email_verified = True
                await db.commit()

            # Révocation totale (réinitialisation du mot de passe) : codes en attente annulés
            post("code", {"code_challenge": CHALLENGE}, _entete(u))
            ok("REVOC   des codes en attente avant révocation", await _codes(u.id) >= 1, await _codes(u.id))
            async with async_session() as db:
                await revoke_user_tokens(db, u.id)
            ok("REVOC   révocation totale → plus aucun code", await _codes(u.id) == 0, await _codes(u.id))
    finally:
        await _nettoyer(uids)
        await _eng.dispose()

    print()
    for nom, cond, detail in checks:
        print(f"  {'OK  ' if cond else 'ECHEC'}  {nom}"
              + (f"   [{detail}]" if not cond and detail else ""))
    reussis = sum(1 for _, c, _ in checks if c)
    print(f"\n  {reussis}/{len(checks)}\n")
    return reussis == len(checks)


def test_extension_auth():
    """Point d'entrée pytest : la suite complète, un seul verdict."""
    assert asyncio.run(run())


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(run()) else 1)
