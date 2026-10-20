"""Administration des documents — liste inter-comptes et téléchargement.

Ce qui est MESURÉ :
  • un non-admin est REFUSÉ (403) par la garde `require_admin` ;
  • `list_documents` voit les documents de TOUS les comptes, avec l'e-mail du
    propriétaire, et `q` filtre sur l'e-mail OU le nom du fichier ;
  • `has_original` / `has_translation` reflètent la présence sur disque ;
  • `download_original` rend les octets d'un document d'un AUTRE utilisateur,
    avec un Content-Disposition `filename*=UTF-8''` encodé ;
  • fichier manquant, traduction absente ou document inconnu -> 404.

Exécution :  backend/venv/Scripts/python.exe backend/tests/test_admin_documents.py
Requiert PostgreSQL.
"""
from __future__ import annotations
import asyncio
import os
import sys
import tempfile
import uuid

import racine  # noqa: F401  -- met backend/ sur le chemin

from fastapi import HTTPException                            # noqa: E402
from sqlalchemy import delete                                # noqa: E402
from sqlalchemy.ext.asyncio import (                         # noqa: E402
    AsyncSession, async_sessionmaker, create_async_engine,
)
from sqlalchemy.pool import NullPool                         # noqa: E402

from app.core.database import DATABASE_URL                   # noqa: E402
from app.core.security import require_admin                  # noqa: E402
from app.models import Document, User                       # noqa: E402
from app.api.admin_documents import (                        # noqa: E402
    download_original, download_translated, list_documents,
)

_eng = create_async_engine(DATABASE_URL, poolclass=NullPool)
async_session = async_sessionmaker(_eng, class_=AsyncSession, expire_on_commit=False)

TOKEN = f"ADMINDOC-{uuid.uuid4().hex[:8]}"
CONTENU = b"%PDF-1.4 contenu d'origine \xc3\xa9\x00\x01"

_checks: list[tuple[bool, str]] = []


def check(cond: bool, label: str) -> None:
    _checks.append((bool(cond), label))
    print(f"  {'OK ' if cond else 'XX '} {label}")


async def _statut(coro) -> int | None:
    """Code HTTP de l'exception levée (None si rien n'est levé)."""
    try:
        await coro
    except HTTPException as e:
        return e.status_code
    return None


async def main() -> None:
    tmp = tempfile.mkdtemp(prefix="admindoc_")
    chemin_ok = os.path.join(tmp, "origine.pdf")
    with open(chemin_ok, "wb") as fh:
        fh.write(CONTENU)

    admin = User(email=f"admin-{TOKEN}@t.io", plan="admin")
    proprio = User(email=f"proprio-{TOKEN}@t.io", plan="free")
    async with async_session() as db:
        db.add_all([admin, proprio])
        await db.commit()
        doc_ok = Document(user_id=proprio.id, original_name=f"Rapport é {TOKEN}.pdf",
                          source_lang="fr", target_lang="en",
                          original_path=chemin_ok, size_bytes=len(CONTENU))
        doc_manquant = Document(user_id=proprio.id, original_name=f"Absent-{TOKEN}.pdf",
                                source_lang="fr", target_lang="en",
                                original_path=os.path.join(tmp, "nexiste-pas.pdf"),
                                size_bytes=10)
        db.add_all([doc_ok, doc_manquant])
        await db.commit()
        id_ok, id_manquant = doc_ok.id, doc_manquant.id

    # ── 1. Non-admin -> 403 ────────────────────────────────────────────────────
    check(await _statut(require_admin(proprio)) == 403, "non-admin refusé (403)")
    check(await require_admin(admin) is admin, "admin accepté")

    # ── 2. Liste : documents d'un autre compte, filtre q ───────────────────────
    async with async_session() as db:
        res = await list_documents(q=TOKEN, _admin=admin, db=db)
    par_id = {d["id"]: d for d in res["items"]}
    check(res["total"] == 2 and set(par_id) == {id_ok, id_manquant},
          "list_documents voit les documents d'un autre compte")
    check(par_id[id_ok]["user_email"] == f"proprio-{TOKEN}@t.io",
          "l'e-mail du propriétaire est joint")
    check(par_id[id_ok]["has_original"] is True and par_id[id_manquant]["has_original"] is False,
          "has_original reflète la présence sur disque")
    check(par_id[id_ok]["has_translation"] is False, "pas de traduction -> has_translation faux")

    async with async_session() as db:
        par_nom = await list_documents(q=f"absent-{TOKEN}", _admin=admin, db=db)
        par_mail = await list_documents(q=f"PROPRIO-{TOKEN}", _admin=admin, db=db)
        rien = await list_documents(q=f"zzz-{TOKEN}-zzz", _admin=admin, db=db)
    check([d["id"] for d in par_nom["items"]] == [id_manquant],
          "q filtre sur le nom du fichier (insensible à la casse)")
    check(par_mail["total"] == 2, "q filtre sur l'e-mail du propriétaire (insensible à la casse)")
    check(rien["total"] == 0 and rien["items"] == [], "q sans correspondance -> liste vide")

    # ── 3. Original d'un autre utilisateur -> 200 + octets ─────────────────────
    async with async_session() as db:
        r = await download_original(id_ok, admin=admin, db=db)
    check(r.status_code == 200 and r.body == CONTENU, "original d'un autre compte : 200 + octets")
    cd = r.headers.get("content-disposition", "")
    check(cd.startswith("attachment; filename*=UTF-8''") and "%C3%A9" in cd and " " not in cd,
          "Content-Disposition encodé en UTF-8")

    # ── 4. Fichier manquant / traduction absente / inconnu -> 404 ──────────────
    async with async_session() as db:
        check(await _statut(download_original(id_manquant, admin=admin, db=db)) == 404,
              "fichier d'origine manquant -> 404")
    async with async_session() as db:
        check(await _statut(download_translated(id_ok, admin=admin, db=db)) == 404,
              "traduction absente -> 404")
    async with async_session() as db:
        check(await _statut(download_original("inconnu-" + TOKEN, admin=admin, db=db)) == 404,
              "document inconnu -> 404")

    # ── Nettoyage ─────────────────────────────────────────────────────────────
    async with async_session() as db:
        await db.execute(delete(User).where(User.email.like(f"%{TOKEN}%")))  # cascade
        await db.commit()
    await _eng.dispose()
    try:
        os.remove(chemin_ok)
        os.rmdir(tmp)
    except OSError:
        pass

    passed = sum(1 for ok, _ in _checks if ok)
    total = len(_checks)
    print(f"\n{passed}/{total} contrôles")
    if passed != total:
        print("ÉCHECS :", [lbl for ok, lbl in _checks if not ok])
        sys.exit(1)
    print("OK — administration des documents conforme")


async def _purger() -> None:
    """Filet de sécurité : un test interrompu ne laisse pas d'admin en base
    (l'alerte du journal d'erreurs part à TOUS les admins)."""
    async with async_session() as db:
        await db.execute(delete(User).where(User.email.like(f"%{TOKEN}%")))
        await db.commit()
    await _eng.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        asyncio.run(_purger())
