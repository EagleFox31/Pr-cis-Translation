"""Verrous de plan — la règle produit, testée porte par porte.

La règle (mots de l'utilisateur) :
  « un utilisateur qui n'a pas de compte ou qui est en fremium ne dois pas
    telecharger ni voir en claire la traduction ; un non connecté ne peux
    meme pas lancer une traduction »

Cette règle a cédé TROIS fois (/result, /partial, /download + /preview),
chaque porte bouchée à la main — et jusqu'ici AUCUN test ne la défendait :
une régression sur n'importe laquelle serait passée en silence. Cette suite
appelle les vraies routes et MESURE (extraction de texte réelle, jamais à
l'œil) que le clair ne sort pas.

Exécution :  backend/venv/Scripts/python.exe backend/test_verrous_plan.py
Requiert la base PostgreSQL (comme le reste du backend).
"""
from __future__ import annotations
import asyncio
import os
import queue
import shutil
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fitz                                              # noqa: E402
from fastapi import HTTPException                        # noqa: E402
from fastapi.testclient import TestClient                # noqa: E402

from sqlalchemy.ext.asyncio import (                     # noqa: E402
    create_async_engine, async_sessionmaker, AsyncSession,
)
from sqlalchemy.pool import NullPool                     # noqa: E402
from database import DATABASE_URL                        # noqa: E402
from models import User, Document                        # noqa: E402

# Moteur DÉDIÉ à connexions non poolées : le TestClient exécute l'app sur SA
# propre boucle asyncio — partager le pool global entre les deux boucles fait
# échouer asyncpg (« attached to a different loop »). Le test garde ses
# connexions, l'app les siennes.
_eng = create_async_engine(DATABASE_URL, poolclass=NullPool)
async_session = async_sessionmaker(_eng, class_=AsyncSession,
                                   expire_on_commit=False)
from auth import create_access_token                     # noqa: E402
import app as appmod                                     # noqa: E402
from routes.documents import (                           # noqa: E402
    STORAGE_BASE, download_document, preview_document,
)

SECRET = "TRADUCTION-CONFIDENTIELLE-XYZZY"


def _pdf_avec_secret() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((40, 100), f"{SECRET} contenu traduit", fontsize=13)
    data = doc.tobytes()
    doc.close()
    return data


def _texte(data: bytes) -> str:
    d = fitz.open(stream=data, filetype="pdf")
    t = "".join(p.get_text() for p in d)
    d.close()
    return t


def _mk_user(plan: str) -> User:
    return User(email=f"verrou-{plan}-{uuid.uuid4().hex[:10]}@example.com",
                plan=plan, email_verified=True)


async def _monter():
    """Deux comptes (free, starter) + un document TRADUIT chacun, dans le vrai
    magasin. `translated_path` désigne désormais la TRADUCTION (JSON), pas un
    rendu : le PDF est recalculé à la demande. On remplace ce rendu par une
    fonction qui renvoie un PDF porteur du secret (le moteur réel est couvert
    par test_engine_v2_generic) — sa présence dans une réponse mesure la fuite."""
    racine = os.path.join(STORAGE_BASE, f"_test_verrous_{uuid.uuid4().hex[:8]}")
    lang_dir = os.path.join(racine, "en")
    os.makedirs(lang_dir, exist_ok=True)
    orig = os.path.join(racine, "original.pdf")
    trad = os.path.join(lang_dir, "pages.json")          # la traduction stockée
    rendu = os.path.join(lang_dir, "rendu.pdf")          # rendu transitoire d'un job
    with open(orig, "wb") as f:
        f.write(_pdf_avec_secret())
    with open(trad, "w", encoding="utf-8") as f:
        f.write('{"pages": []}')
    with open(rendu, "wb") as f:
        f.write(_pdf_avec_secret())
    pdf = _pdf_avec_secret()

    libre, payant = _mk_user("free"), _mk_user("starter")
    async with async_session() as db:
        db.add_all([libre, payant])
        await db.commit()
        docs = {}
        for u in (libre, payant):
            d = Document(user_id=u.id, original_name="doc.pdf",
                         source_lang="auto", target_lang="en",
                         original_path=orig, translated_path=trad,
                         size_bytes=len(pdf), status="done")
            db.add(d)
            await db.commit()
            docs[u.id] = d.id
    return {"racine": racine, "orig": orig, "trad": trad, "rendu": rendu,
            "libre": libre, "payant": payant, "docs": docs}


async def _demonter(ctx):
    async with async_session() as db:
        for u in (ctx["libre"], ctx["payant"]):
            obj = await db.get(User, u.id)
            if obj:
                await db.delete(obj)
        await db.commit()
    shutil.rmtree(ctx["racine"], ignore_errors=True)


async def run():
    checks = []

    def ok(nom, cond, detail=""):
        checks.append((nom, bool(cond), detail))

    # Contexte UNIQUE : hors `with`, chaque requête ouvre puis ferme sa propre
    # boucle, et le pool global garde des connexions mortes — la 2e requête
    # explose. Le prix : le lifespan s'exécute (réconciliation des zombies +
    # balayage des partiels), c'est-à-dire exactement ce qu'un démarrage de
    # serveur ferait. Ne pas lancer cette suite pendant qu'un serveur traduit.
    with TestClient(appmod.app) as client:
        return await _run_checks(client, checks, ok)


async def _run_checks(client, checks, ok):
    # ── Porte 0 : un visiteur ne lance RIEN ────────────────────────────────
    r = client.post("/api/translate",
                    headers={"X-API-Key": appmod.FRONTEND_API_KEY},
                    files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")})
    ok("VISITEUR  /translate sans session refuse (401)", r.status_code == 401,
       f"status={r.status_code}")

    r = client.post("/api/preview/pdf",
                    headers={"X-API-Key": appmod.FRONTEND_API_KEY},
                    files={"file": ("x.docx", b"xx", "application/octet-stream")})
    ok("VISITEUR  /preview/pdf sans session refuse (401)", r.status_code == 401,
       f"status={r.status_code}")

    ctx = await _monter()
    # Le rendu à la demande est remplacé : on teste les VERROUS, pas le moteur.
    # `render_translation_bytes` renvoie un PDF porteur du secret, comme si la
    # traduction stockée avait été reconstruite.
    _vrai_rendu = appmod.render_translation_bytes
    appmod.render_translation_bytes = lambda *a, **k: _pdf_avec_secret()
    try:
        libre, payant = ctx["libre"], ctx["payant"]

        # ── Porte 1 : /documents/{id}/download ─────────────────────────────
        async with async_session() as db:
            try:
                await download_document(ctx["docs"][libre.id], libre, db)
                ok("DOWNLOAD  free sur une traduction : 402", False, "aucune exception")
            except HTTPException as e:
                ok("DOWNLOAD  free sur une traduction : 402", e.status_code == 402,
                   f"status={e.status_code}")
            rep = await download_document(ctx["docs"][payant.id], payant, db)
            ok("DOWNLOAD  starter reçoit la traduction en clair",
               SECRET in _texte(rep.body))

        # ── Porte 2 : /documents/{id}/preview ──────────────────────────────
        async with async_session() as db:
            rep = await preview_document(ctx["docs"][libre.id], libre, db)
            ok("PREVIEW  free : AUCUN mot de la traduction extractible",
               SECRET not in _texte(rep.body))
            rep = await preview_document(ctx["docs"][payant.id], payant, db)
            ok("PREVIEW  starter : la traduction reste lisible en clair",
               SECRET in _texte(rep.body))

        # ── Portes 3 et 4 : /translate/result et /partial (via jobs) ───────
        jeton_libre = create_access_token(libre.id, libre.email)
        jeton_payant = create_access_token(payant.id, payant.email)
        job_id = str(uuid.uuid4())
        appmod._jobs[job_id] = {
            "state": "done", "q": queue.Queue(),
            "result_path": ctx["rendu"], "result_filename": "doc_TRADUIT.pdf",
            "partial_path": ctx["rendu"], "error": None,
            "user_id": libre.id, "pages": None, "created_at": 0.0,
        }
        try:
            entetes = {"X-API-Key": appmod.FRONTEND_API_KEY,
                       "Authorization": f"Bearer {jeton_libre}"}
            r = client.get(f"/api/translate/result/{job_id}", headers=entetes)
            ok("RESULT  free : 402, jamais le fichier", r.status_code == 402,
               f"status={r.status_code}")

            r = client.get(f"/api/translate/partial/{job_id}", headers=entetes)
            ok("PARTIAL  free : 200 mais AUCUN mot extractible",
               r.status_code == 200 and SECRET not in _texte(r.content),
               f"status={r.status_code}")

            # Propriété : le même job vu par un AUTRE compte n'existe pas.
            autres = {"X-API-Key": appmod.FRONTEND_API_KEY,
                      "Authorization": f"Bearer {jeton_payant}"}
            r = client.get(f"/api/translate/result/{job_id}", headers=autres)
            ok("PROPRIÉTÉ  le job d'autrui répond 404", r.status_code == 404,
               f"status={r.status_code}")

            # ── SSE : le flux d'événements exige un jeton du propriétaire ──
            r = client.get(f"/api/translate/events/{job_id}")
            ok("SSE  sans jeton : 404", r.status_code == 404, f"status={r.status_code}")
            r = client.get(f"/api/translate/events/{job_id}?token={jeton_payant}")
            ok("SSE  jeton d'un autre compte : 404", r.status_code == 404,
               f"status={r.status_code}")
        finally:
            appmod._jobs.pop(job_id, None)

        # ── Freemium : formats et plafond de pages ─────────────────────────
        entetes = {"X-API-Key": appmod.FRONTEND_API_KEY,
                   "Authorization": f"Bearer {jeton_libre}"}
        r = client.post("/api/translate", headers=entetes,
                        files={"file": ("x.docx", b"PK\x03\x04",
                                        "application/octet-stream")})
        ok("FREEMIUM  un DOCX (illimitable en pages) est refusé : 402",
           r.status_code == 402, f"status={r.status_code}")

        cap = appmod.cap_pages_for_plan
        ok("CAP  PDF sans sélection, plan à 1 page : page 1 seule",
           cap(None, "pdf", 1) == {1})
        ok("CAP  PPTX sans sélection, plan à 1 page : diapo 1 seule",
           cap(None, "pptx", 1) == {1},
           "l'ancien code ne plafonnait que le PDF : deck entier traduit")
        ok("CAP  sélection trop large : réduite à la 1re page demandée",
           cap({3, 4, 5}, "pdf", 1) == {3})
        ok("CAP  plan illimité : la sélection passe intacte",
           cap({2, 7}, "pdf", 999_999) == {2, 7})

        # ── La protection mesurée, pas crue : rastériser retire le texte ───
        brut = _pdf_avec_secret()
        raster = appmod.rasterize_for_trial(brut)
        ok("RASTER  0 mot du document dans un aperçu d'essai",
           SECRET in _texte(brut) and SECRET not in _texte(raster))
    finally:
        appmod.render_translation_bytes = _vrai_rendu
        await _demonter(ctx)

    # ── Rapport ─────────────────────────────────────────────────────────────
    print()
    for nom, cond, detail in checks:
        print(f"  {'OK  ' if cond else 'ECHEC'}  {nom}"
              + (f"   [{detail}]" if detail and not cond else ""))
    passe = sum(1 for _, c, _ in checks if c)
    print(f"\n  {passe}/{len(checks)}\n")
    return 0 if passe == len(checks) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
