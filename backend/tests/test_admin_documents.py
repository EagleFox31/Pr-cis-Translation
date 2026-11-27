"""Administration des documents — liste inter-comptes et téléchargement.

Ce qui est MESURÉ :
  • un non-admin est REFUSÉ (403) par la garde `require_admin` ;
  • `list_documents` voit les documents de TOUS les comptes, avec l'e-mail du
    propriétaire, et `q` filtre sur l'e-mail OU le nom du fichier ;
  • `has_original` / `has_translation` reflètent la présence sur disque ;
  • `download_original` rend les octets d'un document d'un AUTRE utilisateur,
    avec un Content-Disposition `filename*=UTF-8''` encodé ;
  • fichier manquant, traduction absente ou document inconnu -> 404 ;
  • aperçu (`source-pdf`, `apercu`) : PDF, sans cache client, routes réservées
    à l'admin ;
  • « Créer ma copie » : fiche au nom de l'admin vers les mêmes fichiers,
    traduction propre `_d<id>`, rien de facturé, idempotente, refusée si le
    document n'est pas terminé ou déjà à l'admin, et qui survit à la
    suppression du document du client.

Exécution :  backend/venv/Scripts/python.exe backend/tests/test_admin_documents.py
Requiert PostgreSQL.
"""
from __future__ import annotations
import asyncio
import os
import shutil
import sys
import tempfile
import uuid

import racine  # noqa: F401  -- met backend/ sur le chemin

from fastapi import HTTPException                            # noqa: E402
from sqlalchemy import delete, select                        # noqa: E402
from sqlalchemy.ext.asyncio import (                         # noqa: E402
    AsyncSession, async_sessionmaker, create_async_engine,
)
from sqlalchemy.pool import NullPool                         # noqa: E402

from app.core.database import DATABASE_URL                   # noqa: E402
from app.core.security import require_admin                  # noqa: E402
from app.models import Document, User                       # noqa: E402
import app.api.admin_documents as adm                        # noqa: E402
from app.api.admin_documents import (                        # noqa: E402
    apercu_traduction, creer_copie, download_original, download_translated,
    list_documents, source_pdf,
)
from app.api.documents import STORAGE_BASE, delete_document  # noqa: E402

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
    # Le routeur doit être monté par l'application, pas seulement importé :
    # un oubli dans create_app() rendait la page admin Documents vide (404).
    from app import create_app
    chemins = {getattr(r, "path", "") for r in create_app().routes}
    check("/api/admin/documents" in chemins, "routeur monté dans l'application")

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
    check(cd.startswith("attachment; filename*=UTF-8''") and "%C3%A9" in cd and " " not in cd.split("''", 1)[-1],
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

    # ── 5. Aperçu et copie ─────────────────────────────────────────────────────
    # Le rendu PDF réel (moteur + LibreOffice) est hors sujet ici : on le
    # remplace, et on vérifie ce que ce module en fait.
    appels: list[tuple] = []

    def faux_rendu(doc, ext, trad):
        appels.append((doc.id, ext, trad))
        return b"%PDF-1.4 rendu complet"

    adm._rendu_pdf_complet = faux_rendu
    adm.convert_to_pdf_bytes = lambda data, ext, **k: b"%PDF-1.4 converti depuis " + ext.encode()

    racine_job = os.path.join(STORAGE_BASE, f"_test_admindoc_{uuid.uuid4().hex[:8]}")
    os.makedirs(os.path.join(racine_job, "en"), exist_ok=True)
    orig_job = os.path.join(racine_job, "original.docx")
    trad_job = os.path.join(racine_job, "en", "pages.json")
    json_trad = b'{"pages": [{"page_num": 1, "blocks": []}]}'
    with open(orig_job, "wb") as fh:
        fh.write(b"PK octets docx d'origine")
    with open(trad_job, "wb") as fh:
        fh.write(json_trad)

    def _client(nom: str, statut: str) -> Document:
        return Document(user_id=proprio.id, original_name=nom,
                        source_lang="fr", target_lang="en",
                        original_path=orig_job, translated_path=trad_job,
                        size_bytes=1234, storage_charged=1234, status=statut,
                        page_count=3, pages_done=3, paid=False,
                        reglages='{"precise": true}')

    d_fini = _client(f"Contrat-{TOKEN}.docx", "done")
    d_en_cours = _client(f"Cours-{TOKEN}.docx", "translating")
    d_admin = Document(user_id=admin.id, original_name=f"Mien-{TOKEN}.docx",
                       source_lang="fr", target_lang="en", original_path=orig_job,
                       translated_path=trad_job, size_bytes=1, status="done")
    async with async_session() as db:
        db.add_all([d_fini, d_en_cours, d_admin])
        await db.commit()
        id_fini, id_en_cours, id_admin = d_fini.id, d_en_cours.id, d_admin.id

    def _garde_admin(chemin: str, methode: str) -> bool:
        for r in create_app().routes:
            if getattr(r, "path", "") == chemin and methode in getattr(r, "methods", ()):
                return any(d.call is require_admin for d in r.dependant.dependencies)
        return False

    for chemin, methode in (("/api/admin/documents/{doc_id}/source-pdf", "GET"),
                            ("/api/admin/documents/{doc_id}/apercu", "GET"),
                            ("/api/admin/documents/{doc_id}/copie", "POST")):
        check(_garde_admin(chemin, methode), f"{methode} {chemin.rsplit('/', 1)[-1]} réservé à l'admin")

    async with async_session() as db:
        r = await apercu_traduction(id_fini, admin=admin, db=db)
    check(r.status_code == 200 and r.media_type == "application/pdf"
          and r.headers.get("cache-control") == "no-store"
          and r.body == b"%PDF-1.4 rendu complet",
          "apercu : 200, PDF, sans cache client")
    check(appels == [(id_fini, "docx", trad_job)], "apercu : rendu complet de la traduction du client")
    async with async_session() as db:
        check(await _statut(apercu_traduction(id_manquant, admin=admin, db=db)) == 404,
              "apercu sans traduction -> 404")

    async with async_session() as db:
        r = await source_pdf(id_fini, admin=admin, db=db)
    check(r.status_code == 200 and r.media_type == "application/pdf"
          and r.body == b"%PDF-1.4 converti depuis docx"
          and r.headers.get("cache-control") == "no-store",
          "source-pdf : original converti en PDF")
    async with async_session() as db:
        r = await source_pdf(id_ok, admin=admin, db=db)
    check(r.status_code == 200 and r.body == CONTENU, "source-pdf : un PDF est servi tel quel")
    async with async_session() as db:
        check(await _statut(source_pdf(id_manquant, admin=admin, db=db)) == 404,
              "source-pdf : fichier manquant -> 404")

    # Copie : refus
    async with async_session() as db:
        check(await _statut(creer_copie(id_en_cours, admin=admin, db=db)) == 409,
              "copie d'un document non terminé -> 409")
    async with async_session() as db:
        check(await _statut(creer_copie(id_admin, admin=admin, db=db)) == 400,
              "copie d'un document déjà à l'admin -> 400")
    async with async_session() as db:
        check(await _statut(creer_copie("inconnu-" + TOKEN, admin=admin, db=db)) == 404,
              "copie d'un document inconnu -> 404")

    # Copie : création
    async with async_session() as db:
        rep = await creer_copie(id_fini, admin=admin, db=db)
    check(rep["cree"] is True and rep["id"] not in (id_fini, id_admin), "copie créée : nouvel identifiant")
    async with async_session() as db:
        c = await db.get(Document, rep["id"])
        client = await db.get(Document, id_fini)
    check(c.user_id == admin.id and c.copie_de == id_fini, "la copie est à l'admin et garde l'origine")
    check(c.storage_charged == 0 and c.paid is True and c.status == "done",
          "rien de facturé, lisible en clair, terminée")
    check(c.original_path == orig_job and c.original_name == client.original_name
          and c.page_count == 3 and c.reglages == client.reglages
          and (c.source_lang, c.target_lang) == ("fr", "en"),
          "mêmes fichiers d'origine et mêmes réglages")
    check(c.translated_path != trad_job and f"_d{c.id[:12]}" in c.translated_path
          and os.path.isfile(c.translated_path), "traduction propre à la copie (_d<id>)")
    check(client.translated_path == trad_job and client.status == "done"
          and client.storage_charged == 1234 and client.user_id == proprio.id,
          "le document du client n'est pas modifié")
    with open(trad_job, "rb") as fh:
        check(fh.read() == json_trad, "traduction du client inchangée octet pour octet")
    with open(c.translated_path, "rb") as fh:
        check(fh.read() == json_trad, "traduction de la copie identique à l'instant T")

    # Copie : idempotence
    async with async_session() as db:
        rep2 = await creer_copie(id_fini, admin=admin, db=db)
        nb = len((await db.execute(select(Document.id).where(
            Document.copie_de == id_fini))).scalars().all())
    check(rep2 == {"id": rep["id"], "cree": False} and nb == 1,
          "seconde demande : même copie, rien de recréé")

    # Copie d'une copie : refusée (demandeur autre que son propriétaire, pour
    # passer la garde « déjà à vous » ; la route est appelée en direct).
    async with async_session() as db:
        check(await _statut(creer_copie(rep["id"], admin=proprio, db=db)) == 400,
              "copie d'une copie d'admin -> 400")

    async with async_session() as db:
        res = await list_documents(q=f"Contrat-{TOKEN}", _admin=admin, db=db)
    liens = {d["id"]: d["copie_de"] for d in res["items"]}
    check(liens.get(rep["id"]) == id_fini and liens.get(id_fini) is None,
          "la liste expose copie_de")

    # Le client supprime son document : la copie garde ses fichiers.
    async with async_session() as db:
        u = await db.get(User, proprio.id)
        await delete_document(id_fini, user=u, db=db)
    async with async_session() as db:
        c = await db.get(Document, rep["id"])
        gone = await db.get(Document, id_fini)
    check(gone is None and os.path.isfile(c.original_path) and os.path.isfile(c.translated_path),
          "suppression du document client : la copie garde ses fichiers")

    # ── Nettoyage ─────────────────────────────────────────────────────────────
    shutil.rmtree(racine_job, ignore_errors=True)
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
