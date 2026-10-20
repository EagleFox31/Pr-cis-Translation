"""Beta aliases, private signals, burst admission and real PostgreSQL races."""
import asyncio
from datetime import timedelta
import os
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit
import uuid

import test_beta_program as fixtures
import httpx
from fastapi import Request, Response
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app import create_app
from app.core.database import get_db, DATABASE_URL
from app.core.security import create_access_token
from app.models import User
from app.models.beta import BetaApplication, BetaCampaign, BetaEnrollment
from app.services import beta, beta_abuse
from app.services.beta_meter import DEFAULT_LIMITS


def request(peer="198.51.100.10", cookie=None, forwarded=None):
    headers = []
    if cookie:
        headers.append((b"cookie", (beta_abuse.COOKIE_NAME + "=" + cookie).encode()))
    if forwarded:
        headers += [(b"x-forwarded-for", forwarded.encode()), (b"x-real-ip", forwarded.encode())]
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


class SignalUnitTests(unittest.TestCase):
    def test_only_personal_gmail_mailboxes_are_canonicalized(self):
        self.assertEqual(beta_abuse.canonical_mailbox(" Jane.Doe+beta@GMAIL.COM "), "janedoe@gmail.com")
        self.assertEqual(beta_abuse.canonical_mailbox("j.a.n.e.d.o.e+second@googlemail.com"), "janedoe@gmail.com")
        self.assertEqual(beta_abuse.canonical_mailbox("Jane.Doe+beta@trigenys.com"), "jane.doe+beta@trigenys.com")
        self.assertNotEqual(beta_abuse.canonical_mailbox("jane.doe@trigenys.com"),
                            beta_abuse.canonical_mailbox("janedoe@trigenys.com"))

    def test_cookie_is_signed_and_forged_headers_do_not_change_the_peer(self):
        first = beta_abuse.client_signals(request())
        second = beta_abuse.client_signals(request(cookie=first.new_cookie, forwarded="203.0.113.80"))
        self.assertEqual(first.device_hash, second.device_hash)
        self.assertEqual(first.ip_hash, second.ip_hash)
        self.assertIsNone(second.new_cookie)
        changed = beta_abuse.client_signals(request(peer="198.51.100.11", cookie=first.new_cookie))
        self.assertNotEqual(first.ip_hash, changed.ip_hash)
        self.assertEqual(first.device_hash, changed.device_hash)
        forged = first.new_cookie[:-1] + ("0" if first.new_cookie[-1] != "0" else "1")
        invalid = beta_abuse.client_signals(request(cookie=forged))
        self.assertIsNotNone(invalid.new_cookie)
        self.assertNotEqual(first.device_hash, invalid.device_hash)
        self.assertIsNone(beta_abuse.client_signals(request(peer="testclient")).ip_hash)
        response = Response()
        with patch.object(beta_abuse, "IS_PRODUCTION", True):
            beta_abuse.set_cookie(response, first)
        flags = response.headers["set-cookie"].lower()
        for value in ("httponly", "secure", "samesite=lax", "path=/api/beta", "max-age=2592000"):
            self.assertIn(value, flags)
        self.assertEqual(response.headers["cache-control"], "private, no-store")
        self.assertNotIn("198.51.100.10", flags)


class AbuseApplicationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fx = fixtures.BetaTests()
        await self.fx.asyncSetUp()
        self.client = self.fx.client
        await self.fx.start_campaign()

    async def asyncTearDown(self):
        await self.fx.asyncTearDown()

    async def person(self, email=None):
        async with self.fx.sessions() as db:
            user = User(email=email or f"beta-{uuid.uuid4().hex}@example.com",
                        email_verified=True, plan="free")
            db.add(user)
            await db.commit()
            return user

    async def submit(self, user=None, client=None):
        return await (client or self.client).post("/api/beta/applications",
            headers=self.fx.headers(user or self.fx.tester),
            json={"primary_format": "pdf", "motivation": "Documents de test bilingues"})

    async def dashboard(self):
        result = await self.client.get("/api/admin/beta", headers=self.fx.admin_headers)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.headers["cache-control"], "private, no-store")
        return result.json()

    async def test_gmail_variants_cannot_apply_or_receive_a_second_invitation(self):
        token = uuid.uuid4().hex
        a = await self.person(f"beta.{token}+one@gmail.com")
        b = await self.person(f"beta{token}+two@googlemail.com")
        first = await self.submit(a)
        self.assertEqual(first.status_code, 200, first.text)
        again = await self.submit(a)
        self.assertEqual(again.json()["id"], first.json()["id"])
        self.assertEqual((await self.submit(b)).status_code, 409)
        invited = await self.fx.invite_tester(a)
        self.assertEqual(invited["email"], a.email)
        blocked = await self.client.post("/api/admin/beta/invitations",
            headers=self.fx.admin_headers, json={"email": b.email})
        self.assertEqual(blocked.status_code, 409)
        async with self.fx.sessions() as db:
            self.assertEqual((await db.get(User, a.id)).email, a.email)
            self.assertEqual((await db.get(User, b.id)).email, b.email)
            self.assertEqual(await beta.capacity_used(db), 1)
        foreign = await self.client.post("/api/beta/activate", headers=self.fx.headers(b))
        self.assertEqual(foreign.status_code, 404, "Canonicalization must not transfer an invitation")

    async def test_manual_invitation_also_blocks_a_new_alias_application(self):
        token = uuid.uuid4().hex
        a = await self.person(f"beta.{token}@gmail.com")
        b = await self.person(f"beta{token}+extra@gmail.com")
        await self.fx.invite_tester(a)
        self.assertEqual((await self.submit(b)).status_code, 409)
        self.assertEqual((await self.submit(a)).status_code, 409)

    async def test_shared_network_is_reviewable_and_never_a_denial_by_itself(self):
        first = await self.submit()
        self.client.cookies.clear()  # another browser on the same network
        second = await self.submit(self.fx.other)
        self.assertEqual(second.status_code, 200, second.text)
        dashboard = await self.dashboard()
        row = next(x for x in dashboard["applications"] if x["id"] == second.json()["id"])
        kinds = {flag["kind"] for flag in row["risk"]["flags"]}
        self.assertIn("same_ip", kinds)
        self.assertNotIn("same_browser", kinds)
        self.assertEqual(row["risk"]["related_count"], 1)
        for response in (first, second, await self.client.get("/api/beta/me",
                headers=self.fx.headers(self.fx.other))):
            for private in ("risk", "ip_hash", "device_hash", "mailbox_key", "127.0.0.1"):
                self.assertNotIn(private, response.text)
        for row in dashboard["applications"]:
            approved = await self.client.patch("/api/admin/beta/applications/" + row["id"],
                headers=self.fx.admin_headers, json={"decision": "approved"})
            self.assertEqual(approved.status_code, 200, approved.text)

    async def test_own_application_and_activation_are_not_two_people(self):
        first = (await self.submit()).json()
        await self.client.patch("/api/admin/beta/applications/" + first["id"],
            headers=self.fx.admin_headers, json={"decision": "approved"})
        activated = await self.client.post("/api/beta/activate", headers=self.fx.tester_headers)
        self.assertEqual(activated.status_code, 200, activated.text)
        dashboard = await self.dashboard()
        self.assertEqual(dashboard["applications"][0]["risk"]["flags"], [])
        self.assertEqual(dashboard["enrollments"][0]["risk"]["flags"], [])
        second = await self.submit(self.fx.other)
        self.assertEqual(second.status_code, 200)
        third = await self.submit(await self.person())
        self.assertEqual(third.status_code, 200)
        dashboard = await self.dashboard()
        risk = next(x["risk"] for x in dashboard["applications"] if x["id"] == first["id"])
        flags = {flag["kind"]: flag["count"] for flag in risk["flags"]}
        self.assertEqual(flags["same_browser"], 2)
        self.assertEqual(flags["same_ip"], 2)
        self.assertEqual(flags["rapid_sequence"], 3)
        for private in ("ip_hash", "device_hash", "mailbox_key", "precis_beta_device", "127.0.0.1"):
            self.assertNotIn(private, str(dashboard))

    async def test_browser_burst_is_temporary_idempotent_and_grants_no_quota(self):
        people = [self.fx.tester] + [await self.person() for _ in range(5)]
        for user in people[:5]:
            response = await self.submit(user)
            self.assertEqual(response.status_code, 200, response.text)
        blocked = await self.submit(people[5])
        self.assertEqual(blocked.status_code, 429, blocked.text)
        self.assertEqual(blocked.headers["retry-after"], "600")
        self.assertEqual((await self.submit(people[0])).status_code, 200)
        async with self.fx.sessions() as db:
            rows = (await db.execute(select(BetaApplication))).scalars().all()
            self.assertEqual(len(rows), 5)
            self.assertEqual(await beta.capacity_used(db), 0)
            self.assertEqual((await db.get(User, self.fx.tester.id)).page_credits, 7)
            for row in rows:
                row.submitted_at = beta.now_utc() - timedelta(minutes=11)
            await db.commit()
        self.assertEqual((await self.submit(people[5])).status_code, 200)

    async def test_ip_burst_cannot_be_bypassed_with_a_new_cookie_or_forwarded_header(self):
        self.assertEqual((await self.submit()).status_code, 200)
        async with self.fx.sessions() as db:
            first = (await db.execute(select(BetaApplication))).scalar_one()
            for number in range(19):
                user = User(email=f"burst-{uuid.uuid4().hex}@example.com", email_verified=True)
                db.add(user)
                await db.flush()
                db.add(BetaApplication(campaign_id="pilot", user_id=user.id, email=user.email,
                    primary_format="pdf", motivation="Independent burst fixture",
                    ip_hash=first.ip_hash, device_hash=f"device-{number}"))
            await db.commit()
        self.client.cookies.clear()
        candidate = await self.person()
        blocked = await self.client.post("/api/beta/applications",
            headers={**self.fx.headers(candidate), "X-Forwarded-For": "203.0.113.222"},
            json={"primary_format": "pdf", "motivation": "My legitimate documents"})
        self.assertEqual(blocked.status_code, 429)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.fx.app,
                client=("192.0.2.45", 1234)), base_url="http://test") as other_network:
            self.assertEqual((await self.submit(candidate, client=other_network)).status_code, 200)

    async def test_expired_signals_are_ignored_and_purged_without_resetting_access(self):
        first = (await self.submit()).json()
        await self.fx.invite_tester()
        active = (await self.client.post("/api/beta/activate", headers=self.fx.tester_headers)).json()
        async with self.fx.sessions() as db:
            application = await db.get(BetaApplication, first["id"])
            enrollment = (await db.execute(select(BetaEnrollment))).scalar_one()
            application.submitted_at = beta.now_utc() - timedelta(days=31)
            enrollment.activated_at = beta.now_utc() - timedelta(days=31)
            await db.commit()
            await beta_abuse.purge_signals(db)
            await db.commit()
            for model, key in ((BetaApplication, application.id), (BetaEnrollment, enrollment.id)):
                row = await db.get(model, key, populate_existing=True)
                self.assertIsNone(row.ip_hash)
                self.assertIsNone(row.device_hash)
                self.assertIsNotNone(row.mailbox_key)
            self.assertEqual(enrollment.expires_at.isoformat().replace("+00:00", ""),
                             active["expires_at"].replace("+00:00", ""))
            self.assertEqual(await beta.capacity_used(db), 1)
        self.assertEqual((await self.submit(self.fx.other)).status_code, 200)
        dashboard = await self.dashboard()
        self.assertTrue(all(not row["risk"]["flags"] for row in dashboard["applications"]))

    async def test_legacy_alias_invitation_cannot_activate_or_restore_a_second_trial(self):
        token = uuid.uuid4().hex
        a = await self.person(f"beta.{token}@gmail.com")
        b = await self.person(f"beta{token}+alias@gmail.com")
        async with self.fx.sessions() as db:
            entries = [BetaEnrollment(campaign_id="pilot", email=user.email,
                primary_format="pdf", limits=DEFAULT_LIMITS) for user in (a, b)]
            db.add_all(entries)
            await db.commit()
            second_id = entries[1].id
        first = await self.client.post("/api/beta/activate", headers=self.fx.headers(a))
        self.assertEqual(first.status_code, 200)
        second = await self.client.post("/api/beta/activate", headers=self.fx.headers(b))
        self.assertEqual(second.status_code, 409)
        await self.client.patch("/api/admin/beta/enrollments/" + second_id,
            headers=self.fx.admin_headers, json={"revoke": True})
        restored = await self.client.patch("/api/admin/beta/enrollments/" + second_id,
            headers=self.fx.admin_headers, json={"revoke": False})
        self.assertEqual(restored.status_code, 409)
        self.assertEqual((await self.client.post("/api/beta/activate",
            headers=self.fx.headers(a))).json()["expires_at"], first.json()["expires_at"])

    async def test_google_http_route_is_rate_limited_without_calling_google(self):
        with patch.dict(os.environ, {"GOOGLE_CLIENT_ID": "test-client"}), patch(
                "google.oauth2.id_token.verify_oauth2_token", side_effect=ValueError("fixture")):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.fx.app,
                    client=("192.0.2.99", 1234)), base_url="http://test") as client:
                responses = [await client.post("/api/auth/google",
                    headers={"X-API-Key": fixtures.config.FRONTEND_API_KEY},
                    json={"credential": "invalid-fixture"}) for _ in range(6)]
        self.assertEqual([r.status_code for r in responses], [401] * 5 + [429])


@unittest.skipUnless(os.getenv("CI") == "true" and
    urlsplit(DATABASE_URL).hostname in ("localhost", "127.0.0.1") and
    urlsplit(DATABASE_URL).path == "/precis", "Alias races use isolated CI PostgreSQL")
class AliasRaceTests(unittest.IsolatedAsyncioTestCase):
    async def race(self, activation=False):
        engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        created, user_ids = False, []
        try:
            async with sessions() as db:
                self.assertIsNone(await db.get(BetaCampaign, "pilot"))
                key = uuid.uuid4().hex
                users = [User(email=email, email_verified=True) for email in
                    (f"beta.{key}+one@gmail.com", f"beta{key}+two@googlemail.com")]
                campaign = BetaCampaign(id="pilot", name="Alias race", state="open",
                    capacity=40, first_wave_capacity=20, access_days=30, limits=DEFAULT_LIMITS,
                    starts_at=beta.now_utc(), recruitment_ends_at=beta.now_utc()+timedelta(days=30))
                db.add_all([campaign, *users])
                await db.flush()
                if activation:
                    db.add_all([BetaEnrollment(campaign_id="pilot", email=user.email,
                        primary_format="pdf", limits=DEFAULT_LIMITS) for user in users])
                await db.commit()
                created = True
                user_ids = [user.id for user in users]
            app = create_app()
            async def database():
                async with sessions() as db:
                    yield db
            app.dependency_overrides[get_db] = database
            gate, calls, original = asyncio.Event(), 0, beta.campaign_row
            async def overlap(db, *, lock=False):
                nonlocal calls
                if lock:
                    calls += 1
                    if calls <= 2:
                        if calls == 2:
                            gate.set()
                        await gate.wait()
                return await original(db, lock=lock)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                with patch.object(beta, "campaign_row", side_effect=overlap):
                    responses = await asyncio.wait_for(asyncio.gather(*[
                        client.post("/api/beta/activate" if activation else "/api/beta/applications",
                            headers={"Authorization": "Bearer " + create_access_token(user.id, user.email)},
                            **({} if activation else {"json": {"primary_format": "pdf",
                                "motivation": "Concurrent verified alias fixture"}})) for user in users]), timeout=20)
            self.assertEqual(sorted(r.status_code for r in responses), [200, 409],
                             [r.text for r in responses])
            async with sessions() as db:
                model = BetaEnrollment if activation else BetaApplication
                query = select(func.count()).select_from(model).where(model.campaign_id == "pilot")
                if activation:
                    query = query.where(BetaEnrollment.activated_at.is_not(None))
                self.assertEqual((await db.execute(query)).scalar(), 1)
        finally:
            if created:
                async with sessions() as db:
                    for model in (BetaApplication, BetaEnrollment):
                        await db.execute(delete(model).where(model.campaign_id == "pilot"))
                    await db.execute(delete(BetaCampaign).where(BetaCampaign.id == "pilot"))
                    await db.execute(delete(User).where(User.id.in_(user_ids)))
                    await db.commit()
            await engine.dispose()

    async def test_parallel_gmail_submissions_share_one_mailbox(self):
        await self.race()

    async def test_parallel_legacy_alias_activations_grant_only_one_trial(self):
        await self.race(activation=True)


if __name__ == "__main__":
    unittest.main()
