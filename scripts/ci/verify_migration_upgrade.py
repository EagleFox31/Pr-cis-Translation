"""Rehearse the existing 0007 database upgrade in a disposable CI database."""
import asyncio
import os
from pathlib import Path
import subprocess
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[2]
URL = os.environ['DATABASE_URL']
if urlparse(URL).path != '/precis_migration_ci' or urlparse(URL).hostname not in ('localhost', '127.0.0.1'):
    raise SystemExit('Migration rehearsal only accepts the isolated local CI database')

def upgrade(revision):
    subprocess.run(['alembic', 'upgrade', revision], cwd=ROOT / 'backend', check=True)

async def seed():
    engine = create_async_engine(URL)
    async with engine.begin() as db:
        await db.execute(text("INSERT INTO users (id,email,plan,page_credits) VALUES ('migration-user','migration@example.invalid','starter',17)"))
        for doc_id, status, pages in [('migration-done', 'done', 3), ('migration-error', 'error', 2)]:
            await db.execute(text("INSERT INTO documents (id,user_id,original_name,source_lang,target_lang,original_path,size_bytes,status,page_count) VALUES (:id,'migration-user','fixture.txt','fr','en','fixture.txt',30,:status,:pages)"), {'id': doc_id, 'status': status, 'pages': pages})
        await db.execute(text("INSERT INTO payments (id,user_id,pages,amount,currency,zone,status,credited) VALUES ('migration-payment','migration-user',17,1700,'XAF','CM','SUCCESSFUL',true)"))
    await engine.dispose()

async def verify():
    engine = create_async_engine(URL)
    async with engine.begin() as db:
        user = (await db.execute(text("SELECT plan,page_credits,plan_expires_at,plan_started_at FROM users WHERE id='migration-user'"))).one()
        assert tuple(user) == ('starter', 17, None, None)
        usage = (await db.execute(text("SELECT document_id,kind,pages,refunded FROM usage_records ORDER BY document_id"))).all()
        assert [tuple(row) for row in usage] == [('migration-done','legacy',3,False),('migration-error','legacy',2,True)]
        payment = (await db.execute(text("SELECT credited,refund_due,plan,months,method FROM payments WHERE id='migration-payment'"))).one()
        assert tuple(payment) == (True, False, None, None, None)
        for table in ("beta_campaigns", "beta_enrollments", "beta_usage", "beta_applications"):
            assert (await db.execute(text(f"SELECT count(*) FROM {table}"))).scalar() == 0
        await db.execute(text("DELETE FROM documents WHERE id='migration-done'"))
        retained = (await db.execute(text("SELECT pages,document_id FROM usage_records WHERE id='migration-done'"))).one()
        assert tuple(retained) == (3, None), 'Deleting a legacy document must not erase its consumption'
    await engine.dispose()
    print('PASS: 0007 -> 0011 preserves accounts, plans, credits and payments; consumption survives document deletion.')


async def seed_beta_legacy():
    engine = create_async_engine(URL)
    async with engine.begin() as db:
        await db.execute(text("""
            INSERT INTO beta_campaigns
            (id,name,state,capacity,first_wave_capacity,access_days,limits,created_at)
            VALUES ('migration-beta','Historical closed beta','draft',40,20,30,
                    CAST('{}' AS JSON),CURRENT_TIMESTAMP)
        """))
        for number, email, state in (
            (1, 'be.ta.migration+first@gmail.com', 'pending'),
            (2, 'betamigration+second@googlemail.com', 'declined'),
        ):
            await db.execute(text("""
                INSERT INTO beta_applications
                (id,campaign_id,email,primary_format,motivation,state,submitted_at)
                VALUES (:id,'migration-beta',:email,'pdf','Historical fixture',:state,CURRENT_TIMESTAMP)
            """), {'id': f'migration-app-{number}', 'email': email, 'state': state})
            await db.execute(text("""
                INSERT INTO beta_enrollments
                (id,campaign_id,email,primary_format,limits,invited_at)
                VALUES (:id,'migration-beta',:email,'pdf',CAST('{}' AS JSON),CURRENT_TIMESTAMP)
            """), {'id': f'migration-enrollment-{number}', 'email': email})
    await engine.dispose()

async def verify_beta_legacy():
    engine = create_async_engine(URL)
    async with engine.begin() as db:
        campaign = (await db.execute(text(
            "SELECT state,starts_at,access_days FROM beta_campaigns WHERE id='migration-beta'"))).one()
        assert tuple(campaign) == ('draft', None, 30), 'Upgrade must never open recruitment'
        for table in ('beta_applications', 'beta_enrollments'):
            records = (await db.execute(text(
                f"SELECT email,mailbox_key,ip_hash,device_hash FROM {table} WHERE campaign_id='migration-beta' ORDER BY id"))).all()
            assert len(records) == 2, 'Historical aliases must never be deleted or merged'
            assert [row[0] for row in records] == [
                'be.ta.migration+first@gmail.com', 'betamigration+second@googlemail.com']
            assert all(tuple(row[1:]) == ('betamigration@gmail.com', None, None) for row in records)
        states = (await db.execute(text(
            "SELECT state FROM beta_applications WHERE campaign_id='migration-beta' ORDER BY id"))).scalars().all()
        assert list(states) == ['pending', 'declined'], 'Reviews must stay unchanged'
        user = (await db.execute(text(
            "SELECT plan,page_credits FROM users WHERE id='migration-user'"))).one()
        assert tuple(user) == ('starter', 17)
    await engine.dispose()
    print('PASS: 0011 -> head backfills mailbox keys, preserves historical aliases and decisions, and invents no network metadata.')

upgrade('0007_support_tickets')
asyncio.run(seed())
upgrade('0011_beta_applications')
asyncio.run(verify())
asyncio.run(seed_beta_legacy())
upgrade('head')
upgrade('head')
asyncio.run(verify_beta_legacy())
