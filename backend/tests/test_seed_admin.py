"""ADMIN_EMAIL accepte plusieurs comptes ; le redemarrage reste idempotent."""
import asyncio
import os
import unittest
import uuid
from unittest.mock import patch

import racine  # noqa: F401
import seed_admin
from sqlalchemy import delete, select
from app.models import User


class AdminEmailsTests(unittest.TestCase):
    def test_default_and_single_address(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(seed_admin.admin_emails(), [seed_admin.DEFAULT_ADMIN_EMAIL])
        with patch.dict(os.environ, {"ADMIN_EMAIL": " Owner@Example.com "}):
            self.assertEqual(seed_admin.admin_emails(), ["owner@example.com"])
            self.assertEqual(seed_admin.admin_email(), "owner@example.com")

    def test_list_spaces_duplicates_and_empty_entries(self):
        with patch.dict(os.environ, {"ADMIN_EMAIL":
                " Contact@Trigenys.com, ,mbowouibrah@gmail.com,CONTACT@TRIGENYS.COM,"}):
            self.assertEqual(seed_admin.admin_emails(),
                             ["contact@trigenys.com", "mbowouibrah@gmail.com"])

    def test_empty_list_is_rejected(self):
        with patch.dict(os.environ, {"ADMIN_EMAIL": " , , "}):
            with self.assertRaises(ValueError):
                seed_admin.admin_emails()


async def verify_database():
    token = uuid.uuid4().hex
    existing, new, other = [f"seed-{label}-{token}@example.com"
                            for label in ("existing", "new", "other")]
    emails = [existing, new, other]
    try:
        async with seed_admin._asm() as db:
            db.add_all([User(email=existing, name="Existing owner", plan="free"),
                        User(email=other, name="Other admin", plan="admin")])
            await db.commit()
        with patch.dict(os.environ, {"ADMIN_EMAIL": f" {existing.upper()}, {new},,{existing}"}):
            await seed_admin.main()
            await seed_admin.main()
        async with seed_admin._asm() as db:
            users = (await db.execute(select(User).where(User.email.in_(emails)))).scalars().all()
            assert len(users) == 3, "Restart must not create duplicate or combined addresses"
            by_email = {user.email: user for user in users}
            assert by_email[existing].name == "Existing owner"
            for email in (existing, new):
                user = by_email[email]
                assert user.plan == "admin" and user.email_verified
                assert user.storage_limit == 0 and user.plan_expires_at is None
            assert by_email[other].plan == "admin", "Existing admins keep their rights"
        print("PASS: comma-separated admins created/promoted; restart idempotent; existing admins preserved")
    finally:
        async with seed_admin._asm() as db:
            await db.execute(delete(User).where(User.email.in_(emails)))
            await db.commit()
        await seed_admin.engine.dispose()


if __name__ == "__main__":
    # Fail the suite if any parsing test fails, before reaching the database.
    result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(AdminEmailsTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
    asyncio.run(verify_database())
