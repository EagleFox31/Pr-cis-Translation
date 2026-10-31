"""Application privacy, review, seat limits and PostgreSQL approval concurrency."""
import asyncio
from datetime import timedelta
import os
import unittest
from unittest.mock import patch
import uuid
from urllib.parse import urlsplit

import test_beta_program as fixtures
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
import httpx
from app import create_app
from app.core.database import get_db, DATABASE_URL
from app.core.security import create_access_token
from app.models import User
from app.models.beta import BetaApplication, BetaCampaign, BetaEnrollment
from app.services import beta
from app.services.beta_meter import DEFAULT_LIMITS


class ApplicationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fx = fixtures.BetaTests()
        await self.fx.asyncSetUp()
        self.client = self.fx.client

    async def asyncTearDown(self):
        await self.fx.asyncTearDown()

    async def submit(self, user=None, **changes):
        user = user or self.fx.tester
        return await self.client.post('/api/beta/applications', headers=self.fx.headers(user),
            json={'primary_format': 'xlsx', 'motivation': 'Classeur de suivi commercial bilingue', **changes})

    async def review(self, application_id, decision='approved', headers=None):
        return await self.client.patch('/api/admin/beta/applications/' + application_id,
            json={'decision': decision}, headers=headers or self.fx.admin_headers)

    async def test_public_program_closed_by_default_and_contains_no_private_data(self):
        result = await self.client.get('/api/beta/program')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['limits'], DEFAULT_LIMITS)
        self.assertFalse(result.json()['applications_open'])
        self.assertEqual(result.json()['availability'], 'closed')
        await self.fx.start_campaign()
        await self.submit()
        changed = await self.client.patch(f'/api/admin/beta/campaigns/{self.fx.campaign_id}', headers=self.fx.admin_headers,
            json={'access_days': 45, 'limits': {**DEFAULT_LIMITS, 'xlsx': 3, 'xlsx_words': 400}})
        self.assertEqual(changed.status_code, 200)
        public = (await self.client.get('/api/beta/program')).json()
        self.assertEqual(public['access_days'], 45)
        self.assertEqual(public['limits']['xlsx_words'], 400)
        self.assertNotIn('@', str(public))
        self.assertNotIn('applications', public)

    async def test_requires_verified_account_and_admin_review(self):
        response = await self.client.post('/api/beta/applications', json={
            'primary_format': 'pdf', 'motivation': 'Mon document de test'})
        self.assertEqual(response.status_code, 401)
        closed = await self.submit()
        self.assertEqual(closed.status_code, 409)
        # A stable code lets the page translate the refusal.
        self.assertEqual(closed.json()['detail']['code'], 'applications_closed')
        await self.fx.start_campaign()
        async with self.fx.sessions() as db:
            (await db.get(User, self.fx.tester.id)).email_verified = False
            await db.commit()
        self.assertEqual((await self.submit()).status_code, 403)
        self.assertEqual((await self.submit(self.fx.other, email=self.fx.tester.email)).status_code, 422)
        self.assertEqual((await self.submit(self.fx.other, motivation='    ')).status_code, 422)
        # Invisible characters that reorder or hide text are refused.
        for trap in ('Contrat signé ‮gnp.exe', 'Classeur\x00 de suivi', 'Rapport ⁦annuel⁩'):
            self.assertEqual((await self.submit(self.fx.other, motivation=trap)).status_code, 422)
        # Line breaks and emoji joiners stay allowed.
        own = (await self.submit(self.fx.other, motivation='Rapport annuel\r\nÉquipe 👨‍👩‍👧')).json()
        denied = await self.review(own['id'], headers=self.fx.headers(self.fx.other))
        self.assertEqual(denied.status_code, 403)
        self.assertEqual((await self.client.get('/api/admin/beta', headers=self.fx.tester_headers)).status_code, 403)

    async def test_submission_is_private_idempotent_and_grants_no_access(self):
        await self.fx.start_campaign()
        first = await self.submit()
        self.assertEqual(first.status_code, 200, first.text)
        again = await self.submit(motivation='Une seconde tentative de soumission')
        self.assertEqual(first.json()['id'], again.json()['id'])
        self.assertEqual(first.json()['motivation'], again.json()['motivation'])
        own = (await self.client.get('/api/beta/me', headers=self.fx.tester_headers)).json()
        self.assertEqual(own['application']['state'], 'pending')
        self.assertIsNone(own['enrollment'])
        self.assertFalse(own['can_activate'])
        other = (await self.client.get('/api/beta/me', headers=self.fx.headers(self.fx.other))).json()
        self.assertIsNone(other['application'])
        missing = await self.client.post('/api/beta/activate', headers=self.fx.tester_headers)
        self.assertEqual((missing.status_code, missing.json()['detail']['code']), (404, 'no_invitation'))
        async with self.fx.sessions() as db:
            self.assertEqual(await beta.capacity_used(db, self.fx.campaign_id), 0)
            self.assertEqual((await db.get(User, self.fx.tester.id)).page_credits, 7)
            self.assertEqual((await db.get(User, self.fx.tester.id)).plan, 'free')

    async def test_approval_starts_access_directly_once(self):
        await self.fx.start_campaign()
        application = (await self.submit()).json()
        approved = await self.review(application['id'])
        self.assertEqual(approved.status_code, 200, approved.text)
        async with self.fx.sessions() as db:
            enrollment = await beta.enrollment_for(db, self.fx.tester)
            self.assertEqual(enrollment.user_id, self.fx.tester.id)
            self.assertIsNotNone(enrollment.activated_at)
            self.assertIsNotNone(enrollment.ip_hash)
            expires_at = enrollment.expires_at
        own = (await self.client.get('/api/beta/me', headers=self.fx.tester_headers)).json()
        self.assertEqual(own['enrollment']['state'], 'active')
        self.assertEqual((await self.review(application['id'])).status_code, 200)
        again = await self.client.post('/api/beta/activate', headers=self.fx.tester_headers)
        self.assertEqual(again.status_code, 200, again.text)
        async with self.fx.sessions() as db:
            self.assertEqual((await beta.enrollment_for(db, self.fx.tester)).expires_at, expires_at)
        self.assertEqual((await self.review(application['id'], 'declined')).status_code, 409)
        async with self.fx.sessions() as db:
            self.assertEqual(await beta.capacity_used(db, self.fx.campaign_id), 1)

    async def test_refused_direct_access_waits_for_the_next_visit(self):
        await self.fx.start_campaign()
        application = (await self.submit()).json()
        async with self.fx.sessions() as db:
            (await db.get(User, self.fx.tester.id)).email_verified = False; await db.commit()
        self.assertEqual((await self.review(application['id'])).status_code, 200)
        own = (await self.client.get('/api/beta/me', headers=self.fx.tester_headers)).json()
        self.assertEqual((own['application']['state'], own['enrollment']['state']), ('approved', 'invited'))
        async with self.fx.sessions() as db:
            (await db.get(User, self.fx.tester.id)).email_verified = True; await db.commit()
        own = (await self.client.get('/api/beta/me', headers=self.fx.tester_headers)).json()
        self.assertEqual(own['enrollment']['state'], 'active')

    async def test_decline_and_manual_invitation_keep_status_consistent(self):
        await self.fx.start_campaign()
        row = (await self.submit()).json()
        self.assertEqual((await self.review(row['id'], 'declined')).json()['state'], 'declined')
        async with self.fx.sessions() as db:
            self.assertEqual(await beta.capacity_used(db, self.fx.campaign_id), 0)
        await self.fx.invite_tester()
        own = (await self.client.get('/api/beta/me', headers=self.fx.tester_headers)).json()
        self.assertEqual(own['application']['state'], 'approved')
        self.assertEqual(own['enrollment']['state'], 'active')

    async def test_waiting_applications_do_not_bypass_wave_or_total_capacity(self):
        await self.fx.start_campaign(capacity=2, first_wave_capacity=1)
        await self.fx.invite_tester()
        row = (await self.submit(self.fx.other)).json()
        self.assertEqual((await self.review(row['id'])).status_code, 409)
        async with self.fx.sessions() as db:
            self.assertEqual((await db.get(BetaApplication, row['id'])).state, 'pending')
            (await db.get(BetaCampaign, self.fx.campaign_id)).starts_at = beta.now_utc() - timedelta(days=35)
            await db.commit()
        self.assertEqual((await self.review(row['id'])).status_code, 200)
        public = (await self.client.get('/api/beta/program')).json()
        self.assertFalse(public['applications_open'])
        self.assertEqual(public['availability'], 'full')
        self.assertEqual((await self.submit(self.fx.admin)).status_code, 409)

    async def test_expired_campaign_stops_new_submissions_and_approvals(self):
        await self.fx.start_campaign()
        row = (await self.submit()).json()
        async with self.fx.sessions() as db:
            (await db.get(BetaCampaign, self.fx.campaign_id)).recruitment_ends_at = beta.now_utc() - timedelta(seconds=1)
            await db.commit()
        self.assertEqual((await self.submit(self.fx.other)).status_code, 409)
        self.assertEqual((await self.review(row['id'])).status_code, 409)
        public = (await self.client.get('/api/beta/program')).json()
        self.assertEqual(public['availability'], 'ended')

    async def test_deleted_candidate_can_be_declined_but_not_approved(self):
        await self.fx.start_campaign()
        row = (await self.submit()).json()
        async with self.fx.sessions() as db:
            await db.delete(await db.get(User, self.fx.tester.id))
            await db.commit()
        self.assertEqual((await self.review(row['id'])).status_code, 409)
        self.assertEqual((await self.review(row['id'], 'declined')).status_code, 200)


@unittest.skipUnless(os.getenv('CI') == 'true' and
    urlsplit(DATABASE_URL).hostname in ('localhost', '127.0.0.1') and
    urlsplit(DATABASE_URL).path == '/precis', 'Approval concurrency uses isolated CI PostgreSQL')
class ApprovalConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_admin_approvals_cannot_reserve_the_last_place_twice(self):
        engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        created = False
        user_ids = []
        try:
            async with sessions() as db:
                self.assertIsNone(await db.get(BetaCampaign, 'pilot'))
                campaign = BetaCampaign(id='pilot', name='CI approval race', state='open',
                    capacity=1, first_wave_capacity=1, access_days=30, limits=DEFAULT_LIMITS,
                    starts_at=beta.now_utc(), recruitment_ends_at=beta.now_utc()+timedelta(days=30))
                people = [User(email=f'approval-{uuid.uuid4().hex}@example.com', plan=plan,
                               email_verified=True) for plan in ('admin', 'free', 'free')]
                db.add_all([campaign, *people]); await db.flush()
                rows = [BetaApplication(campaign_id='pilot', user_id=user.id, email=user.email,
                    primary_format='pdf', motivation='Isolated concurrency fixture') for user in people[1:]]
                db.add_all(rows); await db.commit()
                created = True
                user_ids = [user.id for user in people]
                application_ids = [row.id for row in rows]
                headers = {'Authorization': 'Bearer '+create_access_token(people[0].id, people[0].email)}
            app = create_app()
            async def database():
                async with sessions() as db:
                    yield db
            app.dependency_overrides[get_db] = database
            gate = asyncio.Event()
            calls = 0
            original = beta.campaign_row
            async def overlap(db, *, lock=False):
                nonlocal calls
                if lock:
                    calls += 1
                    if calls <= 2:
                        if calls == 2: gate.set()
                        await gate.wait()
                return await original(db, lock=lock)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                with patch.object(beta, 'campaign_row', side_effect=overlap):
                    responses = await asyncio.wait_for(asyncio.gather(*[
                        client.patch('/api/admin/beta/applications/'+key, headers=headers,
                            json={'decision': 'approved'}) for key in application_ids]), timeout=20)
            self.assertEqual(sorted(r.status_code for r in responses), [200, 409])
            async with sessions() as db:
                self.assertEqual(await beta.capacity_used(db, 'pilot'), 1)
                states = (await db.execute(select(BetaApplication.state))).scalars().all()
                self.assertEqual(sorted(states), ['approved', 'pending'])
        finally:
            if created:
                async with sessions() as db:
                    await db.execute(delete(BetaApplication).where(BetaApplication.campaign_id == 'pilot'))
                    await db.execute(delete(BetaEnrollment).where(BetaEnrollment.campaign_id == 'pilot'))
                    await db.execute(delete(BetaCampaign).where(BetaCampaign.id == 'pilot'))
                    await db.execute(delete(User).where(User.id.in_(user_ids)))
                    await db.commit()
            await engine.dispose()


if __name__ == '__main__':
    unittest.main()
