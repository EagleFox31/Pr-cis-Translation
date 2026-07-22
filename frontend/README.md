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
npm run lint         # tsc --noEmit + contrôle des traductions
npm run check:i18n   # les traductions seules
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
  lib/            langues, forfaits, formatage (octets, dates, %)
  locales/        fr, en (i18next)
  i18n.ts
scripts/
  check-i18n.mjs  le seul garde-fou automatique de l'interface
```

### `components/ui/` — les primitives

Tout écran qui a besoin d'un bouton prend `<Button>` ; il n'en réécrit pas un
en style en ligne. `Button`, `IconButton`, `Drawer`, `Avatar`, `ProgressBar`,
`EmptyState`, `Badge`, `Skeleton`, `Toast`.

Leurs états (`:hover`, `:focus-visible`, `:disabled`) vivent dans `index.css`,
bloc « Primitives d'interface ». **Un style en ligne ne sait pas les
exprimer** : le code les simulait en mutant le DOM sur `onMouseEnter`, trois
lignes par bouton — et rien au clavier, où l'on ne voyait aucun état.

Quatre routes seulement : `/home` (ouverte aux visiteurs), `/login`,
`/register`, `/verify-email`. Tout le reste retombe sur `/home`.

## Trois points à connaître

**`services/api.ts` est le seul endroit qui parle au réseau.** Il pose
`X-API-Key`, le jeton de session, et l'en-tête `Accept-Language` tiré de i18next
— c'est lui qui fait arriver l'e-mail de vérification dans la langue que
l'utilisateur avait sous les yeux, et non celle de son système.

**L'aperçu arrive par morceaux, pas d'un bloc.** `useStreamingTranslation`
écoute un flux SSE : on affiche d'abord tout le document d'origine converti,
puis chaque page traduite se substitue à la sienne dès qu'elle est prête. Un
composant d'aperçu doit donc supporter que le PDF **change sous lui**, pagination
comprise.

**`tsc` ne voit pas les traductions.** `t('library.inexistante')` compile sans
broncher et affiche la clé brute à l'écran. `npm run check:i18n` contrôle que toute
clé employée existe, que les deux dictionnaires portent exactement les mêmes
clés, et qu'aucune traduction n'est vide. Il est inclus dans `npm run lint`.

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

Fait :

* ~~`@google/genai` et `GEMINI_API_KEY`~~ retirés — jamais importés, donc jamais
  dans le bundle : ce qu'on gagne est une dépendance de moins à auditer ;
* le **socle** `components/ui/` et `lib/format.ts` ;
* la **barre latérale** (compte + bibliothèque), 444 lignes en un fichier →
  trois composants ; `Échap`, focus et défilement gelé sont venus avec le
  `Drawer` ;
* `check-i18n.mjs`, et les 12 chaînes françaises en dur de la barre latérale
  passées aux dictionnaires.

Reste :

* les autres écrans — Home, Login/Register, Pricing, Preview — encore en styles
  en ligne, plusieurs au-delà de 400 lignes ;
* **43 chaînes françaises en dur** ailleurs dans l'application, dont les
  messages d'erreur de `LoginPage` et `AuthContext` ;
* l'alias `@` pointe la racine du projet, pas `src/`, et **n'est utilisé nulle
  part** (déclaré deux fois : `vite.config.ts` et `tsconfig.json`).

La consigne tient en une phrase : **nettoyer et restructurer sans changer le
fonctionnement**. Et il faut la lire en sachant que l'interface n'a **aucun test
de rendu** : `npm run lint` propre et le build vert ne prouvent ni qu'un écran
s'affiche, ni qu'il s'affiche comme avant. Cette vérification-là reste
manuelle.
