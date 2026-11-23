"""Anti-robots à la création de compte (Cloudflare Turnstile).

Cloudflare n'est jamais appelé : `_siteverify` est remplacé.
"""
import unittest
import uuid
from unittest.mock import AsyncMock, patch

import httpx

import test_beta_program as fixtures  # pose JWT_SECRET et les variables d'environnement
from sqlalchemy import select

from app import config
from app.models import User
from app.rate_limit import limiter
from app.services import turnstile


class TurnstileTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fx = fixtures.BetaTests()
        await self.fx.asyncSetUp()
        self.client = self.fx.client
        if limiter:
            limiter.reset()
        self.cle = patch.object(config, "TURNSTILE_SECRET_KEY", "secret-de-test")
        self.cle.start()

    async def asyncTearDown(self):
        self.cle.stop()
        await self.fx.asyncTearDown()

    async def poster(self, chemin, **corps):
        corps.setdefault("email", f"robot-{uuid.uuid4().hex[:8]}@example.com")
        return await self.client.post(chemin, json=corps,
            headers={"X-API-Key": fixtures.config.FRONTEND_API_KEY})

    async def compte_existe(self, email):
        async with self.fx.sessions() as db:
            return (await db.scalar(select(User).where(User.email == email))) is not None

    async def test_sans_jeton_aucun_compte_cree(self):
        for chemin, extra in (("/api/auth/register", {}), ("/api/auth/login", {}),
                              ("/api/auth/register-password", {"password": "x" * 12})):
            with self.subTest(chemin=chemin):
                email = f"robot-{uuid.uuid4().hex[:8]}@example.com"
                reponse = await self.poster(chemin, email=email, **extra)
                self.assertEqual(reponse.status_code, 400, reponse.text)
                self.assertEqual(reponse.json()["detail"], turnstile.MESSAGE)
                self.assertFalse(await self.compte_existe(email))

    async def test_jeton_accepte_cree_le_compte(self):
        email = f"humain-{uuid.uuid4().hex[:8]}@example.com"
        with patch.object(turnstile, "_siteverify",
                          AsyncMock(return_value={"success": True})) as verif:
            reponse = await self.poster("/api/auth/register", email=email, turnstile_token="jeton")
        self.assertEqual(reponse.status_code, 201, reponse.text)
        self.assertTrue(await self.compte_existe(email))
        envoye = verif.await_args.args[0]
        self.assertEqual((envoye["secret"], envoye["response"]), ("secret-de-test", "jeton"))

    async def test_jeton_refuse(self):
        with patch.object(turnstile, "_siteverify", AsyncMock(
                return_value={"success": False, "error-codes": ["invalid-input-response"]})):
            reponse = await self.poster("/api/auth/register", turnstile_token="faux")
        self.assertEqual(reponse.status_code, 400, reponse.text)

    async def test_jeton_demesure_refuse_sans_appel(self):
        with patch.object(turnstile, "_siteverify", AsyncMock()) as verif:
            reponse = await self.poster("/api/auth/register", turnstile_token="x" * 5000)
        self.assertEqual(reponse.status_code, 400, reponse.text)
        verif.assert_not_awaited()

    async def test_panne_cloudflare_laisse_passer(self):
        with patch.object(turnstile, "_siteverify",
                          AsyncMock(side_effect=httpx.ConnectTimeout("panne"))):
            reponse = await self.poster("/api/auth/register", turnstile_token="jeton")
        self.assertEqual(reponse.status_code, 201, reponse.text)

    async def test_connexion_d_un_compte_existant_sans_jeton(self):
        email = f"ancien-{uuid.uuid4().hex[:8]}@example.com"
        async with self.fx.sessions() as db:
            db.add(User(email=email, plan="free", email_verified=True))
            await db.commit()
        with patch.object(turnstile, "_siteverify", AsyncMock()) as verif:
            reponse = await self.poster("/api/auth/login", email=email)
        self.assertEqual(reponse.status_code, 201, reponse.text)
        verif.assert_not_awaited()

    async def test_sans_cle_aucun_controle(self):
        with patch.object(config, "TURNSTILE_SECRET_KEY", ""), \
                patch.object(turnstile, "_siteverify", AsyncMock()) as verif:
            reponse = await self.poster("/api/auth/register")
        self.assertEqual(reponse.status_code, 201, reponse.text)
        verif.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
