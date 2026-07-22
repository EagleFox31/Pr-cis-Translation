# Frontend — Précis Translator

Interface **React 19 + TypeScript + Vite + Tailwind 4**. Version **1.0.0**.

~7 400 lignes de TSX. Elle ne fait aucun travail lourd : elle envoie un
document, écoute un flux d'événements, et affiche l'aperçu au fil de l'eau.

## Démarrer

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000
```

Depuis la racine, `npm run dev` lance le backend **et** l'interface, avec la
bannière qui rappelle les adresses (localhost + réseau).

```bash
npm run build        # bundle de production -> dist/
npm run lint         # tsc --noEmit — doit être propre
```

En développement, `/api` est **proxyfié** vers `http://localhost:8000`
(`vite.config.ts`). L'interface et l'API sont donc de **même origine** : CORS
n'intervient pas du tout. Il n'entre en jeu qu'en déploiement sur deux domaines.

## La carte

```
src/
  main.tsx        bootstrap React
  App.tsx         splash, providers (auth, Google), routes
  pages/          Home, Login, Register, VerifyEmail
  components/     par domaine : upload, preview, library, pricing,
                  payment, navbar, hero, story, about, comparison, ui
  hooks/          useStreamingTranslation, usePdfPreview,
                  useDocumentLibrary, usePayment, usePricing
  contexts/       AuthContext — session et jeton
  services/api.ts LE seul point d'appel réseau
  lib/            langues, forfaits
  locales/        fr, en (i18next)
  i18n.ts
```

Quatre routes seulement : `/home` (ouverte aux visiteurs), `/login`,
`/register`, `/verify-email`. Tout le reste retombe sur `/home`.

## Deux points à connaître

**`services/api.ts` est le seul endroit qui parle au réseau.** Il pose
`X-API-Key`, le jeton de session, et l'en-tête `Accept-Language` tiré de i18next
— c'est lui qui fait arriver l'e-mail de vérification dans la langue que
l'utilisateur avait sous les yeux, et non celle de son système.

**L'aperçu arrive par morceaux, pas d'un bloc.** `useStreamingTranslation`
écoute un flux SSE : on affiche d'abord tout le document d'origine converti,
puis chaque page traduite se substitue à la sienne dès qu'elle est prête. Un
composant d'aperçu doit donc supporter que le PDF **change sous lui**, pagination
comprise.

## Configuration (`frontend/.env`)

| Variable | Rôle |
|---|---|
| `VITE_API_KEY` | Doit valoir le `FRONTEND_API_KEY` du backend |
| `VITE_API_BASE` | Base de l'API — inutile en dev (proxy Vite) |
| `VITE_GOOGLE_CLIENT_ID` | Connexion Google ; vide = bouton inactif |

> `VITE_API_KEY` voyage dans le bundle : elle est **publique** par nature. Elle
> identifie l'application, elle n'autorise personne. Aucun secret ne doit
> jamais passer par une variable `VITE_`.

## État de ce dossier

Le backend a été restructuré en couches ; **l'interface ne l'a pas encore
été**, et c'est le chantier en cours. Ce qui est déjà repéré :

* `@google/genai` et `GEMINI_API_KEY` (`vite.config.ts`) sont **totalement
  inutilisés** — aucun import dans `src/` ;
* plusieurs composants dépassent 400 lignes en mêlant état, appels et rendu ;
* l'alias `@` pointe la racine du projet, pas `src/`.

La consigne tient en une phrase : **nettoyer et restructurer sans changer le
fonctionnement**. `npm run lint` propre et l'application identique à l'écran
sont les deux seules preuves acceptées.
