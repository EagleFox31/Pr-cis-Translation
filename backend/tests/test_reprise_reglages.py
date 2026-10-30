"""
Reprise d'une traduction : les réglages d'origine sont gardés sur le Document,
un arrêt du serveur la laisse « interrompue » (à reprendre), pas en échec, et
seules les pages non traduites sont rendues ; la reprise ne débite que le reste.

    PYTHONUTF8=1 venv/Scripts/python.exe tests/test_reprise_reglages.py
"""
from __future__ import annotations
import asyncio
import json
import os
import shutil
import sys
import uuid

import racine  # noqa: F401  -- met backend/ sur le chemin

import fitz                                              # noqa: E402
from fastapi.testclient import TestClient                # noqa: E402
from sqlalchemy.ext.asyncio import (                     # noqa: E402
    create_async_engine, async_sessionmaker, AsyncSession,
)
from sqlalchemy.pool import NullPool                     # noqa: E402

from app.core.database import DATABASE_URL               # noqa: E402
from app.models import User, Document                    # noqa: E402
from app.core.security import create_access_token        # noqa: E402
from app import config as cfg                            # noqa: E402
from app import create_app                               # noqa: E402
from app.api import translate as route_translate         # noqa: E402
from app.services.documents import build_job_paths, translation_path_for  # noqa: E402
from app.core.files import get_file_hash                 # noqa: E402
from app.services.jobs import jobs                       # noqa: E402
from app.services.startup import reconcilier_jobs_orphelins  # noqa: E402

_eng = create_async_engine(DATABASE_URL, poolclass=NullPool)
async_session = async_sessionmaker(_eng, class_=AsyncSession,
                                   expire_on_commit=False)


def _pdf(n_pages: int) -> bytes:
    doc = fitz.open()
    for i in range(n_pages):
        doc.new_page(width=400, height=300).insert_text(
            (40, 100), f"reprise {uuid.uuid4().hex} page {i}", fontsize=12)
    data = doc.tobytes()
    doc.close()
    return data


async def run():
    checks = []

    def ok(nom, cond, detail=""):
        checks.append((nom, bool(cond), detail))

    soumis = []
    vrai_submit = route_translate.scheduler.submit
    route_translate.scheduler.submit = lambda job_id, *a, **k: soumis.append(job_id)

    u = User(email=f"reprise-{uuid.uuid4().hex[:8]}@example.com",
             plan="starter", email_verified=True)
    async with async_session() as db:
        db.add(u)
        await db.commit()
    entetes = {"X-API-Key": cfg.FRONTEND_API_KEY,
               "Authorization": f"Bearer {create_access_token(u.id, u.email)}"}
    data = _pdf(4)

    try:
        with TestClient(create_app()) as client:
            def traduire(**extra):
                r = client.post("/api/translate", headers=entetes,
                                files={"file": ("doc.pdf", data, "application/pdf")},
                                data={"target_lang": "en", "pages": "2-3", **extra})
                return r, (jobs.get(r.json().get("job_id")) or {}).get("document_id")

            def job_de(doc_id):
                return next(j for j in soumis
                            if (jobs.get(j) or {}).get("document_id") == doc_id)

            def doc_api(doc_id):
                liste = client.get("/api/documents", headers=entetes).json()
                liste = liste.get("documents", liste) if isinstance(liste, dict) else liste
                return next((d for d in liste if d["id"] == doc_id), {})

            def utilisees():
                return client.get("/api/auth/me/usage", headers=entetes).json().get("pages_used")

            # Le ménage de démarrage tourne dans la boucle de l'application :
            # appelé depuis la boucle du test, ses connexions se bloquent.
            def arret_serveur():
                client.portal.call(reconcilier_jobs_orphelins)

            r, doc_id = traduire()
            ok("la traduction de 2 pages sur 4 est acceptée", r.status_code == 200,
               f"{r.status_code} {r.text[:120]}")
            reg = doc_api(doc_id).get("reglages")
            ok("les réglages d'origine sont renvoyés à la bibliothèque",
               reg == {"pages": "2,3", "precise": False, "beta": False, "deja": 0,
                      "qsuffix": ""}, str(reg))
            ok("2 pages réservées", utilisees() == 2, str(utilisees()))

            # La page 2 est traduite sur disque quand le serveur s'arrête.
            _, lang_dir = build_job_paths(get_file_hash(data), "en")
            os.makedirs(lang_dir, exist_ok=True)
            with open(translation_path_for(lang_dir, "pdf", {2, 3}, ""), "w",
                      encoding="utf-8") as f:
                json.dump({"pages": [{"page_num": 2, "elements": [
                    {"type": "paragraph", "tr_tagged": "<s1>done</s1>"}]}]}, f)

            arret_serveur()
            statut = doc_api(doc_id).get("status")
            ok("après un arrêt du serveur : « interrompu », pas « échec »",
               statut == "interrupted", str(statut))
            ok("après un arrêt : la page traduite reste débitée, l'autre est rendue",
               utilisees() == 1, str(utilisees()))

            r, repris_id = traduire(resume_of=doc_id)
            ok("la reprise est acceptée", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
            ok("la reprise ne débite que la page restante", utilisees() == 2, str(utilisees()))
            ok("le document repris passe « reprise »",
               doc_api(doc_id).get("status") == "resumed", str(doc_api(doc_id).get("status")))
            ok("la reprise retient la page déjà payée",
               (doc_api(repris_id).get("reglages") or {}).get("deja") == 1,
               str(doc_api(repris_id).get("reglages")))

            # Worker de l'ancien processus qui finit tard : le document est
            # repris, sa facturation appartient à la reprise.
            await asyncio.to_thread(jobs.sync_status, job_de(doc_id), "done")
            ok("un job tardif sur un document repris ne refacture rien",
               utilisees() == 2 and doc_api(doc_id).get("status") == "resumed",
               f"{utilisees()} {doc_api(doc_id).get('status')}")

            # La reprise échoue : elle redevient reprenable, sans perdre la
            # page payée par le document d'origine.
            await asyncio.to_thread(jobs.sync_status, job_de(repris_id), "error")
            ok("l'échec d'une reprise la laisse « interrompue »",
               doc_api(repris_id).get("status") == "interrupted",
               str(doc_api(repris_id).get("status")))
            ok("l'échec d'une reprise rend sa page non traduite",
               utilisees() == 1, str(utilisees()))
            r, _ = traduire(resume_of=repris_id)
            ok("la reprise d'une reprise échouée ne paie que le reste",
               r.status_code == 200 and utilisees() == 2, f"{r.status_code} {utilisees()}")

            r, autre_id = traduire(resume_of=doc_id)
            ok("une seconde reprise du même document paie plein tarif",
               r.status_code == 200 and utilisees() == 4, f"{r.status_code} {utilisees()}")

            # Nouvel arrêt : la reprise n'a payé que son reste, elle ne garde
            # rien de plus ; l'autre garde sa page traduite.
            arret_serveur()
            ok("un second arrêt ne facture pas deux fois la page traduite",
               utilisees() == 2, str(utilisees()))

            # Le ménage garde la traduction partielle d'un document interrompu.
            from app.services.documents import chemin_traduction_du_document
            async with async_session() as db:
                autre = await db.get(Document, autre_id)
            ok("le ménage connaît le fichier partiel d'un document interrompu",
               autre.status == "interrupted" and chemin_traduction_du_document(autre)
               == translation_path_for(lang_dir, "pdf", {2, 3}, ""),
               f"{autre.status} {chemin_traduction_du_document(autre)}")

            # Autre sélection : rien de payé n'est repris, le document d'origine
            # reste « interrompu » (reprenable).
            r = client.post("/api/translate", headers=entetes,
                            files={"file": ("doc.pdf", data, "application/pdf")},
                            data={"target_lang": "en", "pages": "1-4",
                                  "resume_of": autre_id})
            ok("une reprise sans remise paie plein tarif",
               r.status_code == 200 and utilisees() == 6, f"{r.status_code} {utilisees()}")
            ok("une reprise sans remise laisse l'original « interrompu »",
               doc_api(autre_id).get("status") == "interrupted",
               str(doc_api(autre_id).get("status")))
    finally:
        route_translate.scheduler.submit = vrai_submit
        for jid in soumis:
            jobs.forget(jid)
        async with async_session() as db:
            obj = await db.get(User, u.id)
            if obj:
                await db.delete(obj)
            await db.commit()
        job_dir, _ = build_job_paths(get_file_hash(data), "en")
        shutil.rmtree(job_dir, ignore_errors=True)

    print()
    for nom, cond, detail in checks:
        print(f"  {'OK  ' if cond else 'ÉCHEC'}  {nom}"
              + (f"   [{detail}]" if not cond and detail else ""))
    reussis = sum(1 for _, c, _ in checks if c)
    print(f"\n  {reussis}/{len(checks)}\n")
    return reussis == len(checks)


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(run()) else 1)
