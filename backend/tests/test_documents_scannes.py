"""Documents scannés — on ne facture jamais une page qu'on n'a pas lue.

LE DÉFAUT VERROUILLÉ ICI
------------------------
Un PDF scanné est une suite d'IMAGES : aucun caractère n'y est extractible. Le
moteur n'en tire rien et rend le document INCHANGÉ. La facturation, elle,
comptait les pages du conteneur.

MESURÉ avant correctif, sur le scan synthétique de cette suite :
    3 pages débitées  ·  0 élément de texte extrait  ·  document rendu tel quel
L'utilisateur payait, recevait son fichier inchangé, et son crédit avait
disparu — sans un mot, ni pour lui, ni dans le journal.

CE QUI EST MESURÉ
-----------------
1. La détection elle-même, sur des PDF SYNTHÉTIQUES fabriqués ici (jamais sur
   un document réel qui aurait révélé le défaut) : un scan pur, un document
   texte, un document MIXTE. La règle est « aucun caractère extractible » —
   pas un seuil calé sur les documents qu'on a sous la main.
2. Que le document mixte ne perd RIEN : les pages écartées de la traduction
   sont copiées telles quelles par le moteur, pas supprimées. C'est ce qui rend
   le correctif acceptable — on facture moins sans livrer moins.
3. Que la détection est bon marché : elle tourne sur chaque envoi.

    backend/venv/Scripts/python.exe backend/tests/test_documents_scannes.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import time

import racine  # noqa: F401  -- met backend/ sur le chemin

import fitz                                                    # noqa: E402

from app.services.documents import (count_pages,               # noqa: E402
                                    pages_avec_texte)

_checks: list[tuple[bool, str]] = []


def check(cond: bool, label: str, detail: str = "") -> None:
    _checks.append((bool(cond), label))
    print(f"  {'OK  ' if cond else 'ECHEC'} {label}"
          + (f"   [{detail}]" if detail and not cond else ""))


# ── Fabriques de documents SYNTHÉTIQUES ──────────────────────────────────────

def _page_texte(doc, titre: str) -> None:
    p = doc.new_page(width=595, height=842)
    p.insert_text((72, 100), titre, fontsize=20, fontname="helv")
    p.insert_text((72, 140), "Une ligne de contenu parfaitement lisible.",
                  fontsize=12, fontname="helv")


def pdf_texte(pages: int = 3) -> bytes:
    doc = fitz.open()
    for i in range(pages):
        _page_texte(doc, f"Chapitre {i + 1}")
    out = doc.tobytes()
    doc.close()
    return out


def pdf_scanne(pages: int = 3) -> bytes:
    """Le texte est DESSINÉ puis rasterisé : visible à l'œil, absent des
    caractères. C'est exactement ce que produit un scanner."""
    src = fitz.open()
    for i in range(pages):
        _page_texte(src, f"Chapitre {i + 1}")
    out = fitz.open()
    for page in src:
        pix = page.get_pixmap(dpi=100)
        np = out.new_page(width=page.rect.width, height=page.rect.height)
        np.insert_image(np.rect, pixmap=pix)
    octets = out.tobytes()
    out.close()
    src.close()
    return octets


def pdf_mixte() -> bytes:
    """Page 1 scannée (couverture photographiée), pages 2-3 en texte — le cas
    courant d'un rapport dont seule la couverture est une image."""
    src = fitz.open()
    _page_texte(src, "Couverture")
    out = fitz.open()
    pix = src[0].get_pixmap(dpi=100)
    p = out.new_page(width=src[0].rect.width, height=src[0].rect.height)
    p.insert_image(p.rect, pixmap=pix)
    _page_texte(out, "Chapitre 1")
    _page_texte(out, "Chapitre 2")
    octets = out.tobytes()
    out.close()
    src.close()
    return octets


def main() -> int:
    # ── 1. Détection ────────────────────────────────────────────────────────
    print("\n1. Detection sur documents synthetiques")

    scan = pdf_scanne(3)
    check(pages_avec_texte(scan, "pdf") == set(),
          "scan pur : AUCUNE page lisible",
          str(pages_avec_texte(scan, "pdf")))
    check(count_pages(scan, "pdf") == 3,
          "scan pur : le conteneur compte pourtant bien 3 pages "
          "(c'est ce decalage qui facturait le vide)")

    texte = pdf_texte(3)
    check(pages_avec_texte(texte, "pdf") == {1, 2, 3},
          "document texte : les 3 pages sont lisibles",
          str(pages_avec_texte(texte, "pdf")))

    mixte = pdf_mixte()
    check(pages_avec_texte(mixte, "pdf") == {2, 3},
          "document mixte : seules les pages 2 et 3 sont lisibles",
          str(pages_avec_texte(mixte, "pdf")))

    # ── 2. Ce que l'endpoint en DÉDUIT (la logique de facturation) ──────────
    print("\n2. Pages facturees, telle que l'endpoint les calcule")

    def facturees(octets: bytes, demande: set[int] | None):
        """Reproduit le calcul de `translate_endpoint` : intersection de ce qui
        est visé avec ce qui est lisible. Rend None si tout est refuse."""
        lisibles = pages_avec_texte(octets, "pdf")
        visees = demande or set(range(1, count_pages(octets, "pdf") + 1))
        traduisibles = visees & lisibles
        return None if not traduisibles else len(traduisibles)

    check(facturees(scan, None) is None,
          "scan pur : REFUS, zero page debitee")
    check(facturees(texte, None) == 3,
          "document texte : 3 pages facturees (aucune regression)")
    check(facturees(mixte, None) == 2,
          "document mixte : 2 pages facturees au lieu de 3",
          str(facturees(mixte, None)))
    check(facturees(mixte, {1}) is None,
          "mixte, page scannee demandee SEULE : refus, rien debite")
    check(facturees(mixte, {1, 2}) == 1,
          "mixte, pages 1-2 demandees : seule la page 2 est facturee")

    # ── 3. Le document mixte ne PERD rien ───────────────────────────────────
    #
    # C'est la condition qui rend le correctif acceptable. Si écarter une page
    # de la traduction la faisait disparaître du résultat, on facturerait moins
    # en livrant moins — un autre défaut, pas une correction.
    print("\n3. Les pages ecartees sont COPIEES, jamais supprimees")

    from engines.pdf.stream import translate_pdf_progressive
    tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "_generic_tmp")
    os.makedirs(tmp, exist_ok=True)
    src_path = os.path.join(tmp, "mixte.pdf")
    out_path = os.path.join(tmp, "mixte_sortie.pdf")
    with open(src_path, "wb") as f:
        f.write(mixte)

    # `debug=True` : le moteur parcourt tout le pipeline SANS appeler le modèle
    # (aucun réseau, aucun coût). Ce qu'on mesure ici est la structure du
    # document produit, pas la qualité de la traduction.
    translate_pdf_progressive(src_path, out_path, target_lang="en",
                              pages={2, 3}, debug=True)

    with fitz.open(out_path) as res:
        check(res.page_count == 3,
              "le document rendu garde ses 3 pages",
              f"{res.page_count} page(s)")
        img_p1 = len(res[0].get_images())
        check(img_p1 >= 1,
              "la page scannee est toujours la, avec son image",
              f"{img_p1} image(s)")

    # ── 4. Coût de la détection ─────────────────────────────────────────────
    #
    # Elle tourne sur CHAQUE envoi, avant tout le reste. Si elle était chère,
    # on l'aurait payée sur tous les documents pour n'en sauver que quelques-uns.
    print("\n4. Coût")
    gros = pdf_texte(60)
    t0 = time.perf_counter()
    pages_avec_texte(gros, "pdf")
    ms = (time.perf_counter() - t0) * 1000
    check(ms < 1000, f"60 pages analysees en {ms:.0f} ms (< 1 s)", f"{ms:.0f} ms")

    # ── 5. Les autres formats ne sont pas concernés ─────────────────────────
    print("\n5. Portee")
    check(pages_avec_texte(b"nimporte quoi", "pptx") is None,
          "un PPTX n'est pas analyse (None = question sans objet)")
    check(pages_avec_texte(b"pas un pdf du tout", "pdf") is None,
          "un PDF illisible ne pretend RIEN (None, pas 'aucune page')")

    # ── 6. LA promesse : l'endpoint ne débite RIEN ──────────────────────────
    #
    # Les sections précédentes mesurent un calcul. Celle-ci mesure l'ARGENT :
    # on appelle la vraie route, avec un vrai compte, et on regarde le solde
    # avant et après. C'est ce contrôle qui tombera si quelqu'un déplace un
    # jour la détection APRÈS le débit — l'ordre est toute la correction.
    print("\n6. Endpoint reel : le solde de pages est-il preserve ?")
    code = asyncio.run(_verifier_endpoint(scan))
    return code


async def _verifier_endpoint(scan: bytes) -> int:
    import io
    import uuid
    from datetime import datetime, timezone

    from fastapi import UploadFile
    from sqlalchemy import select

    from app import config as cfg
    from app.api.translate import translate_endpoint
    from app.core.database import async_session
    from app.models import Document, User

    email = f"scan-{uuid.uuid4().hex[:10]}@essai.test"
    async with async_session() as db:
        # Un compte gratuit qui a DÉJÀ consommé sa traduction offerte du mois
        # (sinon la route emprunte la branche « offerte », qui ne débite rien —
        # et le test passerait sans rien prouver).
        u = User(email=email, name="Essai scan", plan="free",
                 email_verified=True, page_credits=25)
        db.add(u)
        await db.flush()
        db.add(Document(user_id=u.id, original_name="deja.pdf",
                        source_lang="fr", target_lang="en",
                        original_path="/inexistant/deja.pdf", size_bytes=1,
                        status="done", page_count=1,
                        created_at=datetime.now(timezone.utc)))
        await db.commit()
        uid, solde_avant = u.id, u.page_credits

        televerse = UploadFile(filename="scan.pdf", file=io.BytesIO(scan))
        reponse = await translate_endpoint(
            request=None, file=televerse, target_lang="en",
            format_options="{}", quality="fast", precise="", pages="",
            debug="", x_api_key=cfg.FRONTEND_API_KEY,
            current_user=u, db=db)

        check(getattr(reponse, "status_code", None) == 422,
              "un scan pur est REFUSE (422)",
              str(getattr(reponse, "status_code", reponse)))

        import json as _json
        corps = _json.loads(bytes(reponse.body).decode())
        check(corps.get("reason") == "scanned_document",
              "le motif est au PREMIER niveau, comme pour need_credits",
              str(list(corps)))
        check(isinstance(corps.get("detail"), str),
              "`detail` est un TEXTE affichable, pas un objet "
              "(sinon l'interface montre « [object Object] »)",
              type(corps.get("detail")).__name__)

        apres = (await db.execute(
            select(User.page_credits).where(User.id == uid))).scalar()
        check(apres == solde_avant,
              f"le solde est INTACT : {solde_avant} -> {apres}",
              f"{solde_avant} -> {apres}")

        # Ménage : ce compte d'essai n'a rien à faire dans la base.
        doc_ids = (await db.execute(
            select(Document.id).where(Document.user_id == uid))).scalars().all()
        for d in doc_ids:
            await db.delete(await db.get(Document, d))
        await db.delete(await db.get(User, uid))
        await db.commit()

    # ── Verdict ─────────────────────────────────────────────────────────────
    passed = sum(1 for ok, _ in _checks if ok)
    total = len(_checks)
    print(f"\n{passed}/{total} controles")
    if passed != total:
        print("ECHECS :", [lbl for ok, lbl in _checks if not ok])
        return 1
    print("OK - aucune page non lue n'est facturee")
    return 0


if __name__ == "__main__":
    sys.exit(main())
