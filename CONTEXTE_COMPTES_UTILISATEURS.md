# CONTEXTE — Comptes utilisateurs, authentification & stockage

_Dernière mise à jour : 2026-07-15._

> Ce document est le **contexte de référence** pour la fonctionnalité « comptes
> utilisateurs ». Il doit permettre à n'importe quel modèle ou agent de
> reprendre l'implémentation là où elle s'est arrêtée.

---

## But

Ajouter une authentification complète (email + Google OAuth) avec gestion des
documents traduits par utilisateur, remplacement du stockage local
(IndexedDB/localStorage) par du stockage backend, et quotas par abonnement.

---

## Architecture cible

```
┌─ Frontend (React 19 + Vite + Tailwind) ──────────────────────────┐
│  React Router : /login  /register  /verify-email  /home          │
│  AuthContext : JWT en mémoire, refresh automatique               │
│  useDocumentLibrary : fetch API backend (plus d'IndexedDB)       │
│  Google OAuth : @react-oauth/google (bouton)                     │
└───────────────────────────────┬──────────────────────────────────┘
                                │ JWT Bearer
┌─ Backend (FastAPI Python) ────┴──────────────────────────────────┐
│  /api/auth/*     : register, login, refresh, verify-email, google│
│  /api/documents/*: CRUD documents utilisateur                    │
│  /api/translate  : protégé par require_auth (middleware JWT)     │
│  /api/user/storage : quota                                        │
│                                                                   │
│  Middleware : verify_jwt → injecte current_user                   │
│  Email      : SMTP (aiosmtplib), template HTML, code 6 chiffres  │
│  Stockage   : backend/translations/{user_id}/{doc_id}/...        │
└───────────────────────────────┬──────────────────────────────────┘
                                │
┌─ PostgreSQL ──────────────────┴──────────────────────────────────┐
│  Tables : users, documents, refresh_tokens, verification_codes   │
│  ORM    : SQLAlchemy 2.0 async + asyncpg                         │
│  Migrations : Alembic                                            │
└──────────────────────────────────────────────────────────────────┘
```

---

## Modèles de données

### User
| Colonne | Type | Notes |
|---|---|---|
| `id` | UUID | PK, généré côté serveur |
| `email` | String(255) | UNIQUE, NOT NULL, lowercased |
| `password_hash` | String(255) | nullable (Google OAuth = pas de mdp) |
| `name` | String(255) | nullable |
| `email_verified` | Boolean | default False |
| `google_id` | String(255) | nullable, UNIQUE |
| `avatar_url` | String(512) | nullable |
| `plan` | Enum(`free`, `pro`, `enterprise`) | default `free` |
| `storage_used` | BigInteger | default 0 (octets) |
| `storage_limit` | BigInteger | default 104857600 (100 Mo pour `free`) |
| `created_at` | DateTime | default now |
| `updated_at` | DateTime | auto-update |

### Document
| Colonne | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `user_id` | UUID | FK → User |
| `original_name` | String(512) | nom du fichier source |
| `source_lang` | String(10) | auto-détecté |
| `target_lang` | String(10) | choisi par l'utilisateur |
| `original_path` | String(1024) | chemin disque backend |
| `translated_path` | String(1024) | nullable, rempli quand prêt |
| `size_bytes` | BigInteger | taille du fichier source |
| `status` | Enum(`pending`, `translating`, `done`, `error`) | |
| `page_count` | Integer | nullable |
| `created_at` | DateTime | |
| `updated_at` | DateTime | |

### RefreshToken
| Colonne | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `user_id` | UUID | FK → User |
| `token_hash` | String(255) | UNIQUE, SHA256 du token |
| `expires_at` | DateTime | 30 jours |
| `created_at` | DateTime | |

### VerificationCode
| Colonne | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `user_id` | UUID | FK → User |
| `code` | String(6) | 6 chiffres |
| `token` | String(255) | UNIQUE, pour le lien cliquable |
| `expires_at` | DateTime | 15 minutes |
| `used` | Boolean | default False |
| `created_at` | DateTime | |

---

## Flux d'authentification

### Inscription email
1. `POST /api/auth/register` → `{email, password, name?}`
2. Backend : crée User (`email_verified=False`), génère `VerificationCode` (code 6 chiffres + token lien)
3. Envoie email avec **les deux** : code + lien `{FRONTEND_URL}/verify-email?token=xxx`
4. Retourne `{message: "Vérifiez votre email"}` (PAS de JWT)

### Vérification — double canal

**Canal 1 — Lien cliqué :**
1. `GET /api/auth/verify-email?token=abc123`
2. Backend : vérifie token, marque `email_verified=True`, `used=True`
3. Redirect → `{FRONTEND_URL}/login?verified=1`

**Canal 2 — Code saisi manuellement :**
1. `POST /api/auth/verify-email` → `{email, code}`
2. Backend : vérifie code (6 chiffres, expire 15 min), marque `email_verified=True`
3. Retourne `{access_token, refresh_token, user}` → connecté directement

### Connexion email
1. `POST /api/auth/login` → `{email, password}`
2. Vérifie `email_verified=True` sinon erreur « Vérifiez votre email »
3. Retourne `{access_token, refresh_token, user}`

### Google OAuth
1. Frontend : Google Identity Services → `credential` (id_token JWT Google)
2. `POST /api/auth/google` → `{credential}`
3. Backend : vérifie token Google (`google-auth`), extrait `email`, `sub`, `name`, `picture`
4. Si User existe par `google_id` → connexion
5. Si User existe par `email` mais sans `google_id` → lie `google_id`, connexion
6. Sinon → création User (`email_verified=True`, `google_id`, `name`, `avatar_url`)
7. Retourne `{access_token, refresh_token, user}`

### Refresh token
1. `POST /api/auth/refresh` → `{refresh_token}`
2. Vérifie hash + expiration, génère nouveau JWT
3. Rotation : ancien refresh token invalidé, nouveau émis

---

## Middleware auth (FastAPI)

```python
# backend/auth.py
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def require_auth(credentials = Depends(security)) -> User:
    payload = verify_jwt(credentials.credentials)
    user = await get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(401)
    return user
```

Appliqué sur toutes les routes `/api/documents/*` et `/api/translate/*`.

---

## Quotas de stockage

| Plan | Stockage |
|---|---|
| `free` | 100 Mo |
| `pro` | 1 Go |
| `enterprise` | 10 Go |

Vérifié avant upload ET avant lancement de traduction. Si dépassement → erreur 402.

---

## Fichiers modifiés / créés

### Backend — nouveaux
| Fichier | Rôle |
|---|---|
| `backend/database.py` | Engine SQLAlchemy async, session factory |
| `backend/models.py` | Modèles ORM : User, Document, RefreshToken, VerificationCode |
| `backend/auth.py` | JWT, bcrypt, middleware `require_auth` |
| `backend/routes/auth.py` | Routes auth (register, login, refresh, verify, google) |
| `backend/routes/documents.py` | CRUD documents utilisateur |
| `backend/email_service.py` | Envoi email vérification (SMTP async) |
| `backend/migrations/` | Alembic (init + migrations) |

### Backend — modifiés
| Fichier | Changement |
|---|---|
| `backend/requirements.txt` | + sqlalchemy, asyncpg, alembic, pyjwt, bcrypt, google-auth, aiosmtplib |
| `backend/app.py` | Routes auth/documents, dépendance `require_auth` |
| `backend/.env.example` | + DATABASE_URL, JWT_SECRET, SMTP_*, GOOGLE_CLIENT_ID |

### Frontend — nouveaux
| Fichier | Rôle |
|---|---|
| `frontend/src/contexts/AuthContext.tsx` | Contexte auth (JWT, user, login/logout) |
| `frontend/src/pages/LoginPage.tsx` | Formulaire connexion |
| `frontend/src/pages/RegisterPage.tsx` | Formulaire inscription |
| `frontend/src/pages/VerifyEmailPage.tsx` | Page vérification (code + lien auto) |

### Frontend — modifiés
| Fichier | Changement |
|---|---|
| `frontend/src/App.tsx` | React Router, AuthContext provider |
| `frontend/src/hooks/useDocumentLibrary.ts` | Refonte : API backend au lieu d'IndexedDB |
| `frontend/src/utils/idbStore.ts` | **Supprimé** |

---

## Ordre d'implémentation (8 étapes)

1. ✅ **Base de données** : `database.py` + `models.py` + Alembic init
2. **Auth backend** : `auth.py` (JWT, bcrypt) + `routes/auth.py` (register, login, refresh, me)
3. **Email + vérification** : `email_service.py` + double canal (lien + code)
4. **Documents backend** : `routes/documents.py` + réorganisation stockage
5. **Google OAuth** : backend + frontend
6. **Frontend auth** : AuthContext, pages, routing
7. **Frontend documents** : refonte useDocumentLibrary → API
8. **Abonnements** : quotas, middleware

---

## Environnement

```bash
# backend/.env — nouvelles variables
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/precis
JWT_SECRET=votre-secret-jwt-64-chars-min
JWT_EXPIRY_MINUTES=60
REFRESH_TOKEN_EXPIRY_DAYS=30

SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=noreply@precis.app

FRONTEND_URL=http://localhost:3000
GOOGLE_CLIENT_ID=votre-google-client-id.apps.googleusercontent.com
```
