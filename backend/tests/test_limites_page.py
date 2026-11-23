"""Limites par page de l'extension (étude extension-gratuite-forfaits).

  • les bornes de chaque forfait (entreprise et admin comme Pro, inconnu comme Gratuit) ;
  • compteurs permanents en base : cumul sur une même page, accord partiel quand
    la limite tombe au milieu d'une demande, refus ensuite ;
  • Starter plus large, Pro illimité, passage de forfait relève la limite ;
  • pages par jour : la page suivante est refusée, une page déjà commencée ne l'est
    jamais, les pages d'un autre jour ne comptent pas, créations simultanées sous verrou ;
  • `rendre` retranche (plancher 0) et efface la ligne revenue à zéro ;
  • `verifier` ne compte rien ;
  • bornes techniques en mémoire (lots, analyses, captures) ; identifiant de page nettoyé.

Exécution :  backend/venv/Scripts/python.exe backend/tests/test_limites_page.py
Requiert PostgreSQL.
"""
from __future__ import annotations
import asyncio
import sys
import uuid
from datetime import timedelta

import racine  # noqa: F401  -- met backend/ sur le chemin

from sqlalchemy import func, select, update                # noqa: E402
from sqlalchemy.ext.asyncio import (                       # noqa: E402
    create_async_engine, async_sessionmaker, AsyncSession,
)
from sqlalchemy.pool import NullPool                       # noqa: E402

from app.core.database import DATABASE_URL                 # noqa: E402
from app.models import ExtensionUsage, User, utcnow        # noqa: E402
from app.services import limites_page as lp                # noqa: E402

_eng = create_async_engine(DATABASE_URL, poolclass=NullPool)
async_session = async_sessionmaker(_eng, class_=AsyncSession, expire_on_commit=False)


async def _compte(plan: str) -> str:
    async with async_session() as db:
        u = User(email=f"lim-{uuid.uuid4().hex[:10]}@example.com", plan=plan,
                 email_verified=True)
        db.add(u)
        await db.commit()
        return u.id


async def _supprimer(uid: str):
    async with async_session() as db:
        u = await db.get(User, uid)
        if u:
            await db.delete(u)
        await db.commit()


async def _reserver(uid, page, **k):
    async with async_session() as db:
        user = await db.get(User, uid)
        return await lp.reserver(db, user, page, **k)


async def _rendre(uid, page, **k):
    async with async_session() as db:
        await lp.rendre(db, uid, page, **k)


async def _verifier(uid, page, **k):
    async with async_session() as db:
        user = await db.get(User, uid)
        return await lp.verifier(db, user, page, **k)


async def _ligne(uid, page):
    async with async_session() as db:
        return await db.get(ExtensionUsage, (uid, page))


async def _nb_lignes(uid):
    async with async_session() as db:
        return (await db.execute(select(func.count()).select_from(ExtensionUsage).where(
            ExtensionUsage.user_id == uid))).scalar_one()


def _avec_compte(plan):
    """Exécute la fonction async avec un compte du forfait, supprimé ensuite."""
    def deco(f):
        def test():
            async def run():
                uid = await _compte(plan)
                try:
                    await f(uid)
                finally:
                    await _supprimer(uid)
            asyncio.run(run())
        test.__name__ = f.__name__
        return test
    return deco


def test_bornes_des_forfaits():
    assert lp.bornes("free") == {"texte": 30_000, "images": 30, "texte_image": 2_000, "pages_jour": 30}
    assert lp.bornes("starter")["texte"] == 100_000 and lp.bornes("starter")["images"] == 80
    assert lp.bornes("starter")["texte_image"] == 4_000 and lp.bornes("starter")["pages_jour"] == 150
    pro = lp.bornes("pro")
    assert pro["texte"] is None and pro["images"] is None and pro["texte_image"] is None
    assert pro["pages_jour"] == 500
    assert lp.bornes("enterprise") == pro and lp.bornes("admin") == pro
    assert lp.bornes("inconnu") == lp.bornes("free") == lp.bornes(None)


def test_cle_page():
    assert lp.cle_page(None) == ""
    assert lp.cle_page("ab-12/../x y") == "ab-12xy"
    assert len(lp.cle_page("a" * 500)) == lp.ID_MAX


def test_bornes_techniques():
    lp.reinitialiser()
    for _ in range(lp.LOTS_MAX):
        assert lp.prendre("u1", "q", lots=1) is None
    assert lp.prendre("u1", "q", lots=1) == "lots"
    # Refus sans rien compter ; les autres bornes de la page restent libres.
    assert lp._compteurs[("u1", "q")]["lots"] == lp.LOTS_MAX
    assert lp.prendre("u1", "q", analyses=1) is None
    for _ in range(lp.ANALYSES_MAX - 1):
        assert lp.prendre("u1", "q", analyses=1) is None
    assert lp.prendre("u1", "q", analyses=1) == "analyses"
    for _ in range(lp.CAPTURES_MAX):
        assert lp.prendre("u1", "p", captures=1) is None
    assert lp.prendre("u1", "p", captures=1) == "captures"
    # Autre page, autre utilisateur : budgets neufs.
    assert lp.prendre("u1", "autre", lots=1) is None
    assert lp.prendre("u2", "q", lots=1) is None
    assert "texte" not in lp.BORNES and "images" not in lp.BORNES


@_avec_compte("free")
async def test_cumul_texte_jusqu_a_la_limite(uid):
    assert await _reserver(uid, "p1", texte=20_000) == (20_000, 0, None)
    # Accord partiel : le reste de la limite, et le nom de la limite atteinte.
    assert await _reserver(uid, "p1", texte=20_000) == (10_000, 0, "texte")
    assert await _reserver(uid, "p1", texte=5) == (0, 0, "texte")
    assert (await _ligne(uid, "p1")).caracteres == 30_000
    # Autre page : compteur neuf.
    assert await _reserver(uid, "p2", texte=100) == (100, 0, None)


@_avec_compte("free")
async def test_images_et_texte_separes(uid):
    for _ in range(30):
        assert await _reserver(uid, "p", images=1) == (0, 1, None)
    assert await _reserver(uid, "p", images=1) == (0, 0, "images")
    # Le texte de la page reste libre.
    assert await _reserver(uid, "p", texte=10) == (10, 0, None)
    # Les deux dans la même demande : « texte » est cité en premier.
    assert await _reserver(uid, "p", texte=40_000, images=1) == (29_990, 0, "texte")
    l = await _ligne(uid, "p")
    assert (l.caracteres, l.images) == (30_000, 30)


@_avec_compte("free")
async def test_rien_accorde_ne_cree_pas_de_ligne(uid):
    assert await _reserver(uid, "vide") == (0, 0, None)
    assert await _ligne(uid, "vide") is None
    assert await _reserver(uid, "vide", texte=0, images=0) == (0, 0, None)
    assert await _nb_lignes(uid) == 0


@_avec_compte("starter")
async def test_starter(uid):
    assert await _reserver(uid, "p", texte=100_000) == (100_000, 0, None)
    assert await _reserver(uid, "p", texte=1) == (0, 0, "texte")
    assert await _reserver(uid, "p", images=80) == (0, 80, None)
    assert await _reserver(uid, "p", images=1) == (0, 0, "images")


@_avec_compte("pro")
async def test_pro_illimite(uid):
    assert await _reserver(uid, "p", texte=500_000, images=200) == (500_000, 200, None)
    assert await _reserver(uid, "p", texte=500_000, images=200) == (500_000, 200, None)
    assert await _verifier(uid, "p", images=True) is None


@_avec_compte("free")
async def test_passage_de_forfait_releve_la_limite(uid):
    assert await _reserver(uid, "p", texte=30_000) == (30_000, 0, None)
    assert await _reserver(uid, "p", texte=10) == (0, 0, "texte")
    async with async_session() as db:
        await db.execute(update(User).where(User.id == uid).values(plan="starter"))
        await db.commit()
    assert await _reserver(uid, "p", texte=10) == (10, 0, None)


@_avec_compte("free")
async def test_pages_par_jour(uid):
    for i in range(30):
        assert await _reserver(uid, f"p{i}", texte=1) == (1, 0, None)
    assert await _reserver(uid, "p30", texte=1) == (0, 0, "pages_jour")
    assert await _ligne(uid, "p30") is None
    assert await _verifier(uid, "p30") == "pages_jour"
    # Une page déjà commencée n'est pas une page nouvelle.
    assert await _reserver(uid, "p0", texte=5) == (5, 0, None)
    assert await _verifier(uid, "p0", images=True) is None
    # Même une demande d'image sur la page commencée passe.
    assert await _reserver(uid, "p0", images=1) == (0, 1, None)
    # Pages commencées hier : elles ne comptent plus aujourd'hui, mais restent
    # connues (jamais « nouvelles ») et gardent leurs compteurs.
    hier = utcnow().date() - timedelta(days=1)
    async with async_session() as db:
        await db.execute(update(ExtensionUsage).where(ExtensionUsage.user_id == uid)
                         .values(jour=hier))
        await db.commit()
    assert await _reserver(uid, "p30", texte=1) == (1, 0, None)
    assert await _reserver(uid, "p1", texte=1) == (1, 0, None)
    assert (await _ligne(uid, "p1")).caracteres == 2


@_avec_compte("free")
async def test_creations_simultanees(uid):
    # 40 pages différentes en même temps : le verrou n'en laisse passer que 30.
    res = await asyncio.gather(*(_reserver(uid, f"s{i}", texte=1) for i in range(40)))
    assert sum(1 for r in res if r[2] is None) == 30, res
    assert sum(1 for r in res if r[2] == "pages_jour") == 10
    assert await _nb_lignes(uid) == 30


@_avec_compte("free")
async def test_rendre(uid):
    await _reserver(uid, "p", texte=100, images=2)
    await _rendre(uid, "p", texte=40)
    l = await _ligne(uid, "p")
    assert (l.caracteres, l.images) == (60, 2)
    # Plancher à 0 ; la ligne n'est effacée que lorsque tout est à zéro.
    await _rendre(uid, "p", texte=500, images=1)
    l = await _ligne(uid, "p")
    assert (l.caracteres, l.images) == (0, 1)
    await _rendre(uid, "p", images=1)
    assert await _ligne(uid, "p") is None
    # Page inconnue : sans effet.
    await _rendre(uid, "inconnue", texte=5, images=5)
    assert await _nb_lignes(uid) == 0


@_avec_compte("free")
async def test_rendre_libere_la_page_du_jour(uid):
    for i in range(30):
        await _reserver(uid, f"p{i}", images=1)
    assert await _verifier(uid, "neuve") == "pages_jour"
    await _rendre(uid, "p0", images=1)
    assert await _verifier(uid, "neuve") is None


@_avec_compte("free")
async def test_verifier_ne_compte_rien(uid):
    assert await _verifier(uid, "p", images=True) is None
    assert await _nb_lignes(uid) == 0
    await _reserver(uid, "p", images=30)
    assert await _verifier(uid, "p") is None
    assert await _verifier(uid, "p", images=True) == "images"
    assert (await _ligne(uid, "p")).images == 30
    # Le texte n'entre pas dans la vérification.
    await _reserver(uid, "t", texte=30_000)
    assert await _verifier(uid, "t", images=True) is None


@_avec_compte("free")
async def test_utilisateurs_independants(uid):
    autre = await _compte("free")
    try:
        assert await _reserver(uid, "p", texte=30_000) == (30_000, 0, None)
        assert await _reserver(autre, "p", texte=30_000) == (30_000, 0, None)
    finally:
        await _supprimer(autre)


if __name__ == "__main__":
    echecs = 0
    for nom, f in list(globals().items()):
        if nom.startswith("test_"):
            try:
                f()
                print(f"OK   {nom}")
            except AssertionError as e:
                echecs += 1
                print(f"ÉCHEC {nom} {e}")
    print(f"\n  {'ÉCHECS : ' + str(echecs) if echecs else 'tout passe'}")
    sys.exit(1 if echecs else 0)
