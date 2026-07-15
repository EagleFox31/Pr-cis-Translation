# CONTEXTE — Comptes utilisateurs, authentification & stockage

_Dernière mise à jour : 2026-07-15 — fin de session._

> Ce document est le **contexte de référence** pour la fonctionnalité « comptes
> utilisateurs ». Tout est implémenté, testé et fonctionnel.

---

## Bilan de la session

### Authentification
- ✅ **Passwordless** : email → code 6 chiffres → connexion (pas de mot de passe)
- ✅ **Google OAuth** : bouton « Continuer avec Google » fonctionnel
- ✅ **Double canal** vérification : lien cliqué OU code saisi manuellement
- ✅ **JWT** : access token (60 min) + refresh token (30 jours) avec rotation
- ✅ **Email** : Gmail SMTP (`smtp.gmail.com:587`), template HTML branded Précis, no-reply

### Base de données (PostgreSQL)
- ✅ SQLAlchemy 2.0 async + asyncpg, migrations Alembic
- ✅ Tables : `users`, `documents`, `refresh_tokens`, `verification_codes`
- ✅ Compte admin seed : `mbowouibrah@gmail.com` (plan `admin`, illimité)

### Forfaits & quotas
- ✅ **Gratuit** : 1 page/mois, 0 Mo stockage, pas de téléchargement
- ✅ **Starter** : pages illimitées, 500 Mo stockage
- ✅ **Pro** : pages illimitées, 2 Go stockage
- ✅ **Enterprise** : pages illimitées, 10 Go stockage
- ✅ **Admin** : tout illimité, mode précis (deepseek-v4-flash)

### Interface
- ✅ **Visiteur** : landing page complète, formulaire visible, clic Traduire → /login
- ✅ **Navbar** : avatar ouvre la sidebar (plus de dropdown), boutons Connexion/Inscription
- ✅ **Sidebar unifiée** : profil (avatar, plan, stockage, déconnexion) + documents
- ✅ **Pages auth** : design cohérent (logo animé, fond dégradé, AuthBackground multilingue)
- ✅ **Tarifs** : cartes avec stockage, badge actif, bouton grisé, ✕ rouge pour restrictions
- ✅ **Formulaire** : mode précis admin (checkbox jaune dans options avancées)

### Stockage documents
- ✅ **localStorage/IndexedDB supprimés** — visiteurs = mémoire volatile
- ✅ **Connectés** : documents sauvegardés en base, fetch API `/api/documents`
- ✅ **Quota** : vérifié avant traduction, erreur 402 si dépassé

### Console & logs
- ✅ Logs de démarrage propres (4 lignes au lieu de 15)
- ✅ `SIGKILL` Windows corrigé
- ✅ Animation hero ralentie avec pauses

---

## Architecture

```
┌─ Frontend (React 19 + Vite + Tailwind) ──────────────────────────────┐
│  React Router : /login  /register  /verify-email  /home              │
│  AuthContext : JWT, login/logout/register/verify/google              │
│  useDocumentLibrary : API backend (plus d'IndexedDB)                 │
│  Google OAuth : @react-oauth/google (GoogleLogin component)          │
│  Sidebar unifiée : profil (haut) + documents (bas)                   │
│  PricingCards : forfaits avec stockage, badge actif, bouton grisé    │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ JWT Bearer
┌─ Backend (FastAPI Python) ────┴──────────────────────────────────────┐
│  /api/auth/*        : register, login, refresh, verify, google, me   │
│  /api/documents/*   : CRUD documents utilisateur                     │
│  /api/translate     : JWT détecté → Document en base, quota vérifié  │
│  /api/user/storage  : quota                                          │
│                                                                       │
│  Freemium : 1 page/mois (compteur par mois calendaire, 402 si atteint)│
│  Admin    : mode précis (checkbox → quality=precise → deepseek-v4)   │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
┌─ PostgreSQL ──────────────────┴──────────────────────────────────────┐
│  Tables : users, documents, refresh_tokens, verification_codes       │
│  ORM    : SQLAlchemy 2.0 async + asyncpg                             │
│  Migrations : Alembic                                                │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Modèles de données (état final)

### User
| Colonne | Type | Notes |
|---|---|---|
| `id` | String(32) | PK, hex UUID |
| `email` | String(255) | UNIQUE, NOT NULL, lowercased |
| `password_hash` | String(255) | nullable (passwordless, Google OAuth) |
| `name` | String(255) | nullable |
| `email_verified` | Boolean | default False |
| `google_id` | String(255) | nullable, UNIQUE |
| `avatar_url` | String(512) | nullable |
| `plan` | String(20) | `free`/`starter`/`pro`/`enterprise`/`admin` |
| `storage_used` | BigInteger | default 0 |
| `storage_limit` | BigInteger | default 0 (free), selon plan |
| `created_at` | DateTime | |
| `updated_at` | DateTime | |

### Document
| Colonne | Type | Notes |
|---|---|---|
| `id` | String(32) | PK |
| `user_id` | String(32) | FK → User |
| `original_name` | String(512) | |
| `source_lang` | String(10) | |
| `target_lang` | String(10) | |
| `original_path` | String(1024) | |
| `translated_path` | String(1024) | nullable |
| `size_bytes` | BigInteger | |
| `status` | String(20) | `pending`/`translating`/`done`/`error` |
| `page_count` | Integer | nullable |
| `created_at` | DateTime | |
| `updated_at` | DateTime | |

---

## Forfaits (PLAN_STORAGE / PLAN_PAGE_LIMIT)

| Plan | Stockage | Pages | Badge |
|---|---|---|---|
| `free` | 0 Mo | 1 page/mois | Gratuit (gris) |
| `starter` | 500 Mo | Illimité | Starter (bleu) |
| `pro` | 2 Go | Illimité | Pro (bleu) |
| `enterprise` | 10 Go | Illimité | Enterprise (bleu) |
| `admin` | Illimité | Illimité | Admin (bleu) |

---

## Flux d'authentification (passwordless)

1. **Login** : `POST /api/auth/login {email}` → code envoyé → `POST /api/auth/verify-email {email, code}` → JWT
2. **Register** : `POST /api/auth/register {email, name?}` → code envoyé → idem
3. **Google** : `POST /api/auth/google {credential}` → vérifie token → JWT
4. **Refresh** : `POST /api/auth/refresh {refresh_token}` → nouveau couple
5. **Vérification lien** : `GET /api/auth/verify-email?token=xxx` → redirect `/login?verified=1`

---

## Flux visiteur / connecté

```
Visiteur (non connecté) :
  → Landing page, formulaire visible
  → Clic « Traduire » → redirection /login
  → Aucun forfait actif, carte Freemium → bouton « Commencer » → /login

Connecté (free) :
  → 1 page/mois, pas de téléchargement, pas de stockage
  → Toast « Passez à Starter » après traduction
  → 402 si quota atteint

Connecté (payant) :
  → Pages illimitées, stockage selon plan
  → Documents sauvegardés en base, visibles dans la sidebar
```

---

## Comptes spéciaux

| Email | Plan | Notes |
|---|---|---|
| `mbowouibrah@gmail.com` | admin | Stockage illimité, mode précis activable |
| `toujoursmoi237@gmail.com` | free | Compte test |

Seed : `backend/seed_admin.py` (usage unique, promeut `mbowouibrah` en admin).

---

## Fichiers clés

### Backend
| Fichier | Rôle |
|---|---|
| `backend/database.py` | Engine SQLAlchemy async |
| `backend/models.py` | Modèles + plans/quotas |
| `backend/auth.py` | JWT, bcrypt, require_auth |
| `backend/routes/auth.py` | Endpoints auth |
| `backend/routes/documents.py` | CRUD documents |
| `backend/email_service.py` | Gmail SMTP, template HTML |
| `backend/app.py` | Routes, limite freemium, sauvegarde Document |
| `backend/migrations/versions/0001_init.py` | Migration initiale |
| `backend/seed_admin.py` | Seed compte admin |

### Frontend
| Fichier | Rôle |
|---|---|
| `frontend/src/App.tsx` | React Router, AuthProvider, GoogleOAuthProvider |
| `frontend/src/services/api.ts` | Client HTTP avec refresh JWT auto |
| `frontend/src/contexts/AuthContext.tsx` | Contexte auth (JWT, user, login/logout) |
| `frontend/src/pages/LoginPage.tsx` | Connexion passwordless + Google |
| `frontend/src/pages/RegisterPage.tsx` | Inscription |
| `frontend/src/pages/VerifyEmailPage.tsx` | Vérification code + lien |
| `frontend/src/pages/Home.tsx` | Page principale, toast freemium |
| `frontend/src/components/navbar/Navbar.tsx` | Avatar → sidebar, boutons auth |
| `frontend/src/components/library/DocumentLibrary.tsx` | Sidebar profil + documents |
| `frontend/src/components/pricing/PricingCards.tsx` | Cartes tarifs avec stockage, badge actif |
| `frontend/src/components/upload/TranslationSection.tsx` | Formulaire, redirection /login visiteur, mode précis |
| `frontend/src/components/auth/AuthBackground.tsx` | Fond animé multilingue |
| `frontend/src/hooks/useDocumentLibrary.ts` | Bibliothèque (API backend / mémoire) |
| `frontend/src/hooks/useStreamingTranslation.ts` | Streaming SSE + flag `precise` |

### Supprimés
| Fichier | Raison |
|---|---|
| `frontend/src/utils/idbStore.ts` | Remplacé par API backend |

---

## Environnement (.env)

```bash
# backend/.env
DATABASE_URL=postgresql+asyncpg://postgres:***RETIRE***@127.0.0.1:5432/precis
JWT_SECRET=***RETIRE***
JWT_EXPIRY_MINUTES=60
REFRESH_TOKEN_EXPIRY_DAYS=30
FRONTEND_URL=http://localhost:3000
EMAIL_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=toujoursmoi237@gmail.com
SMTP_PASSWORD=***RETIRE***
GOOGLE_CLIENT_ID=130716245882-d2b9m4gp2ig8mtfkutg9mq5peeukc16o.apps.googleusercontent.com

# frontend/.env
VITE_API_KEY=precis_frontend_secure_key_2026_xK9mP2vL
VITE_API_BASE=
VITE_GOOGLE_CLIENT_ID=130716245882-d2b9m4gp2ig8mtfkutg9mq5peeukc16o.apps.googleusercontent.com
```

---

## Commandes utiles

```bash
# Démarrage
npm run dev

# Base de données (première fois)
backend\venv\Scripts\python.exe backend\seed_admin.py

# Tests email
curl -X POST http://127.0.0.1:8000/api/auth/login -H "Content-Type: application/json" -d "{\"email\":\"test@precis.app\"}"
```
