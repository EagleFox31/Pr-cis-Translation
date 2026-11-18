"""Journal central des erreurs — écriture, regroupement, garde admin, cycle
« consigner puis vider », et mails admin selon la gravité.

Ce qui est MESURÉ, jamais supposé :
  • `log_error` écrit une ligne, d'où qu'on l'appelle ;
  • deux occurrences d'un même défaut partagent leur `fingerprint` (regroupement)
    et deux défauts distincts non ;
  • `require_admin` bloque un non-admin (403) et laisse passer l'admin ;
  • on NE supprime PAS un log `new` (409) — il faut d'abord marquer traité ;
  • mails admin : error regroupées (1/h), critical immédiat (1 par panne),
    critical du navigateur rétrogradé, warning sans mail, récap quotidien unique.

Exécution :  backend/venv/Scripts/python.exe backend/tests/test_error_logs.py
Requiert PostgreSQL et la migration 0005.
"""
from __future__ import annotations
import asyncio
import sys
import uuid

import racine  # noqa: F401  -- met backend/ sur le chemin

from fastapi import HTTPException                         # noqa: E402
from sqlalchemy import delete, select                      # noqa: E402
from sqlalchemy.ext.asyncio import (                      # noqa: E402
    AsyncSession, async_sessionmaker, create_async_engine,
)
from sqlalchemy.pool import NullPool                      # noqa: E402

from app.core.database import DATABASE_URL                # noqa: E402
from app.core.security import require_admin               # noqa: E402
from app.models import ErrorLog, STATUS_HANDLED, STATUS_NEW, User  # noqa: E402
from app.services import error_log as svc                 # noqa: E402
from app.api.logs import (                                 # noqa: E402
    TargetBody, delete_logs, list_groups, mark_handled,
)

_eng = create_async_engine(DATABASE_URL, poolclass=NullPool)
async_session = async_sessionmaker(_eng, class_=AsyncSession, expire_on_commit=False)

TOKEN = f"ERRLOG-TEST-{uuid.uuid4().hex[:8]}"

_checks: list[tuple[bool, str]] = []


def check(cond: bool, label: str) -> None:
    _checks.append((bool(cond), label))
    print(f"  {'OK ' if cond else 'XX '} {label}")


async def main() -> None:
    # ── Comptes de test ───────────────────────────────────────────────────────
    admin = User(email=f"admin-{TOKEN}@t.io", plan="admin")
    normal = User(email=f"user-{TOKEN}@t.io", plan="free")
    async with async_session() as db:
        db.add_all([admin, normal])
        await db.commit()
        admin_id, normal_id = admin.id, normal.id

    # ── 1. log_error écrit une ligne ──────────────────────────────────────────
    await svc.log_error("frontend", f"{TOKEN} boom", level="error",
                        stack="Trace\n at x", context={"url": "/x"},
                        location="Hero", trigger_alert=False)
    async with async_session() as db:
        row = (await db.execute(
            select(ErrorLog).where(ErrorLog.message.like(f"%{TOKEN} boom%"))
        )).scalars().first()
    check(row is not None and row.source == "frontend" and row.stack is not None,
          "log_error écrit une ligne (source + pile)")

    # ── 2. fingerprint : stable et discriminant ───────────────────────────────
    fp_a1 = svc.fingerprint("frontend", "error", "hello", "L")
    fp_a2 = svc.fingerprint("frontend", "error", "hello", "L")
    fp_b = svc.fingerprint("frontend", "error", "world", "L")
    check(fp_a1 == fp_a2, "fingerprint stable pour un même défaut")
    check(fp_a1 != fp_b, "fingerprint distingue deux défauts")

    # ── 3. Regroupement : 3 occurrences d'une même empreinte ──────────────────
    grp_fp = svc.fingerprint("backend", "error", f"{TOKEN} grp", "L")
    async with async_session() as db:
        for _ in range(3):
            db.add(ErrorLog(source="backend", level="error",
                            message=f"{TOKEN} grp", fingerprint=grp_fp,
                            status=STATUS_NEW))
        await db.commit()
        res = await list_groups(source="backend", q=TOKEN, _admin=admin, db=db)
    grp = next((g for g in res["groups"] if g["fingerprint"] == grp_fp), None)
    check(grp is not None and grp["count"] == 3 and grp["status"] == STATUS_NEW,
          "la liste regroupe 3 occurrences en une entrée (count=3, new)")

    # ── 3b. La recherche trouve aussi par e-mail du compte ────────────────────
    mail_fp = svc.fingerprint("backend", "error", f"{TOKEN} mail", "L")
    async with async_session() as db:
        db.add(ErrorLog(source="backend", level="error", message=f"{TOKEN} mail",
                        fingerprint=mail_fp, status=STATUS_NEW,
                        user_email=normal.email))
        await db.commit()
        res = await list_groups(q=normal.email, _admin=admin, db=db)
    check(any(g["fingerprint"] == mail_fp for g in res["groups"]),
          "la recherche du journal trouve une erreur par l'e-mail du compte")

    # ── 3c. Filtre exact par compte, jokers de recherche neutralisés ──────────
    autre_fp = svc.fingerprint("backend", "error", f"{TOKEN} autre", "L")
    async with async_session() as db:
        db.add(ErrorLog(source="backend", level="error", message=f"{TOKEN} autre",
                        fingerprint=autre_fp, status=STATUS_NEW,
                        user_email=f"x{normal.email}"))
        await db.commit()
        exact = await list_groups(user_email=normal.email.upper(), _admin=admin, db=db)
        joker = await list_groups(q="%", _admin=admin, db=db)
    fps = {g["fingerprint"] for g in exact["groups"]}
    check(mail_fp in fps and autre_fp not in fps,
          "le filtre user_email ne garde que ce compte (pas un e-mail qui le contient)")
    check(not any(g["fingerprint"] in (mail_fp, autre_fp) for g in joker["groups"]),
          "un « % » dans la recherche est cherché tel quel, pas comme joker")

    # ── 4. Garde admin ────────────────────────────────────────────────────────
    blocked = False
    try:
        await require_admin(user=normal)
    except HTTPException as e:
        blocked = (e.status_code == 403)
    check(blocked, "require_admin refuse un non-admin (403)")
    check(await require_admin(user=admin) is admin, "require_admin laisse passer l'admin")

    # ── 5. Cycle : suppression REFUSÉE tant que `new`, permise une fois traité ─
    refused = False
    async with async_session() as db:
        try:
            await delete_logs(TargetBody(fingerprints=[grp_fp]), _admin=admin, db=db)
        except HTTPException as e:
            refused = (e.status_code == 409)
    check(refused, "suppression d'un log `new` refusée (409)")

    async with async_session() as db:
        r = await mark_handled(TargetBody(fingerprints=[grp_fp]), _admin=admin, db=db)
    check(r["handled"] == 3, "marquage `traité` sur les 3 occurrences")

    async with async_session() as db:
        r = await delete_logs(TargetBody(fingerprints=[grp_fp]), _admin=admin, db=db)
    check(r["deleted"] == 3, "suppression permise une fois `traité`")

    # ── 6. Mails admin selon la gravité (docs/etude-retours-18-11.md §2) ──────
    import datetime as dt
    from types import SimpleNamespace
    from app.services import alertes_admin as al
    import app.core.email as email_mod

    sent: list[tuple[str, dict]] = []
    orig_send = email_mod.send_plain

    async def fake_send(to, subject, body, **carte):   # noqa: ANN001
        sent.append((subject, carte))

    email_mod.send_plain = fake_send
    al._reinitialiser()
    jours = [dt.date(2001, 1, 1), dt.date(2001, 1, 2)]
    try:
        # 20 erreurs d'affilée → un seul mail qui les regroupe
        for i in range(20):
            await svc.log_error("backend", f"{TOKEN} rafale{i % 2}", location=f"L{i % 2}")
        check(len(sent) == 1, "20 erreurs d'affilée → un seul mail")
        check(len(sent[0][1].get("details", [])) <= 3, "le mail liste au plus 3 groupes")

        # critical : tout de suite, une fois par panne
        sent.clear()
        await svc.log_error("backend", f"{TOKEN} panne", level="critical", location="P")
        await svc.log_error("backend", f"{TOKEN} panne", level="critical", location="P")
        check(len(sent) == 1 and sent[0][1].get("niveau") == "critique",
              "critical : un mail immédiat, pas de doublon pour la même panne")

        # critical déclaré par le navigateur → traité comme error (déjà envoyé : rien)
        sent.clear()
        check(al.niveau_alerte("frontend", "critical") == "error",
              "critical du navigateur rétrogradé en error")
        await svc.log_error("frontend", f"{TOKEN} faux critique", level="critical", location="F")
        check(not sent, "critical du navigateur : pas de mail immédiat")

        # warning : jamais de mail
        await svc.log_error("backend", f"{TOKEN} avert", level="warning", location="W")
        check(not sent, "warning : pas de mail")

        # candidature bêta
        async with async_session() as db:
            ok = await al.candidature_beta(db, SimpleNamespace(
                email=f"cand-{TOKEN}@example.com", motivation="Traduire mes cours",
                primary_format="pdf"), "Candidat")
        check(ok and len(sent) == 1 and "candidature" in sent[0][0],
              "candidature bêta → un mail")

        # récapitulatif : rien la veille → pas de mail, mais le jour est marqué
        sent.clear()
        async with async_session() as db:
            r1 = await al.recapitulatif_quotidien(db, jours[0] + dt.timedelta(days=1))
        check(r1 is False and not sent, "récap : journée vide → pas de mail")

        # un avertissement la veille → un mail, une seule fois
        async with async_session() as db:
            db.add(ErrorLog(source="backend", level="warning", message=f"{TOKEN} recap",
                            fingerprint=svc.fingerprint("backend", "warning", "recap", "R"),
                            status=STATUS_NEW,
                            created_at=dt.datetime(2001, 1, 2, 12, tzinfo=dt.timezone.utc)))
            await db.commit()
        async with async_session() as db:
            r2 = await al.recapitulatif_quotidien(db, jours[1] + dt.timedelta(days=1))
        async with async_session() as db:
            r3 = await al.recapitulatif_quotidien(db, jours[1] + dt.timedelta(days=1))
        check(r2 is True and r3 is False and len(sent) == 1,
              "récap : envoyé une fois, pas deux le même jour")
    finally:
        email_mod.send_plain = orig_send
        al._reinitialiser()
        async with async_session() as db:
            from app.models import AdminRecap
            await db.execute(delete(AdminRecap).where(AdminRecap.jour.in_(jours)))
            await db.commit()

    # ── Nettoyage ─────────────────────────────────────────────────────────────
    async with async_session() as db:
        await db.execute(delete(ErrorLog).where(ErrorLog.message.like(f"%{TOKEN}%")))
        for uid in (admin_id, normal_id):
            u = await db.get(User, uid)
            if u:
                await db.delete(u)
        await db.commit()
    await _eng.dispose()

    # ── Verdict ───────────────────────────────────────────────────────────────
    passed = sum(1 for ok, _ in _checks if ok)
    total = len(_checks)
    print(f"\n{passed}/{total} contrôles")
    if passed != total:
        print("ÉCHECS :", [lbl for ok, lbl in _checks if not ok])
        sys.exit(1)
    print("OK — journal des erreurs conforme")


async def _purger() -> None:
    """Filet de sécurité : un test interrompu ne laisse ni admin (destinataire
    des alertes) ni erreurs de test en base."""
    async with async_session() as db:
        await db.execute(delete(ErrorLog).where(ErrorLog.message.like(f"%{TOKEN}%")))
        await db.execute(delete(User).where(User.email.like(f"%{TOKEN}%")))
        await db.commit()
    await _eng.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        asyncio.run(_purger())
