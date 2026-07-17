"""
Routes d'authentification — register, login, refresh, me, verify-email, google.
"""
from __future__ import annotations
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Body
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import User, VerificationCode
from auth import (
    create_access_token, create_refresh_token,
    rotate_refresh_token, revoke_user_tokens, require_auth,
    hash_password, verify_password,
)
from email_service import send_verification_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
VERIFICATION_CODE_EXPIRY_MINUTES = 15
# Anti-bombing : un email de code au maximum toutes les N secondes par compte.
RESEND_THROTTLE_SECONDS = 45
# Anti-brute-force : nombre d'essais erronés tolérés avant invalidation du code.
MAX_CODE_ATTEMPTS = 5


def _aware(dt):
    """Normalise un datetime en UTC-aware (asyncpg peut renvoyer naïf selon la
    config), pour des soustractions sûres."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

# ── Schémas ──────────────────────────────────────────────────────────────────

class EmailBody(BaseModel):
    email: EmailStr
    name: str | None = None

class RefreshBody(BaseModel):
    refresh_token: str

class VerifyCodeBody(BaseModel):
    email: EmailStr
    code: str

class GoogleBody(BaseModel):
    credential: str   # id_token JWT Google

# Longueur minimale d'un mot de passe. Seule règle imposée : la LONGUEUR.
# Exiger « une majuscule, un chiffre, un symbole » pousse aux mots de passe
# courts et réutilisés (« Motdepasse1! ») ; c'est la recommandation actuelle de
# l'ANSSI comme du NIST — la longueur fait la force, pas la ponctuation.
MIN_PASSWORD_LEN = 10

class PasswordLoginBody(BaseModel):
    email: EmailStr
    password: str

class PasswordRegisterBody(BaseModel):
    email: EmailStr
    password: str
    name: str | None = None

class ForgotBody(BaseModel):
    email: EmailStr

class ResetBody(BaseModel):
    email: EmailStr
    code: str
    password: str

class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: dict


def _user_response(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "email_verified": user.email_verified,
        "avatar_url": user.avatar_url,
        "plan": user.plan,
        "storage_used": user.storage_used,
        "storage_limit": user.storage_limit,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


async def _generate_verification(db: AsyncSession, user: User) -> VerificationCode:
    """Crée un code de vérification (6 chiffres + token lien).

    Throttle anti-bombing : refuse (429) si un code a été émis pour ce compte il y
    a moins de `RESEND_THROTTLE_SECONDS`. Sans cela, `login`/`register` (qui créent
    un compte à la volée pour n'importe quel email) permettaient d'inonder une
    boîte de messages en boucle."""
    last = await db.execute(
        select(VerificationCode)
        .where(VerificationCode.user_id == user.id)
        .order_by(VerificationCode.created_at.desc())
        .limit(1)
    )
    prev = last.scalar_one_or_none()
    if prev is not None:
        age = (datetime.now(timezone.utc) - _aware(prev.created_at)).total_seconds()
        if age < RESEND_THROTTLE_SECONDS:
            raise HTTPException(
                status_code=429,
                detail=f"Un code vient d'être envoyé. Réessayez dans "
                       f"{int(RESEND_THROTTLE_SECONDS - age) + 1}s.",
            )
    # Invalider les anciens codes non utilisés
    stmt = select(VerificationCode).where(
        VerificationCode.user_id == user.id,
        VerificationCode.used == False,  # noqa: E712
    )
    result = await db.execute(stmt)
    for old in result.scalars().all():
        old.used = True

    code = f"{secrets.randbelow(1_000_000):06d}"
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(minutes=VERIFICATION_CODE_EXPIRY_MINUTES)

    vc = VerificationCode(
        user_id=user.id, code=code, token=token, expires_at=expires,
    )
    db.add(vc)
    await db.commit()
    await db.refresh(vc)
    return vc


# ── POST /register ───────────────────────────────────────────────────────────

@router.post("/register", status_code=201)
async def register(body: EmailBody, db: AsyncSession = Depends(get_db)):
    """Inscription sans mot de passe : crée le compte, envoie le code de vérification."""
    email = body.email.lower().strip()
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Cet email est déjà utilisé.")

    user = User(email=email, name=body.name)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    vc = await _generate_verification(db, user)
    await send_verification_email(user.email, vc.code, vc.token)

    return {"message": "Code envoyé. Vérifiez votre email pour continuer.", "email": email}


# ── POST /login ──────────────────────────────────────────────────────────────

@router.post("/login", status_code=201)
async def login(body: EmailBody, db: AsyncSession = Depends(get_db)):
    """Connexion sans mot de passe : envoie un code de vérification.
    Si l'utilisateur n'existe pas, le crée automatiquement (inscription implicite)."""
    email = body.email.lower().strip()

    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        # Inscription implicite
        user = User(email=email, name=body.name)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    vc = await _generate_verification(db, user)
    await send_verification_email(user.email, vc.code, vc.token)

    is_new = not user.email_verified
    return {
        "message": "Code envoyé. Vérifiez votre email pour continuer.",
        "email": email,
        "is_new": is_new,
    }


# ── Mot de passe ─────────────────────────────────────────────────────────────
# La connexion par CODE EMAIL reste en place (elle sert de repli et de première
# entrée). Le mot de passe évite d'aller relever sa boîte à chaque session.

def _check_password_strength(pw: str) -> None:
    if len(pw) < MIN_PASSWORD_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"Mot de passe trop court : {MIN_PASSWORD_LEN} caractères minimum.",
        )


async def _issue(db: AsyncSession, user: User) -> AuthResponse:
    """Couple de jetons pour une session ouverte."""
    return AuthResponse(
        access_token=create_access_token(user.id, user.email),
        refresh_token=await create_refresh_token(db, user.id),
        user=_user_response(user),
    )


@router.post("/register-password", status_code=201)
async def register_password(body: PasswordRegisterBody,
                            db: AsyncSession = Depends(get_db)):
    """Inscription avec mot de passe. L'email reste à vérifier par code."""
    email = body.email.lower().strip()
    _check_password_strength(body.password)

    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is not None and user.password_hash:
        raise HTTPException(status_code=409, detail="Un compte existe déjà pour cet email.")

    if user is None:
        user = User(email=email, name=body.name)
        db.add(user)
    user.password_hash = hash_password(body.password)
    await db.commit()
    await db.refresh(user)

    vc = await _generate_verification(db, user)
    await send_verification_email(user.email, vc.code, vc.token)
    return {"message": "Compte créé. Vérifiez votre email pour l'activer.",
            "email": email, "is_new": True}


@router.post("/login-password")
async def login_password(body: PasswordLoginBody,
                         db: AsyncSession = Depends(get_db)):
    """Connexion par mot de passe — ouvre la session directement."""
    email = body.email.lower().strip()
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()

    # Message IDENTIQUE que le compte n'existe pas, n'ait pas de mot de passe ou
    # que le mot de passe soit faux : distinguer ces cas transforme la page de
    # connexion en annuaire (on saurait quels emails ont un compte).
    if user is None or not user.password_hash \
            or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect.")

    if not user.email_verified:
        raise HTTPException(status_code=403,
                            detail="Email non vérifié. Vérifiez votre boîte de réception.")
    return await _issue(db, user)


@router.post("/forgot-password", status_code=201)
async def forgot_password(body: ForgotBody, db: AsyncSession = Depends(get_db)):
    """Envoie un code de réinitialisation — vérification de l'email d'abord."""
    email = body.email.lower().strip()
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()

    # Réponse TOUJOURS identique, compte ou pas : sinon cet endpoint dirait
    # publiquement quels emails sont inscrits chez vous.
    #
    # L'envoi est ENCAPSULÉ, et ce n'est pas de la superstition : on n'envoie
    # que si le compte existe. Une panne SMTP ferait donc répondre 500 pour un
    # compte existant contre 201 pour un inconnu — l'erreur elle-même rétablit
    # l'énumération que ce endpoint est censé interdire. Constaté en test, SMTP
    # injoignable. Le silence est ici la bonne réponse : l'utilisateur redemande
    # un code, l'attaquant n'apprend rien.
    if user is not None:
        try:
            vc = await _generate_verification(db, user)
            await send_verification_email(user.email, vc.code, vc.token)
        except Exception:
            logger.exception("forgot-password : envoi du code impossible")
    return {"message": "Si un compte existe pour cet email, un code vient d'être envoyé.",
            "email": email}


@router.post("/reset-password")
async def reset_password(body: ResetBody, db: AsyncSession = Depends(get_db)):
    """Nouveau mot de passe contre un code valide reçu par email."""
    email = body.email.lower().strip()
    _check_password_strength(body.password)

    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=400, detail="Code invalide ou expiré.")

    vc = (await db.execute(
        select(VerificationCode)
        .where(VerificationCode.user_id == user.id,
               VerificationCode.code == body.code.strip(),
               VerificationCode.used == False)      # noqa: E712
        .order_by(VerificationCode.created_at.desc())
    )).scalars().first()

    if vc is None or _aware(vc.expires_at) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Code invalide ou expiré.")

    vc.used = True
    user.password_hash = hash_password(body.password)
    # Un email qui prouve la possession de la boîte VAUT vérification.
    user.email_verified = True
    await db.commit()

    # Toutes les sessions ouvertes tombent : si un intrus était connecté, le
    # changement de mot de passe doit l'expulser — sinon il ne sert à rien.
    await revoke_user_tokens(db, user.id)
    await db.refresh(user)
    return await _issue(db, user)


# ── POST /refresh ────────────────────────────────────────────────────────────

@router.post("/refresh")
async def refresh(body: RefreshBody, db: AsyncSession = Depends(get_db)):
    """Rotation du refresh token → nouveau couple access + refresh."""
    result = await rotate_refresh_token(db, body.refresh_token)
    if result is None:
        raise HTTPException(status_code=401, detail="Refresh token invalide ou expiré.")

    new_refresh, user = result
    access_token = create_access_token(user.id, user.email)

    return AuthResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        user=_user_response(user),
    )


# ── POST /logout ─────────────────────────────────────────────────────────────

@router.post("/logout")
async def logout(
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Révoque tous les refresh tokens de l'utilisateur."""
    await revoke_user_tokens(db, user.id)
    return {"message": "Déconnecté."}


# ── GET /me ──────────────────────────────────────────────────────────────────

@router.get("/me")
async def me(user: User = Depends(require_auth)):
    """Profil de l'utilisateur connecté."""
    return _user_response(user)


# ── GET /verify-email (lien) ─────────────────────────────────────────────────

@router.get("/verify-email")
async def verify_email_link(token: str, db: AsyncSession = Depends(get_db)):
    """Vérification par lien cliqué dans l'email.
    Redirige vers le frontend avec le statut."""
    from fastapi.responses import RedirectResponse

    stmt = select(VerificationCode).where(
        VerificationCode.token == token,
        VerificationCode.used == False,  # noqa: E712
    )
    result = await db.execute(stmt)
    vc = result.scalar_one_or_none()

    if vc is None or vc.expires_at < datetime.now(timezone.utc):
        return RedirectResponse(f"{FRONTEND_URL}/verify-email?error=expired")

    vc.used = True
    user = await db.get(User, vc.user_id)
    if user:
        user.email_verified = True
    await db.commit()

    return RedirectResponse(f"{FRONTEND_URL}/login?verified=1")


# ── POST /verify-email (code) ────────────────────────────────────────────────

@router.post("/verify-email")
async def verify_email_code(body: VerifyCodeBody, db: AsyncSession = Depends(get_db)):
    """Vérification par code 6 chiffres saisi manuellement.
    Connecte directement l'utilisateur."""
    stmt = select(User).where(User.email == body.email.lower().strip())
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

    # On récupère le code ACTIF le plus récent (indépendamment de la valeur
    # saisie) pour pouvoir COMPTER les essais erronés : sans cela, un code à
    # 6 chiffres (1 M combinaisons, fenêtre 15 min) était brute-forçable sans
    # aucune limite.
    stmt = (
        select(VerificationCode)
        .where(
            VerificationCode.user_id == user.id,
            VerificationCode.used == False,  # noqa: E712
        )
        .order_by(VerificationCode.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    vc = result.scalar_one_or_none()

    if vc is None or _aware(vc.expires_at) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Code invalide ou expiré.")

    if vc.code != body.code.strip():
        vc.attempts += 1
        if vc.attempts >= MAX_CODE_ATTEMPTS:
            vc.used = True                      # trop d'essais → code condamné
            await db.commit()
            raise HTTPException(
                status_code=429,
                detail="Trop de tentatives. Demandez un nouveau code.",
            )
        remaining = MAX_CODE_ATTEMPTS - vc.attempts
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"Code invalide. {remaining} essai(s) restant(s).",
        )

    vc.used = True
    user.email_verified = True
    await db.commit()

    access_token = create_access_token(user.id, user.email)
    refresh_token = await create_refresh_token(db, user.id)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=_user_response(user),
    )


# ── POST /google ─────────────────────────────────────────────────────────────

@router.post("/google")
async def google_auth(body: GoogleBody, db: AsyncSession = Depends(get_db)):
    """Connexion/inscription via Google OAuth."""
    import google.auth.transport.requests
    from google.oauth2 import id_token

    google_client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    if not google_client_id:
        raise HTTPException(status_code=501, detail="Google OAuth non configuré.")

    try:
        id_info = id_token.verify_oauth2_token(
            body.credential,
            google.auth.transport.requests.Request(),
            google_client_id,
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Token Google invalide.")

    email = id_info.get("email", "").lower().strip()
    google_id = id_info.get("sub", "")
    name = id_info.get("name")
    picture = id_info.get("picture")

    if not email or not google_id:
        raise HTTPException(status_code=400, detail="Le token Google est incomplet.")

    # Chercher par google_id d'abord, puis par email
    stmt = select(User).where(User.google_id == google_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

    if user is None:
        # Création
        user = User(
            email=email,
            google_id=google_id,
            name=name,
            avatar_url=picture,
            email_verified=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        # Mise à jour
        if not user.google_id:
            user.google_id = google_id
        if not user.avatar_url and picture:
            user.avatar_url = picture
        if not user.email_verified:
            user.email_verified = True
        await db.commit()
        await db.refresh(user)

    access_token = create_access_token(user.id, user.email)
    refresh_token = await create_refresh_token(db, user.id)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=_user_response(user),
    )


# ── POST /resend-verification ────────────────────────────────────────────────

@router.post("/resend-verification", status_code=201)
async def resend_verification(email: EmailStr = Body(..., embed=True), db: AsyncSession = Depends(get_db)):
    """Renvoie un email de vérification."""
    stmt = select(User).where(User.email == email.lower().strip())
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        # Ne pas révéler si l'email existe ou pas
        return {"message": "Si cet email est enregistré, un code de vérification lui a été envoyé."}

    if user.email_verified:
        return {"message": "Cet email est déjà vérifié."}

    vc = await _generate_verification(db, user)
    await send_verification_email(user.email, vc.code, vc.token)

    return {"message": "Un nouveau code de vérification a été envoyé."}
