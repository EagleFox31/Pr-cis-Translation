"""
Pause et annulation d'une traduction à la demande du client : seul son
propriétaire peut l'arrêter ; l'arrêt est pris au point de contrôle suivant ;
les pages traduites restent débitées, le reste est rendu ; un document en
pause ou annulé se reprend sans repayer ses pages faites.

    PYTHONUTF8=1 venv/Scripts/python.exe tests/test_arret_job.py
"""
from __future__ import annotations
import asyncio
import json
import os
import shutil
import sys
import tempfile
import time
import uuid

import racine  # noqa: F401  -- met backend/ sur le chemin

import fitz                                              # noqa: E402
from fastapi.testclient import TestClient                # noqa: E402
from sqlalchemy.ext.asyncio import (                     # noqa: E402
    create_async_engine, async_sessionmaker, AsyncSession,
)
from sqlalchemy.pool import NullPool                     # noqa: E402

from app.core.database import DATABASE_URL               # noqa: E402
from app.models import Document, User                    # noqa: E402
from app.core.security import create_access_token        # noqa: E402
from app import config as cfg                            # noqa: E402
from app import create_app                               # noqa: E402
from app.api import translate as route_translate         # noqa: E402
from app.services.documents import build_job_paths, translation_path_for  # noqa: E402
from app.core.files import get_file_hash                 # noqa: E402
from app.services.jobs import ArretDemande, jobs         # noqa: E402
from app.services.scheduler import TranslationScheduler  # noqa: E402
from engines.pdf.engine import PDFObjectEngine          # noqa: E402
from engines.pdf.version import ENGINE_VERSION          # noqa: E402
from engines.pdf.stream import translate_pdf_progressive  # noqa: E402

_eng = create_async_engine(DATABASE_URL, poolclass=NullPool)
async_session = async_sessionmaker(_eng, class_=AsyncSession,
                                   expire_on_commit=False)


def _pdf(n_pages: int) -> bytes:
    doc = fitz.open()
    for i in range(n_pages):
        doc.new_page(width=400, height=300).insert_text(
            (40, 100), f"arret {uuid.uuid4().hex} page {i}", fontsize=12)
    data = doc.tobytes()
    doc.close()
    return data


def _attendre(job_id: str, etats=("paused", "cancelled"), delai=10.0) -> str | None:
    fin = time.time() + delai
    while time.time() < fin:
        etat = (jobs.get(job_id) or {}).get("state")
        if etat in etats:
            return etat
        time.sleep(0.05)
    return (jobs.get(job_id) or {}).get("state")


async def run():
    checks = []

    def ok(nom, cond, detail=""):
        checks.append((nom, bool(cond), detail))

    # Unitaire : le drapeau d'arrêt.
    jid = jobs.create()
    ok("arrêt d'un job inconnu refusé", jobs.demander_arret("inconnu", "paused") is None)
    ok("arrêt d'un job en file : à arrêter tout de suite",
       jobs.demander_arret(jid, "cancelled") == "en_file")
    ok("un job arrêté en file n'est pas démarré", jobs.demarrer(jid) is False)
    try:
        jobs.verifier_arret(jid)
        ok("le point de contrôle lève l'arrêt", False)
    except ArretDemande as a:
        ok("le point de contrôle lève l'arrêt", a.mode == "cancelled", a.mode)
    ok("ArretDemande traverse un `except Exception`",
       not issubclass(ArretDemande, Exception))
    jobs.arreter(jid, "cancelled")
    evt = jobs.get(jid)["q"].get_nowait()
    ok("le flux reçoit « stopped »", evt == {"type": "stopped", "mode": "cancelled"}, str(evt))
    ok("arrêt d'un job fini refusé", not jobs.demander_arret(jid, "paused"))
    jobs.forget(jid)
    jid = jobs.create()
    ok("un job pris par un worker démarre", jobs.demarrer(jid) is True)
    ok("arrêt d'un job démarré : au prochain point de contrôle",
       jobs.demander_arret(jid, "paused") == "en_cours")
    ok("second arrêt refusé", jobs.demander_arret(jid, "cancelled") is None)
    jobs.forget(jid)
    jid = jobs.create()
    jobs.get(jid)["document_id"] = "doc-biblio"
    ok("la bibliothèque retrouve le job d'un document",
       jobs.id_for_document("doc-biblio") == jid)
    jobs.forget(jid)
    ok("document sans job vivant : aucun job", jobs.id_for_document("doc-biblio") is None)

    soumis, original_present = [], []
    vrai_submit = route_translate.scheduler.submit

    def faux_submit(job_id, *a, **k):
        soumis.append(job_id)
        job_dir, _ = build_job_paths(get_file_hash(data), "en")
        original_present.append(os.path.isfile(os.path.join(job_dir, "original.pdf")))
    route_translate.scheduler.submit = faux_submit
    ordo = TranslationScheduler(1)

    u = User(email=f"arret-{uuid.uuid4().hex[:8]}@example.com",
             plan="starter", email_verified=True)
    autre = User(email=f"arret-{uuid.uuid4().hex[:8]}@example.com",
                 plan="starter", email_verified=True)
    async with async_session() as db:
        db.add_all([u, autre])
        await db.commit()

    def entetes_de(x):
        return {"X-API-Key": cfg.FRONTEND_API_KEY,
                "Authorization": f"Bearer {create_access_token(x.id, x.email)}"}
    entetes = entetes_de(u)
    data = _pdf(4)

    try:
        with TestClient(create_app()) as client:
            def traduire(**extra):
                r = client.post("/api/translate", headers=entetes,
                                files={"file": ("doc.pdf", data, "application/pdf")},
                                data={"target_lang": "en", "pages": "2-3", **extra})
                job_id = r.json().get("job_id")
                return r, job_id, (jobs.get(job_id) or {}).get("document_id")

            def doc_api(doc_id):
                liste = client.get("/api/documents", headers=entetes).json()
                liste = liste.get("documents", liste) if isinstance(liste, dict) else liste
                return next((d for d in liste if d["id"] == doc_id), {})

            def utilisees():
                return client.get("/api/auth/me/usage", headers=entetes).json().get("pages_used")

            def arreter(job_id, action, qui=None):
                return client.post(f"/api/translate/{job_id}/{action}",
                                   headers=qui or entetes)

            r, job_id, doc_id = traduire()
            ok("2 pages réservées", r.status_code == 200 and utilisees() == 2,
               f"{r.status_code} {utilisees()}")
            ok("un autre compte ne peut pas arrêter ce job",
               arreter(job_id, "cancel", entetes_de(autre)).status_code == 404)
            ok("action inconnue refusée", arreter(job_id, "stop").status_code in (404, 422))
            # La page 2 est traduite sur disque quand la pause est prise.
            _, lang_dir = build_job_paths(get_file_hash(data), "en")
            os.makedirs(lang_dir, exist_ok=True)
            # Vraie extraction : le partiel se REND (décision E), un faux
            # squelette de page n'y suffirait pas.
            src = fitz.open(stream=data, filetype="pdf")
            page2 = PDFObjectEngine().extract_page_data(src, 1, src[1],
                                                        images_par_reference=True)
            src.close()
            page2["moteur"] = ENGINE_VERSION
            for e in page2["elements"]:
                if e.get("type") == "paragraph":
                    e["tr_tagged"] = "<s1>done</s1>"
            with open(translation_path_for(lang_dir, "pdf", {2, 3}, ""), "w",
                      encoding="utf-8") as f:
                json.dump({"pages": [page2]}, f)

            # Moteur PDF : l'arrêt n'interrompt pas une page déjà au cache
            # (elle se recopie sans frais), seulement une page À traduire.
            def _arret():
                raise ArretDemande("paused")
            tmp = tempfile.mkdtemp(prefix="arret_pdf_")
            try:
                source = os.path.join(tmp, "o.pdf")
                with open(source, "wb") as f:
                    f.write(data)
                cache = translation_path_for(lang_dir, "pdf", {2, 3}, "")
                try:
                    translate_pdf_progressive(source, os.path.join(tmp, "a.pdf"), "en",
                                              pages={2}, cache_path=cache, arret=_arret)
                    ok("PDF : page au cache livrée malgré l'arrêt", True)
                except ArretDemande:
                    ok("PDF : page au cache livrée malgré l'arrêt", False)
                try:
                    translate_pdf_progressive(source, os.path.join(tmp, "b.pdf"), "en",
                                              pages={2, 3}, cache_path=cache, arret=_arret)
                    ok("PDF : arrêt avant la page à traduire", False)
                except ArretDemande:
                    ok("PDF : arrêt avant la page à traduire", True)

                # Arrêt pendant la traduction de la page 3 : abandonnée sur-le-
                # champ (le modèle « ne répond pas » 4 s), jamais mise au cache.
                from engines.pdf import translate as pdf_translate
                from engines import translation_ai
                demande = []
                vrai_tr, vraie_fiche = (pdf_translate.translate_extraction,
                                        translation_ai.TranslatorAI.fiche_document)

                def _lent(data, **_k):
                    demande.append(1)
                    time.sleep(4)
                    for e in data["pages"][0]["elements"]:
                        if e.get("type") == "paragraph":
                            e["tr_tagged"] = "<s1>tard</s1>"

                def _arret_en_vol():
                    if demande:
                        raise ArretDemande("cancelled")
                pdf_translate.translate_extraction = _lent
                translation_ai.TranslatorAI.fiche_document = lambda *a, **k: ""
                debut = time.monotonic()
                try:
                    translate_pdf_progressive(source, os.path.join(tmp, "c.pdf"), "en",
                                              pages={2, 3}, cache_path=cache,
                                              arret=_arret_en_vol)
                    ok("PDF : page en vol abandonnée sans attendre", False)
                except ArretDemande:
                    ok("PDF : page en vol abandonnée sans attendre",
                       time.monotonic() - debut < 2.5, f"{time.monotonic() - debut:.1f} s")
                finally:
                    pdf_translate.translate_extraction = vrai_tr
                    translation_ai.TranslatorAI.fiche_document = vraie_fiche
                time.sleep(4.5)               # la réponse tardive arrive
                with open(cache, encoding="utf-8") as f:
                    au_cache = {p.get("page_num") for p in json.load(f).get("pages", [])}
                ok("PDF : page tardive jamais mise au cache", 3 not in au_cache,
                   str(au_cache))
            finally:
                shutil.rmtree(tmp, ignore_errors=True)

            r = arreter(job_id, "pause")
            ok("le propriétaire met en pause", r.status_code == 200
               and r.json().get("status") == "paused", f"{r.status_code} {r.text[:120]}")
            ok("l'original est écrit avant la mise en file",
               original_present[:1] == [True], str(original_present))
            ok("un job encore en file s'arrête tout de suite",
               (jobs.get(job_id) or {}).get("state") == "paused",
               str((jobs.get(job_id) or {}).get("state")))

            # Point de contrôle « avant le démarrage » : le job en file ne part pas.
            lance = []
            ordo.submit(job_id, 0, lambda: lance.append(1), ())
            etat = await asyncio.to_thread(_attendre, job_id)
            ok("un job en pause avant son démarrage ne démarre pas",
               etat == "paused" and not lance, f"{etat} {lance}")
            ok("pause : document « en pause »",
               doc_api(doc_id).get("status") == "paused", str(doc_api(doc_id).get("status")))
            ok("pause : la page traduite reste débitée, l'autre est rendue",
               utilisees() == 1, str(utilisees()))
            ok("arrêt d'un job déjà arrêté : 409",
               arreter(job_id, "cancel").status_code == 409)
            r = client.get(f"/api/translate/result/{job_id}", headers=entetes)
            ok("résultat d'un job arrêté : 409, pas 202", r.status_code == 409, str(r.status_code))

            # Reconnexion SSE : l'événement final déjà consommé est reconstitué.
            q = jobs.get(job_id)["q"]
            while not q.empty():
                q.get_nowait()
            jeton = entetes["Authorization"].split()[1]
            with client.stream("GET", f"/api/translate/events/{job_id}",
                               params={"token": jeton}) as flux:
                corps = "".join(flux.iter_text())
            ok("SSE : « stopped » rejoué à la reconnexion",
               '"type": "stopped"' in corps and '"mode": "paused"' in corps, corps[-200:])

            # Décision E : les pages traduites d'un document arrêté se livrent.
            r = client.get(f"/api/documents/{doc_id}/download", headers=entetes)
            ok("téléchargement du partiel d'un document en pause",
               r.status_code == 200 and "_TRADUIT_PARTIEL" in r.headers.get("content-disposition", ""),
               f"{r.status_code} {r.headers.get('content-disposition')} {r.text[:120]}")
            r = client.get(f"/api/documents/{doc_id}/preview", headers=entetes)
            ok("aperçu du partiel d'un document en pause",
               r.status_code == 200 and r.content[:4] == b"%PDF", f"{r.status_code} {r.text[:120]}")

            # Le fichier est partagé par empreinte : un autre compte y a traduit
            # la page 3. Ce document n'a payé qu'une page : il ne reçoit qu'elle.
            cache_pdf = translation_path_for(lang_dir, "pdf", {2, 3}, "")
            with open(cache_pdf, encoding="utf-8") as f:
                avant_autre = f.read()
            src = fitz.open(stream=data, filetype="pdf")
            page3 = PDFObjectEngine().extract_page_data(src, 2, src[2],
                                                        images_par_reference=True)
            src.close()
            page3["moteur"] = ENGINE_VERSION
            for e in page3["elements"]:
                if e.get("type") == "paragraph":
                    e["tr_tagged"] = "<s1>autre</s1>"
            with open(cache_pdf, "w", encoding="utf-8") as f:
                json.dump({"pages": [page2, page3]}, f)

            def textes_pdf(octets):
                d = fitz.open(stream=octets, filetype="pdf")
                try:
                    return [p.get_text() for p in d]
                finally:
                    d.close()
            r = client.get(f"/api/documents/{doc_id}/download", headers=entetes)
            t = textes_pdf(r.content) if r.status_code == 200 else []
            ok("partiel borné au payé : seule la page payée, traduite, est livrée",
               len(t) == 1 and "done" in t[0],
               f"{r.status_code} {[x[:30] for x in t]}")
            r = client.get(f"/api/documents/{doc_id}/preview", params={"page": 3},
                           headers=entetes)
            t = textes_pdf(r.content) if r.status_code == 200 else []
            ok("aperçu borné au payé : la page non payée est l'original",
               len(t) == 4 and "autre" not in t[2] and "arret" in t[2],
               f"{r.status_code} {[x[:30] for x in t]}")
            with open(cache_pdf, "w", encoding="utf-8") as f:
                f.write(avant_autre)

            # Plan gratuit, page non achetée : pas de téléchargement, aperçu en pixels.
            async def changer_plan(plan):
                async with async_session() as db:
                    x = await db.get(User, u.id)
                    x.plan = plan
                    # Payé sous Starter, le document garde son droit au clair :
                    # on le bascule aussi en « non payé ».
                    d = await db.get(Document, doc_id)
                    d.paid = plan != "free"
                    await db.commit()
            await changer_plan("free")
            r_dl = client.get(f"/api/documents/{doc_id}/download", headers=entetes)
            r_ap = client.get(f"/api/documents/{doc_id}/preview", headers=entetes)
            await changer_plan("starter")
            ok("plan gratuit : partiel non téléchargeable (402)",
               r_dl.status_code == 402, str(r_dl.status_code))
            t = textes_pdf(r_ap.content) if r_ap.status_code == 200 else ["?"]
            ok("plan gratuit : aperçu du partiel rastérisé (aucun texte)",
               r_ap.status_code == 200 and not "".join(t).strip(),
               f"{r_ap.status_code} {[x[:30] for x in t]}")

            # Reprise d'un document en pause : seul le reste est débité.
            r, repris_job, repris_id = traduire(resume_of=doc_id)
            ok("la reprise d'un document en pause ne paie que le reste",
               r.status_code == 200 and utilisees() == 2, f"{r.status_code} {utilisees()}")
            ok("la reprise retient la page déjà payée",
               (doc_api(repris_id).get("reglages") or {}).get("deja") == 1,
               str(doc_api(repris_id).get("reglages")))
            r = client.get(f"/api/documents/{doc_id}/download", headers=entetes)
            ok("un document repris ne livre plus de partiel",
               "_PARTIEL" not in r.headers.get("content-disposition", ""),
               f"{doc_api(doc_id).get('status')} {r.status_code} "
               f"{r.headers.get('content-disposition')}")

            # Annulation de la reprise en cours : le job s'arrête à son point
            # de contrôle, la page réservée pour lui est rendue.
            ok("le propriétaire annule", arreter(repris_job, "cancel").status_code == 200)

            def _job_qui_leve():
                jobs.verifier_arret(repris_job)
                lance.append(2)
            ordo.submit(repris_job, 0, _job_qui_leve, ())
            etat = await asyncio.to_thread(_attendre, repris_job)
            ok("annulation : job arrêté", etat == "cancelled" and 2 not in lance, str(etat))
            ok("annulation : document « annulé »",
               doc_api(repris_id).get("status") == "cancelled",
               str(doc_api(repris_id).get("status")))
            ok("annulation : la page non faite est rendue, la page payée reste",
               utilisees() == 1, str(utilisees()))
            r, _, _ = traduire(resume_of=repris_id)
            ok("un document annulé se reprend en ne payant que le reste",
               r.status_code == 200 and utilisees() == 2, f"{r.status_code} {utilisees()}")
    finally:
        route_translate.scheduler.submit = vrai_submit
        for j in soumis:
            jobs.forget(j)
        async with async_session() as db:
            for x in (u, autre):
                obj = await db.get(User, x.id)
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
