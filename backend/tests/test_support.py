"""Assistance — creation par un utilisateur, garde admin, cycle traiter/supprimer.

Ce qui est MESURE :
  • `create_ticket` ecrit un ticket avec le snapshot de l'auteur (e-mail + plan) ;
  • une categorie inconnue retombe sur "problem" (pas de valeur fantome) ;
  • `list_tickets` renvoie le ticket a l'admin, avec le compteur d'ouverts ;
  • `handle_tickets` marque traite (+ note interne) ;
  • on NE supprime PAS un ticket `open` (409), mais on supprime un `handled`.

Execution :  backend/venv/Scripts/python.exe backend/tests/test_support.py
Requiert PostgreSQL et la migration 0007.
"""
from __future__ import annotations
import asyncio
import sys
import uuid

import racine  # noqa: F401  -- met backend/ sur le chemin

from fastapi import HTTPException, Request                  # noqa: E402
from sqlalchemy import delete, select                       # noqa: E402
from sqlalchemy.ext.asyncio import (                         # noqa: E402
    AsyncSession, async_sessionmaker, create_async_engine,
)
from sqlalchemy.pool import NullPool                         # noqa: E402

from app.core.database import DATABASE_URL                   # noqa: E402
from app.models import STATUS_OPEN, SupportTicket, TICKET_HANDLED, User  # noqa: E402
import app.api.support as sup                                # noqa: E402
from app.api.support import (DeleteBody, HandleBody, TicketBody,  # noqa: E402
                             create_ticket, delete_tickets,
                             handle_tickets, list_tickets)

_eng = create_async_engine(DATABASE_URL, poolclass=NullPool)
async_session = async_sessionmaker(_eng, class_=AsyncSession, expire_on_commit=False)

TOKEN = f"SUPPORT-{uuid.uuid4().hex[:8]}"

_checks: list[tuple[bool, str]] = []


def check(cond: bool, label: str) -> None:
    _checks.append((bool(cond), label))
    print(f"  {'OK ' if cond else 'XX '} {label}")


def _fake_request() -> Request:
    return Request({"type": "http", "headers": [(b"user-agent", b"pytest")],
                    "method": "POST", "path": "/api/support"})


async def main() -> None:
    # Alerte e-mail neutralisee : le test reste hermetique (pas de SMTP).
    async def _noop(*a, **k):  # noqa: ANN001
        return None
    sup.send_plain = _noop

    admin = User(email=f"admin-{TOKEN}@t.io", plan="admin")
    author = User(email=f"user-{TOKEN}@t.io", plan="starter")
    async with async_session() as db:
        db.add_all([admin, author])
        await db.commit()
        admin_id, author_id = admin.id, author.id

    # ── 1. Creation : snapshot auteur + categorie repli ───────────────────────
    async with async_session() as db:
        auth = await db.get(User, author_id)
        r = await create_ticket(
            TicketBody(category="wat", subject=f"{TOKEN} souci",
                       message="ca ne marche pas", url="/home",
                       document_id="doc-42", document_name="rapport.pdf"),
            _fake_request(), user=auth, db=db)
    tid = r["id"]
    check(r["ok"] and tid, "create_ticket cree un ticket")
    async with async_session() as db:
        tk = await db.get(SupportTicket, tid)
    check(tk is not None and tk.user_email == f"user-{TOKEN}@t.io",
          "l'e-mail de l'auteur est fige sur le ticket")
    check(tk is not None and tk.category == "problem",
          "categorie inconnue -> repli 'problem' (pas de valeur fantome)")
    check(tk is not None and (tk.context or {}).get("plan") == "starter",
          "le plan au moment T est capture dans le contexte")
    check(tk is not None and (tk.context or {}).get("document_name") == "rapport.pdf"
          and (tk.context or {}).get("document_id") == "doc-42",
          "le document reference (id + nom) atterrit dans le contexte")

    # ── 2. Liste (admin) : ticket present + compteur d'ouverts ────────────────
    async with async_session() as db:
        adm = await db.get(User, admin_id)
        res = await list_tickets(q=TOKEN, _admin=adm, db=db)
    subjects = {t["subject"] for t in res["tickets"]}
    check(f"{TOKEN} souci" in subjects, "list_tickets renvoie le ticket a l'admin")
    check(res["open_count"] >= 1, "le compteur d'ouverts inclut le ticket")

    # ── 3. Suppression REFUSEE tant qu'ouvert ─────────────────────────────────
    refused = False
    async with async_session() as db:
        adm = await db.get(User, admin_id)
        try:
            await delete_tickets(DeleteBody(ids=[tid]), _admin=adm, db=db)
        except HTTPException as e:
            refused = (e.status_code == 409)
    check(refused, "suppression d'un ticket ouvert refusee (409)")

    # ── 4. Traitement (+ note), puis suppression permise ──────────────────────
    async with async_session() as db:
        adm = await db.get(User, admin_id)
        h = await handle_tickets(HandleBody(ids=[tid], note="repondu par mail"),
                                 _admin=adm, db=db)
    check(h["handled"] == 1, "handle_tickets marque le ticket traite")
    async with async_session() as db:
        tk = await db.get(SupportTicket, tid)
    check(tk is not None and tk.status == TICKET_HANDLED and tk.admin_note,
          "statut 'handled' + note interne persistes")

    async with async_session() as db:
        adm = await db.get(User, admin_id)
        d = await delete_tickets(DeleteBody(ids=[tid]), _admin=adm, db=db)
    check(d["deleted"] == 1, "suppression permise une fois traite")

    # ── Nettoyage ─────────────────────────────────────────────────────────────
    async with async_session() as db:
        await db.execute(delete(SupportTicket).where(SupportTicket.subject.like(f"%{TOKEN}%")))
        for uid in (admin_id, author_id):
            u = await db.get(User, uid)
            if u:
                await db.delete(u)
        await db.commit()
    await _eng.dispose()

    passed = sum(1 for ok, _ in _checks if ok)
    total = len(_checks)
    print(f"\n{passed}/{total} controles")
    if passed != total:
        print("ECHECS :", [lbl for ok, lbl in _checks if not ok])
        sys.exit(1)
    print("OK - assistance conforme")


if __name__ == "__main__":
    asyncio.run(main())
