"""Anti-abus des pages offertes : cookie signé, appareil, boîte e-mail, vélocité IP.

Aucun fournisseur de traduction n'est appelé : seul le worker est remplacé.
"""
from datetime import datetime, timedelta, timezone
import unittest
import uuid

import test_beta_program as fixtures  # pose JWT_SECRET et les variables d'environnement
from fastapi import Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.models import DeviceLink, FreeGrant, User
from app.models.base import Base
from app.services import anti_abus, usage
from app.services.beta_abuse import canonical_mailbox


def requete(peer="198.51.100.10", cookie=None, headers=None, forwarded=None):
    entetes = [(name.lower().encode(), value.encode()) for name, value in (headers or {}).items()]
    if cookie:
        entetes.append((b"cookie", (anti_abus.COOKIE_NAME + "=" + cookie).encode()))
    if forwarded:
        entetes += [(b"x-forwarded-for", forwarded.encode()), (b"x-real-ip", forwarded.encode())]
    return Request({"type": "http", "headers": entetes, "client": (peer, 1234)})


def signaux(cookie="c", copie=None, empreinte=None, ip="ip-1"):
    """Signaux fabriqués à la main, hachés comme le fait le service."""
    return anti_abus.DeviceSignals(
        ip_hash=ip, cookie_hash=anti_abus._digest("cookie", cookie),
        copy_hash=anti_abus._digest("copy", copie) if copie else None,
        print_hash=anti_abus._digest("print", empreinte) if empreinte else None)


class SignauxTests(unittest.TestCase):
    def test_cookie_signe_accepte_et_cookie_falsifie_remplace(self):
        premier = anti_abus.client_signals(requete())
        self.assertIsNotNone(premier.new_cookie)
        # Le même cookie présenté ensuite est reconnu, sans nouveau cookie.
        suite = anti_abus.client_signals(requete(cookie=premier.new_cookie))
        self.assertIsNone(suite.new_cookie)
        self.assertEqual(suite.cookie_hash, premier.cookie_hash)
        # Signature modifiée, signature absente, format invalide : nouveau cookie.
        nonce, signature = premier.new_cookie.split(".")
        autre_nonce = anti_abus.client_signals(requete()).new_cookie.split(".")[0]
        for faux in (nonce + "." + "0" * 64, autre_nonce + "." + signature, nonce,
                     "n'importe quoi"):
            with self.subTest(faux=faux):
                resultat = anti_abus.client_signals(requete(cookie=faux))
                self.assertIsNotNone(resultat.new_cookie)
                self.assertNotEqual(resultat.cookie_hash, premier.cookie_hash)

    def test_cookie_pose_httponly_sur_le_chemin_api(self):
        signals = anti_abus.client_signals(requete())
        reponse = Response()
        anti_abus.set_cookie(reponse, signals)
        pose = reponse.headers["set-cookie"]
        self.assertIn(anti_abus.COOKIE_NAME + "=", pose)
        self.assertIn("HttpOnly", pose)
        self.assertIn("Path=/api", pose)
        self.assertEqual(reponse.headers["cache-control"], "private, no-store")
        # Cookie déjà valide : aucun Set-Cookie.
        reconnu = anti_abus.client_signals(requete(cookie=signals.new_cookie))
        autre = Response()
        anti_abus.set_cookie(autre, reconnu)
        self.assertNotIn("set-cookie", autre.headers)

    def test_en_tetes_invalides_ignores_et_valides_haches(self):
        for valeur in ("court", "contient des espaces!", "x" * 129, "é" * 10, ""):
            with self.subTest(valeur=valeur):
                resultat = anti_abus.client_signals(requete(headers={
                    "X-Device-Copy": valeur, "X-Device-Print": valeur}))
                self.assertIsNone(resultat.copy_hash)
                self.assertIsNone(resultat.print_hash)
        valide = anti_abus.client_signals(requete(headers={
            "X-Device-Copy": "copie-locale_01", "X-Device-Print": "A" * 64}))
        self.assertEqual(valide.copy_hash, anti_abus._digest("copy", "copie-locale_01"))
        self.assertEqual(valide.print_hash, anti_abus._digest("print", "A" * 64))
        self.assertNotIn("copie-locale_01", valide.copy_hash)

    def test_ip_vient_du_pair_jamais_de_x_forwarded_for(self):
        seul = anti_abus.client_signals(requete(peer="198.51.100.10"))
        usurpe = anti_abus.client_signals(requete(peer="198.51.100.10", forwarded="203.0.113.99"))
        autre = anti_abus.client_signals(requete(peer="198.51.100.11"))
        self.assertEqual(seul.ip_hash, usurpe.ip_hash)
        self.assertNotEqual(seul.ip_hash, autre.ip_hash)
        self.assertIsNone(anti_abus.client_signals(requete(peer="pas-une-ip")).ip_hash)

    def test_ipv6_regroupee_par_prefixe_64(self):
        ip = lambda peer: anti_abus.client_signals(requete(peer=peer)).ip_hash
        # Changer d'adresse dans son /64 ne contourne pas les limites par IP.
        self.assertEqual(ip("2001:db8:1:2::1"), ip("2001:db8:1:2:ffff::9"))
        self.assertNotEqual(ip("2001:db8:1:2::1"), ip("2001:db8:1:3::1"))
        # Une IPv4 encapsulée en IPv6 reste l'IPv4.
        self.assertEqual(ip("::ffff:198.51.100.10"), ip("198.51.100.10"))


class DomainesTests(unittest.TestCase):
    def test_domaines_jetables(self):
        for adresse in ("x@mailinator.com", "x@Mailinator.COM ", "x@sous.mailinator.com"):
            with self.subTest(adresse=adresse):
                self.assertTrue(anti_abus.is_disposable(adresse))
        for adresse in ("x@gmail.com", "x@googlemail.com", "x@trigenys.com", "sans-arobase", ""):
            with self.subTest(adresse=adresse):
                self.assertFalse(anti_abus.is_disposable(adresse))
        with self.assertRaises(Exception) as contexte:
            anti_abus.reject_disposable("x@mailinator.com")
        self.assertEqual(contexte.exception.status_code, 400)
        anti_abus.reject_disposable("x@gmail.com")

    def test_boite_canonique_etendue(self):
        self.assertEqual(canonical_mailbox("Jane+a@Outlook.com"), "jane@outlook.com")
        self.assertEqual(canonical_mailbox("jane+a@icloud.com"), "jane@icloud.com")
        self.assertEqual(canonical_mailbox("jane+a@proton.me"), "jane@proton.me")
        self.assertEqual(canonical_mailbox("jane-promo@yahoo.com"), "jane@yahoo.com")
        self.assertEqual(canonical_mailbox("j.a.n.e+a@gmail.com"), "jane@gmail.com")
        self.assertEqual(canonical_mailbox("jane+a@trigenys.com"), "jane+a@trigenys.com")
        self.assertEqual(anti_abus.mailbox_key("jane+a@outlook.com"),
                         anti_abus.mailbox_key("JANE@outlook.com"))


class BaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite://")
        async with self.engine.begin() as connexion:
            await connexion.run_sync(Base.metadata.create_all)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def compte(self, db, email=None, ancien=True, **champs):
        user = User(email=email or f"anti-{uuid.uuid4().hex[:10]}@example.com", plan="free",
                    email_verified=True,
                    created_at=datetime.now(timezone.utc) - timedelta(days=3 if ancien else 0),
                    **champs)
        db.add(user)
        await db.flush()
        return user

    async def attribuer(self, db, user, machine="m1", ip="ip-1", pages=1, il_y_a=timedelta(0)):
        db.add(FreeGrant(user_id=user.id, machine_id=machine, ip_hash=ip, pages=pages,
                         mailbox_key=anti_abus.mailbox_key(user.email),
                         created_at=datetime.now(timezone.utc) - il_y_a))
        await db.flush()


class MachineTests(BaseTests):
    async def test_machine_connue_au_second_passage(self):
        async with self.sessions() as db:
            machine, connue = await anti_abus.resolve_machine(db, signaux("a"))
            self.assertFalse(connue)
            suite, connue = await anti_abus.resolve_machine(db, signaux("a"))
            self.assertTrue(connue)
            self.assertEqual(suite, machine)
            # Cookie effacé mais copie locale conservée : même machine retrouvée.
            await anti_abus.resolve_machine(db, signaux("a", copie="copie-0001"))
            retrouvee, connue = await anti_abus.resolve_machine(db, signaux("neuf", copie="copie-0001"))
            self.assertTrue(connue)
            self.assertEqual(retrouvee, machine)
            await db.commit()

    async def test_fusion_la_plus_ancienne_l_emporte(self):
        passe = datetime.now(timezone.utc) - timedelta(days=5)
        async with self.sessions() as db:
            ancienne, _ = await anti_abus.resolve_machine(db, signaux("a"), now=passe)
            recente, _ = await anti_abus.resolve_machine(
                db, signaux("b", copie="copie-b001"), now=passe + timedelta(days=1))
            self.assertNotEqual(ancienne, recente)
            utilisateur = await self.compte(db)
            await self.attribuer(db, utilisateur, machine=recente)
            # Une requête qui porte le cookie de A et la copie de B les relie.
            fusion, connue = await anti_abus.resolve_machine(
                db, signaux("a", copie="copie-b001"))
            self.assertTrue(connue)
            self.assertEqual(fusion, ancienne)
            machines = set((await db.execute(select(DeviceLink.machine_id))).scalars())
            self.assertEqual(machines, {ancienne})
            rattachee = await db.scalar(select(FreeGrant.machine_id))
            self.assertEqual(rattachee, ancienne)
            await db.commit()

    async def test_en_tete_ne_delie_jamais(self):
        async with self.sessions() as db:
            machine, _ = await anti_abus.resolve_machine(db, signaux("a", copie="copie-0002"))
            # Une copie différente avec le même cookie s'ajoute à la machine.
            meme, connue = await anti_abus.resolve_machine(db, signaux("a", copie="copie-0003"))
            self.assertTrue(connue)
            self.assertEqual(meme, machine)
            self.assertEqual(await db.scalar(select(func.count()).select_from(DeviceLink)), 3)
            await db.commit()

    async def test_empreinte_ne_fusionne_jamais_deux_machines(self):
        async with self.sessions() as db:
            premiere, _ = await anti_abus.resolve_machine(db, signaux("a", empreinte="fp-1"))
            seconde, _ = await anti_abus.resolve_machine(db, signaux("b", copie="copie-b002"))
            self.assertNotEqual(premiere, seconde)
            # Deux appareils identiques partagent l'empreinte : le cookie l'emporte.
            meme, connue = await anti_abus.resolve_machine(db, signaux("b", empreinte="fp-1"))
            self.assertTrue(connue)
            self.assertEqual(meme, seconde)
            machines = set((await db.execute(select(DeviceLink.machine_id))).scalars())
            self.assertEqual(machines, {premiere, seconde})
            await db.commit()

    async def test_empreinte_seule_retrouve_le_navigateur_efface(self):
        async with self.sessions() as db:
            machine, _ = await anti_abus.resolve_machine(db, signaux("a", empreinte="fp-2"))
            # Cookie et copie effacés : seule l'empreinte reste.
            retrouvee, connue = await anti_abus.resolve_machine(db, signaux("neuf", empreinte="fp-2"))
            self.assertTrue(connue)
            self.assertEqual(retrouvee, machine)
            await db.commit()

    async def test_touch_enregistre_l_appareil_et_pose_le_cookie(self):
        async with self.sessions() as db:
            reponse = Response()
            await anti_abus.touch(db, requete(), reponse)
            self.assertIn(anti_abus.COOKIE_NAME + "=", reponse.headers["set-cookie"])
            self.assertEqual(await db.scalar(select(func.count()).select_from(DeviceLink)), 1)


class RisqueTests(BaseTests):
    async def risque(self, db, user, signals=None, machine="m1", connue=True, needed=1):
        return await anti_abus.free_risk(db, user, signals or signaux(), machine, connue, needed)

    async def test_aucun_risque_pour_un_compte_ordinaire(self):
        async with self.sessions() as db:
            self.assertIsNone(await self.risque(db, await self.compte(db)))

    async def test_domaine_jetable(self):
        async with self.sessions() as db:
            user = await self.compte(db, email="jetable@mailinator.com")
            self.assertEqual(await self.risque(db, user), "disposable")

    async def test_meme_boite_canonique_sur_un_autre_compte(self):
        async with self.sessions() as db:
            premier = await self.compte(db, email="jane.doe@gmail.com")
            await self.attribuer(db, premier, machine="autre")
            second = await self.compte(db, email="janedoe+bis@gmail.com")
            self.assertEqual(await self.risque(db, second, machine="encore"), "mailbox")
            # Le compte lui-même ne se bloque pas.
            self.assertIsNone(await self.risque(db, premier, machine="autre"))

    async def test_appareil_deja_servi_a_deux_autres_comptes(self):
        async with self.sessions() as db:
            for _ in range(2):
                await self.attribuer(db, await self.compte(db), machine="m1")
            nouveau = await self.compte(db)
            self.assertEqual(await self.risque(db, nouveau, machine="m1"), "device")
            self.assertIsNone(await self.risque(db, nouveau, machine="m2"))

    async def test_un_seul_autre_compte_sur_l_appareil_reste_permis(self):
        async with self.sessions() as db:
            await self.attribuer(db, await self.compte(db), machine="m1")
            self.assertIsNone(await self.risque(db, await self.compte(db), machine="m1"))

    async def test_velocite_ip_sur_24h(self):
        async with self.sessions() as db:
            await self.attribuer(db, await self.compte(db), machine="x", ip="ip-9", pages=28)
            user = await self.compte(db)
            haut = signaux(ip="ip-9")
            self.assertEqual(await self.risque(db, user, haut, machine="y", needed=3), "ip")
            self.assertIsNone(await self.risque(db, user, haut, machine="y", needed=2))
            # Hors de la fenêtre de 24 h, l'attribution ne compte plus.
            await self.attribuer(db, await self.compte(db), machine="z", ip="ip-8", pages=40,
                                 il_y_a=timedelta(hours=30))
            self.assertIsNone(await self.risque(db, user, signaux(ip="ip-8"), machine="y", needed=5))

    async def test_compte_neuf_sur_appareil_inconnu(self):
        async with self.sessions() as db:
            neuf = await self.compte(db, ancien=False)
            self.assertEqual(await self.risque(db, neuf, connue=False), "new_account")
            self.assertIsNone(await self.risque(db, neuf, connue=True))
            self.assertIsNone(await self.risque(db, await self.compte(db), connue=False))

    async def test_telephone_verifie_leve_la_zone_grise_mais_pas_l_abus_net(self):
        maintenant = datetime.now(timezone.utc)
        async with self.sessions() as db:
            for _ in range(2):
                await self.attribuer(db, await self.compte(db), machine="m1", ip="ip-7", pages=30)
            verifie = await self.compte(db, ancien=False, phone_verified_at=maintenant)
            # Appareil, IP et compte neuf sont tous réunis : le téléphone lève les trois.
            self.assertIsNone(await self.risque(
                db, verifie, signaux(ip="ip-7"), machine="m1", connue=False, needed=5))
            jetable = await self.compte(db, email="v@mailinator.com", phone_verified_at=maintenant)
            self.assertEqual(await self.risque(db, jetable), "disposable")
            premier = await self.compte(db, email="paul@gmail.com")
            await self.attribuer(db, premier, machine="ailleurs")
            double = await self.compte(db, email="p.aul+2@gmail.com", phone_verified_at=maintenant)
            self.assertEqual(await self.risque(db, double, machine="autre"), "mailbox")

    async def test_attributions_d_un_mois_precedent_ne_comptent_pas(self):
        async with self.sessions() as db:
            debut = usage.month_start()
            for _ in range(2):
                user = await self.compte(db)
                db.add(FreeGrant(user_id=user.id, machine_id="m1", ip_hash="ip-1", pages=1,
                                 mailbox_key=anti_abus.mailbox_key(user.email),
                                 created_at=debut - timedelta(seconds=1)))
            await db.flush()
            self.assertIsNone(await self.risque(db, await self.compte(db), machine="m1"))


class PurgeTests(BaseTests):
    async def test_purge_des_liens_et_des_attributions_perimes(self):
        maintenant = datetime.now(timezone.utc)
        async with self.sessions() as db:
            for nom, jours in (("vieux", 61), ("recent", 10)):
                db.add(DeviceLink(hash=nom, kind="cookie", machine_id="m", created_at=maintenant,
                                  last_seen=maintenant - timedelta(days=jours)))
            user = await self.compte(db)
            for jours in (36, 10):
                await self.attribuer(db, user, il_y_a=timedelta(days=jours))
            await db.flush()
            await anti_abus.purge(db)
            await db.commit()
            self.assertEqual(set((await db.execute(select(DeviceLink.hash))).scalars()), {"recent"})
            self.assertEqual(await db.scalar(select(func.count()).select_from(FreeGrant)), 1)


class EndpointTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fx = fixtures.BetaTests()
        await self.fx.asyncSetUp()
        self.client = self.fx.client
        self.appareil = {"X-Device-Copy": "copie-poste-0001"}

    async def asyncTearDown(self):
        await self.fx.asyncTearDown()

    async def nouveau_compte(self, **champs):
        async with self.fx.sessions() as db:
            champs.setdefault("created_at", datetime.now(timezone.utc) - timedelta(days=3))
            user = User(email=f"endpoint-{uuid.uuid4().hex[:10]}@example.com", plan="free",
                        email_verified=True, **champs)
            db.add(user)
            await db.commit()
            return user

    async def envoyer(self, user, **entetes):
        return await self.client.post("/api/translate",
            headers={**self.fx.headers(user), **entetes},
            files={"file": ("document.pdf", fixtures.pdf(), "application/octet-stream")},
            data={"target_lang": "en", "use_beta": "0"})

    async def etat(self, user):
        async with self.fx.sessions() as db:
            compte = await db.get(User, user.id)
            return compte.page_credits, await usage.free_pages_used(db, user.id)

    async def test_troisieme_compte_du_mois_sur_le_meme_appareil_est_refuse_sans_debit(self):
        for _ in range(2):
            reponse = await self.envoyer(await self.nouveau_compte(), **self.appareil)
            self.assertEqual(reponse.status_code, 200, reponse.text)
        async with self.fx.sessions() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(FreeGrant)), 2)
        troisieme = await self.nouveau_compte()
        refus = await self.envoyer(troisieme, **self.appareil)
        self.assertEqual(refus.status_code, 402, refus.text)
        corps = refus.json()
        self.assertEqual(corps["reason"], "free_limit_device")
        self.assertEqual(corps["risk"], "device")
        self.assertEqual(await self.etat(troisieme), (0, 0))
        # Le refus ne laisse aucune attribution ni aucun document en file.
        async with self.fx.sessions() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(FreeGrant)), 2)

    async def test_un_compte_avec_des_pages_achetees_passe_et_ne_consomme_que_celles_ci(self):
        for _ in range(2):
            reponse = await self.envoyer(await self.nouveau_compte(), **self.appareil)
            self.assertEqual(reponse.status_code, 200, reponse.text)
        acheteur = await self.nouveau_compte(page_credits=3)
        reponse = await self.envoyer(acheteur, **self.appareil)
        self.assertEqual(reponse.status_code, 200, reponse.text)
        self.assertEqual(await self.etat(acheteur), (2, 0))

    async def test_les_appareils_differents_ne_se_bloquent_pas(self):
        for numero in range(3):
            # Un autre poste : ni le cookie ni la copie locale du précédent.
            self.client.cookies.clear()
            reponse = await self.envoyer(await self.nouveau_compte(),
                                         **{"X-Device-Copy": f"copie-poste-{numero:04d}"})
            self.assertEqual(reponse.status_code, 200, reponse.text)

    async def test_compte_neuf_sur_appareil_inconnu_est_refuse_puis_accepte_une_fois_connu(self):
        neuf = await self.nouveau_compte(created_at=datetime.now(timezone.utc))
        refus = await self.envoyer(neuf, **self.appareil)
        self.assertEqual(refus.status_code, 402, refus.text)
        self.assertEqual(refus.json()["risk"], "new_account")
        # Le refus a pourtant enregistré l'appareil : la tentative suivante passe.
        self.assertIn(anti_abus.COOKIE_NAME + "=", refus.headers.get("set-cookie", ""))
        suite = await self.envoyer(neuf, **self.appareil)
        self.assertEqual(suite.status_code, 200, suite.text)

    async def test_inscription_avec_un_domaine_jetable_refusee(self):
        reponse = await self.client.post("/api/auth/register",
            json={"email": f"x{uuid.uuid4().hex[:6]}@mailinator.com"},
            headers={"X-API-Key": fixtures.config.FRONTEND_API_KEY})
        self.assertEqual(reponse.status_code, 400, reponse.text)
        self.assertEqual(reponse.json()["detail"], anti_abus.DISPOSABLE_MESSAGE)


if __name__ == "__main__":
    unittest.main()
