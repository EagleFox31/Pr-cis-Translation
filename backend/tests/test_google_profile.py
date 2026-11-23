"""Le profil renvoye apres connexion Google porte le nom du jeton verifie."""
import asyncio
import os
import uuid
from unittest.mock import patch

import racine  # noqa: F401
from fastapi import HTTPException, Request, Response
from sqlalchemy import select
from app.api.auth import GoogleBody, google_auth
from app.models import User
import seed_admin

# Profile unit test; HTTP throttling is covered in test_beta_abuse.py.
google_handler = getattr(google_auth, '__wrapped__', google_auth)


async def main():
    token = uuid.uuid4().hex
    email = f"google-profile-{token}@example.com"
    claims = {"email": email, "sub": f"google-{token}",
              "email_verified": True, "name": "  Google Account Name  "}

    async def login(payload):
        with patch.dict(os.environ, {"GOOGLE_CLIENT_ID": "test-client"}), patch(
                "google.oauth2.id_token.verify_oauth2_token", return_value=payload):
            async with seed_admin._asm() as db:
                return await google_handler(GoogleBody(credential="test-token"), db,
                                            request=Request({"type": "http", "headers": []}), response=Response())

    try:
        # Reproduit le compte administrateur amorce avant sa premiere connexion.
        async with seed_admin._asm() as db:
            user = User(email=email, name="Ibrahim Mbowou", plan="admin")
            db.add(user)
            await db.commit()
            user_id = user.id
        response = await login(claims)
        assert response.user["id"] == user_id
        assert response.user["name"] == "Google Account Name"
        assert response.user["plan"] == "admin"
        assert response.access_token and response.refresh_token
        # Un redemarrage ne doit pas ecraser le nom recupere de Google.
        await seed_admin.ensure_admin(email)
        async with seed_admin._asm() as db:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one()
            assert user.name == "Google Account Name" and user.google_id == claims["sub"]
        response = await login({**claims, "name": "Updated Google Name"})
        assert response.user["name"] == "Updated Google Name"
        response = await login({**claims, "name": "   "})
        assert response.user["name"] == "Updated Google Name", "Empty Google names preserve the profile"
        with patch.dict(os.environ, {"GOOGLE_CLIENT_ID": "test-client"}), patch(
                "google.oauth2.id_token.verify_oauth2_token", side_effect=ValueError("invalid token")):
            async with seed_admin._asm() as db:
                try:
                    await google_handler(GoogleBody(credential="invalid-token"), db,
                                         request=Request({"type": "http", "headers": []}), response=Response())
                except HTTPException as exc:
                    assert exc.status_code == 401
                else:
                    raise AssertionError("An unverified token must not update the profile")
        async with seed_admin._asm() as db:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one()
            assert user.name == "Updated Google Name" and user.plan == "admin"
        print("PASS: verified Google name returned and persisted; admin rights and identity retained; restart safe; invalid tokens rejected")
    finally:
        async with seed_admin._asm() as db:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is not None:
                await db.delete(user)
                await db.commit()
        await seed_admin.engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
