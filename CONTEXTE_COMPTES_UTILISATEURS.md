# CONTEXTE — Comptes utilisateurs, authentification & stockage

_Dernière mise à jour : 2026-07-16 — correctifs 4-6 vérifiés sur le Postgres réel._

> Ce document est le **contexte de référence** pour la fonctionnalité « comptes
> utilisateurs ».

---

## ⚠️ Correctifs 2026-07-14 (audit après reprise)

L'audit du code a révélé **trois bugs critiques** (le doc les disait « testés et
fonctionnels » — ils ne l'étaient pas). Corrigés et vérifiés sur le Postgres réel
(8/8, cf. `scratchpad/verif_comptes.py`) :

1. **Deadlock à chaque traduction connectée** (`app.py`, `translate_endpoint`).
   L'endpoint est `async` mais interrogeait la DB via
   `run_coroutine_threadsafe(coro, loop)` **sur la boucle qui l'exécute**, puis
   `fut.result(timeout=3)` bloquait cette boucle → coroutine jamais exécutée →
   timeout 3 s → repli silencieux `plan="free"`. Effet : **tout compte payant
   rétrogradé en gratuit** (1 page) + **3–6 s de latence** par requête.
   → Corrigé : `Depends(optional_auth)` + `Depends(get_db)`, requêtes en `await`
   direct. Plus aucun `run_coroutine_threadsafe`/`get_event_loop`.

2. **Quota freemium jamais appliqué.** Le compteur mensuel compte les `Document`,
   mais `_save_document_for_user` n'en créait **aucun** pour un plan `free`
   (stockage 0 → `used+size>0` toujours vrai → `return`). Compteur = 0 pour
   toujours → « 1 page/mois » inopérant.
   → Corrigé : le `Document` est le **registre d'usage** ; il est créé pour tout
   compte authentifié (`free` compris), le stockage n'étant facturé que si le
   plan en offre.

3. **Perte de données à la suppression** (`routes/documents.py`).
   `delete_document` faisait `rmtree(dirname(original_path))`, or ce dossier est
   le **cache partagé par hash** commun à tous les comptes → supprimer un doc
   effaçait les traductions d'autrui.
   → Corrigé : on n'efface que les fichiers strictement sous
   `translations/<user_id>/` (garde-fou `commonpath`).

### Correctifs 2026-07-16 (2ᵉ passe — reste des bugs comptes)
4. **Anti-brute-force** (`verify-email` code). Le code à 6 chiffres (1 M
   combinaisons, fenêtre 15 min) n'avait ni compteur ni verrou.
   → Colonne `VerificationCode.attempts` (migration `0002_verif_attempts`) ;
   `verify_email_code` récupère le code actif, incrémente `attempts` à chaque
   erreur, condamne le code après `MAX_CODE_ATTEMPTS = 5` (429). Vérifié DB (6/6).
5. **Email-bombing** (`login`/`register`/`resend`). Un mail était envoyé pour
   n'importe quel email sans throttle.
   → `_generate_verification` refuse (429) si un code a été émis il y a moins de
   `RESEND_THROTTLE_SECONDS = 45`. Vérifié DB.
6. **`translated_path`/`status` jamais mis à jour** → téléchargement servait
   l'ORIGINAL. Le job tourne dans un thread séparé.
   → Lien `job_id → document_id` posé à la création ; `_job_done`/`_job_error`
   reportent `status=done|error` et `translated_path` via `_sync_document_status`
   (moteur dédié `NullPool` — sûr depuis un thread worker, pas de réutilisation
   du pool lié à la boucle principale). Vérifié DB (4/4).

### Re-vérification indépendante (2026-07-16, avant consolidation)

Rejouée **sur le Postgres réel** (`127.0.0.1:5432/precis`), utilisateurs jetables
créés puis supprimés :

| Vérification | Résultat |
|---|---|
| `app.py` s'importe, 20 routes exposées | ✅ |
| Migration `0002_verif_attempts` **appliquée** (`alembic_version = 0002`), colonne `attempts` présente | ✅ |
| Anti-brute-force : 5 essais faux → `attempts` 1→5, messages « N essai(s) restant(s) », puis **429** et code condamné (`used=True`) ; **le bon code est ensuite refusé** | ✅ 6/6 |
| Freemium : compte `free` + 1 doc ce mois → **402** avec le message clair | ✅ |
| **Deadlock (correctif 1)** : compte `pro` + 1 doc ce mois → **200** (accepté). L'ancien code retombait sur `free` après timeout et l'aurait refusé en 402 | ✅ |

> ⚠️ **La migration `0002_verif_attempts` doit être appliquée à tout
> environnement** (elle était appliquée en local mais le fichier n'était pas
> suivi par git — désormais commité). Sans elle, `verify_email_code` casse :
> le code attend `verification_codes.attempts`.
> ```bash
> cd backend && venv/Scripts/python.exe -m alembic upgrade head
> ```

### Recommandation restante (hors périmètre code)
- **Secrets committés** (`.env` reproduit dans ce doc) : mot de passe SMTP,
  `JWT_SECRET` de dev. À révoquer / rotationner avant toute mise en prod —
  action manuelle côté propriétaire du compte. **Non traité à ce jour.**

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

> ⚠️ **Ce fichier est suivi par git ; `backend/.env` ne l'est pas.** Les valeurs
> secrètes ci-dessous ont donc été remplacées par des marqueurs : les recopier
> ici annulait exactement la protection du `.gitignore`. Les vraies valeurs sont
> dans `backend/.env`, et là seulement.
>
> **L'historique git conserve les anciennes versions de ce fichier** : le mot de
> passe applicatif Gmail et celui de PostgreSQL y ont été exposés. Les masquer
> empêche la diffusion future, **pas** la lecture du passé — leur **rotation
> reste obligatoire** avant toute mise en production.

```bash
# backend/.env
DATABASE_URL=postgresql+asyncpg://postgres:<MOT_DE_PASSE_PG>@127.0.0.1:5432/precis
JWT_SECRET=<64+ caractères aléatoires — en générer un NOUVEAU pour la prod>
JWT_EXPIRY_MINUTES=60
REFRESH_TOKEN_EXPIRY_DAYS=30
FRONTEND_URL=http://localhost:3000
EMAIL_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=toujoursmoi237@gmail.com
SMTP_PASSWORD=<MOT_DE_PASSE_APPLICATIF_GMAIL>
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
