# SRS — Refonte de l'interface utilisateur Précis Translator

> **Software Requirements Specification** · Version 1.0 · 2026-06-11
> Périmètre : frontend React/Vite (+ extension backend pour la progression temps réel)

---

## 1. Introduction

### 1.1 Objet
Refonte complète de l'interface utilisateur de Précis Translator pour offrir une
expérience de navigation fluide, intuitive et **premium**, alignée sur les design
systems des applications de référence (`taskoverflow`, `Academy-Assist-Portail`),
tout en conservant le format **one-page avec snap-scrolling**.

### 1.2 Déclencheurs de la refonte (constats)
| # | Constat | Gravité |
|---|---------|---------|
| C1 | Transition brutale bleu foncé (`#0d1b3e`) → blanc entre le Hero et la section suivante : rupture visuelle sans dégradé ni animation | Élevée |
| C2 | Ordre des sections illogique : l'outil de traduction (cœur du produit, dans `StorySection`) arrive **après** le Pricing, en 5ᵉ position | Élevée |
| C3 | Processus de traduction opaque : simple spinner pendant 1 à 3 minutes, aucune information de progression | Élevée |
| C4 | Visualisation post-traduction perfectible (cadrage, toolbar, comparaison côte à côte) | Moyenne |
| C5 | Identité visuelle hétérogène : 3 familles de polices (Cormorant Garamond, DM Sans, Plus Jakarta Sans), palette navy/or/ivoire sans tokens sémantiques | Moyenne |

### 1.3 Références de design
- `C:\Users\IBRAH\Documents\Projets\taskoverflow` — Tailwind v4 `@theme`, tokens HSL sémantiques (background/foreground/card/muted/accent/border/ring), police Inter, rayons 0.75rem, scrollbar discrète.
- `C:\Users\IBRAH\Documents\Projets\Academy-Assist-Portail` — composants shadcn/ui (cva + variants), boutons `default/outline/secondary/ghost/destructive`, focus rings accessibles, transitions douces.

---

## 2. Description générale

### 2.1 Existant
- **Stack** : React 19 + Vite + Tailwind v4, motion (animations), pdf.js (aperçu), i18next.
- **Structure one-page** (`Home.tsx`) : Navbar → Hero → FeaturesGrid → ComparisonTable → PricingSection → StorySection (outil de traduction + aperçu) → AboutSection.
- **Snap-scroll** : `scroll-snap-type: y mandatory` sur desktop (≥1025px).
- **Flux de traduction** : upload → `POST /api/translate` (bloquant) → blob → aperçu comparatif (PdfViewer double canvas) → téléchargement.

### 2.2 Cible
Une landing one-page premium dont le **produit est immédiatement accessible**,
avec des transitions de sections orchestrées, un design system unifié et un
processus de traduction **transparent** (progression par étapes en temps réel).

---

## 3. Exigences fonctionnelles

### RF-1 — Réordonnancement des sections
Nouvel ordre (de haut en bas) :
1. **Hero** (proposition de valeur + CTA « Traduire un document » → scroll vers §2)
2. **Traduction** (l'outil : upload, langues, options, progression, aperçu) — *promu de la 5ᵉ à la 2ᵉ position*
3. **Fonctionnalités** (grille)
4. **Comparaison** (tableau)
5. **Tarifs** (toggle mensuel/annuel)
6. **À propos / Contact** (footer intégré)

La navbar reflète cet ordre ; le scroll-spy met en évidence la section active.

### RF-2 — Transitions de sections douces (correctif C1)
- **RF-2.1** Aucune jonction de sections ne doit juxtaposer deux fonds de luminosité fortement contrastée sans zone de transition.
- **RF-2.2** Le Hero (fond sombre) se termine par un **dégradé de transition** (navy → slate → background clair) d'au moins 120 px, ou par un séparateur de forme (vague/diagonale SVG) assurant la continuité.
- **RF-2.3** Les sections suivantes alternent des fonds de même famille (`background` ↔ `muted`, jamais sombre↔clair sans transition).
- **RF-2.4** Apparition des contenus au scroll : fade-in + translation Y (≤ 24 px, 0.5–0.7 s, `ease-out`), déclenchée par IntersectionObserver, une seule fois par section.
- **RF-2.5** Le snap-scrolling est **conservé** (desktop), avec `scroll-behavior: smooth` ; sur mobile, défilement libre.

### RF-3 — Design system unifié (correctifs C5)
- **RF-3.1** Tokens sémantiques Tailwind v4 `@theme` calqués sur les références :
  `--color-background`, `--color-foreground`, `--color-card`, `--color-muted`,
  `--color-muted-foreground`, `--color-primary`, `--color-primary-foreground`,
  `--color-accent`, `--color-border`, `--color-ring`, `--color-destructive`.
- **RF-3.2** Palette : conserver l'identité navy de Précis comme `primary`
  (`hsl(222 47% 11%)` ≈ navy actuel) sur fond clair `hsl(210 40% 98%)` ;
  l'or (`--gold`) devient `accent` réservé aux touches premium (badges, highlights).
- **RF-3.3** Typographie : **une seule famille** UI — Inter (ou Plus Jakarta Sans en repli), graisses 400/500/600/700. Suppression de Cormorant Garamond et DM Mono des parcours principaux.
- **RF-3.4** Composants unifiés style shadcn/ui (cva) : Button (default/outline/ghost/secondary), Card, Badge, Input/Select, Progress — focus visible (`ring-3 ring-ring/50`), états disabled, `active:translate-y-px`.
- **RF-3.5** Rayons (`0.75rem` lg), ombres douces, scrollbar fine et discrète (6 px, opacité faible).

### RF-4 — Processus de traduction transparent (correctif C3)
- **RF-4.1** Remplacement du spinner par une **barre de progression dynamique** affichant en temps réel : étape courante + pourcentage + détail.
- **RF-4.2** Étapes affichées (mapping sur le pipeline backend réel) :
  | Étape | Source backend | Pondération indicative |
  |-------|----------------|------------------------|
  | Téléversement | upload HTTP | 0–5 % |
  | Extraction | `extract_text` (page i/N) | 5–20 % |
  | Traduction IA | `translate_json` (lot i/N) | 20–85 % |
  | Génération du document | `inject_translation` (page i/N) | 85–98 % |
  | Finalisation | réponse/cache | 98–100 % |
- **RF-4.3** **Backend — endpoint de progression** : le `POST /api/translate` devient asynchrone par jobs :
  - `POST /api/translate` → `202 { job_id }` (démarre le job en tâche de fond) ;
  - `GET /api/translate/{job_id}/events` → **SSE** (`text/event-stream`) émettant `{ stage, current, total, percent, message }` — branché sur l'infrastructure `progress_callback` existante des moteurs ;
  - `GET /api/translate/{job_id}/result` → fichier traduit (200) ou 425 si en cours ;
  - Compatibilité : conserver le mode synchrone si `?sync=1` (clients existants).
- **RF-4.4** UI de progression : barre principale (pourcentage), libellé d'étape, sous-texte de détail (« Traduction page 3/5 »), animation de pulsation douce pendant les phases longues ; état d'erreur intégré (message + bouton réessayer).
- **RF-4.5** Cache hit (traduction déjà existante) : passage direct à 100 % sans étapes intermédiaires.

### RF-5 — Visualisation post-traduction (correctif C4)
- **RF-5.1** L'aperçu comparatif (original | traduit) occupe la zone de la section Traduction en remplaçant le formulaire, avec **transition animée** (slide/fade) au lieu d'un swap brutal.
- **RF-5.2** Toolbar épurée : pagination (‹ page x/N ›), zoom (−/100 %/+), badges de langues (source → cible), bouton Télécharger (primary) et Nouvelle traduction (ghost), alignés sur le design system.
- **RF-5.3** Les deux panneaux sont synchronisés (page et zoom) ; étiquettes de langue dynamiques (codes réels, plus de « FR — Original » figé).
- **RF-5.4** Mode essai (spotlight au survol) conservé fonctionnellement, restylé aux tokens.
- **RF-5.5** États de chargement des canvas : skeleton à la place d'un canvas vide.

### RF-6 — Navigation
- **RF-6.1** Navbar fixe, fond translucide + blur, ombre au scroll (existant conservé, restylé tokens).
- **RF-6.2** Scroll-spy + indicateur de section actif animé (soulignement glissant).
- **RF-6.3** Menu mobile plein écran avec stagger d'apparition des liens.
- **RF-6.4** Indicateur de progression de scroll vertical discret (points de section, optionnel desktop).

---

## 4. Exigences non fonctionnelles

| ID | Exigence |
|----|----------|
| RNF-1 | **Aucune régression fonctionnelle** : upload, traduction, aperçu, téléchargement, mode essai, i18n fr/en restent opérationnels |
| RNF-2 | Performance : pas de bibliothèque UI lourde supplémentaire ; animations GPU (transform/opacity uniquement) ; `prefers-reduced-motion` respecté |
| RNF-3 | Accessibilité : contrastes AA, focus visible sur tous les interactifs, navigation clavier des sections, `aria-live` sur la barre de progression |
| RNF-4 | Responsive : breakpoints 480 / 768 / 1024 / 1280 ; snap-scroll désactivé < 1025 px (comportement actuel conservé) |
| RNF-5 | Compatibilité : Chrome/Edge/Firefox récents ; SSE avec repli polling (`GET /status`) si EventSource indisponible |
| RNF-6 | Le backend reste compatible avec les clients existants (mode `?sync=1`) |

---

## 5. Architecture de la solution

### 5.1 Frontend
```
src/
├── styles/tokens.css          # @theme — tokens sémantiques (RF-3.1)
├── components/
│   ├── ui/                    # Button, Card, Badge, Progress, Input (cva)
│   ├── layout/SectionShell.tsx# wrapper de section : snap, fond, reveal
│   ├── navbar/                # restylé tokens
│   ├── hero/                  # + bande de transition dégradée (RF-2.2)
│   ├── translate/             # ex-StorySection promue : upload + progress + preview
│   ├── features/ comparison/ pricing/ about/
└── hooks/
    ├── useTranslation.ts      # → useTranslationJob (SSE + états d'étapes)
    └── useSectionReveal.ts    # IntersectionObserver mutualisé
```

### 5.2 Backend (extension progression)
```
app.py
├── POST /api/translate            # 202 {job_id} | mode sync conservé (?sync=1)
├── GET  /api/translate/{id}/events# SSE — relaie progress_callback
├── GET  /api/translate/{id}/result# FileResponse | 425 si en cours
└── jobs.py                        # registre en mémoire {id: queue, état, résultat}
```
Le `progress_callback` déjà présent dans les trois moteurs alimente la queue du
job (aucune modification des moteurs nécessaire — seules les bornes de
pourcentage sont calculées dans `jobs.py`).

---

## 6. Critères d'acceptation

| ID | Critère | Vérification |
|----|---------|--------------|
| CA-1 | Aucune jonction sombre→clair brutale visible en parcourant la page | Revue visuelle des 6 jonctions |
| CA-2 | La section Traduction est accessible en 1 snap depuis le Hero, et via le CTA | Test manuel |
| CA-3 | Pendant une traduction de 5 pages, l'utilisateur voit ≥ 4 mises à jour de progression distinctes avec étapes nommées | Test E2E avec document multi-pages |
| CA-4 | Une traduction en cache affiche 100 % en < 2 s | Test manuel |
| CA-5 | Tous les boutons/inputs partagent les mêmes tokens (audit visuel, aucune couleur codée en dur hors tokens) | Grep `#[0-9a-f]{6}` sur les composants |
| CA-6 | Snap-scrolling fonctionnel desktop, absent mobile | Test 2 viewports |
| CA-7 | `prefers-reduced-motion` désactive les animations de reveal | Émulation devtools |
| CA-8 | Parcours complet (upload → progression → aperçu → téléchargement) sans erreur console | Test E2E |

---

## 7. Hors périmètre (cette itération)
- Authentification / comptes utilisateurs et paiement réel des plans.
- Dark mode (les tokens le permettront ultérieurement).
- Persistance des jobs (registre en mémoire suffisant en mono-instance).
- Refonte du moteur PDF (aucune modification des règles d'injection).

---

## 8. Plan de réalisation proposé

| Lot | Contenu | Dépendances |
|-----|---------|-------------|
| L1 | Design system : tokens + composants ui/ (Button, Card, Badge, Progress, Input) | — |
| L2 | SectionShell + réordonnancement + transitions de jonction + reveals | L1 |
| L3 | Backend jobs + SSE + hook `useTranslationJob` | — (parallélisable) |
| L4 | Section Traduction : upload restylé + barre de progression temps réel | L1, L3 |
| L5 | Aperçu post-traduction : toolbar, transitions, skeletons, badges dynamiques | L1, L4 |
| L6 | Navbar/menu mobile restylés + scroll-spy animé + polish final | L2 |
