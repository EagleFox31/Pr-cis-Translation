---
name: Précis Translator
description: Traduction de documents qui garde la mise en page — identité « papier de cabinet », marine, bleu d'encre et or discret.
colors:
  navy-ink: "#0d1b3e"
  navy-mid: "#162248"
  stamp-blue: "#1a4dc7"
  stamp-blue-bright: "#2563eb"
  blue-wash: "#dbeafe"
  seal-gold: "#c9a84c"
  seal-gold-light: "#f0d98a"
  ivory-paper: "#f9f7f3"
  white: "#ffffff"
  gray-50: "#f8fafc"
  gray-100: "#f1f5f9"
  gray-200: "#e2e8f0"
  gray-300: "#cbd5e1"
  gray-500: "#64748b"
  gray-700: "#334155"
  gray-900: "#0f172a"
  success-green: "#15803d"
  warning-amber: "#b45309"
  danger-red: "#b91c1c"
typography:
  display:
    fontFamily: "Cormorant Garamond, Georgia, serif"
    fontSize: "clamp(2rem, 3.5vw, 3.2rem)"
    fontWeight: 400
    lineHeight: 1.15
    letterSpacing: "-0.01em"
  display-hero:
    fontFamily: "Cormorant Garamond, Georgia, serif"
    fontSize: "clamp(1.7rem, 3.1vw, 3.4rem)"
    fontWeight: 300
    lineHeight: 1.08
    letterSpacing: "-0.02em"
  heading-page:
    fontFamily: "Cormorant Garamond, Georgia, serif"
    fontSize: "26px"
    fontWeight: 600
    lineHeight: 1.25
  heading-dialog:
    fontFamily: "DM Sans, system-ui, sans-serif"
    fontSize: "18px"
    fontWeight: 700
    lineHeight: 1.3
  body:
    fontFamily: "DM Sans, system-ui, sans-serif"
    fontSize: "15.5px"
    fontWeight: 400
    lineHeight: 1.75
  body-ui:
    fontFamily: "DM Sans, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.5
  label-tag:
    fontFamily: "DM Sans, system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.12em"
  mono:
    fontFamily: "DM Mono, monospace"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.4
  wordmark:
    fontFamily: "Pinyon Script, cursive"
    fontSize: "48px"
    fontWeight: 400
    lineHeight: 1
rounded:
  xs: "6px"
  btn: "9px"
  field: "10px"
  card: "12px"
  dialog: "18px"
  panel: "20px"
  pill: "100px"
spacing:
  xs: "6px"
  sm: "12px"
  md: "16px"
  lg: "24px"
  section: "32px"
  frame-max: "1240px"
  nav-h: "72px"
components:
  button-primary:
    backgroundColor: "{colors.stamp-blue}"
    textColor: "{colors.white}"
    rounded: "{rounded.btn}"
    padding: "9px 16px"
    typography: "{typography.body-ui}"
  button-primary-hover:
    backgroundColor: "{colors.stamp-blue-bright}"
  button-secondary:
    backgroundColor: "{colors.white}"
    textColor: "{colors.stamp-blue}"
    rounded: "{rounded.btn}"
    padding: "9px 16px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.gray-500}"
    rounded: "{rounded.btn}"
    padding: "9px 16px"
  badge:
    backgroundColor: "{colors.blue-wash}"
    textColor: "{colors.stamp-blue}"
    rounded: "{rounded.pill}"
    padding: "3px 10px"
  dialog:
    backgroundColor: "{colors.white}"
    textColor: "{colors.gray-900}"
    rounded: "{rounded.dialog}"
    padding: "26px 24px"
  card-document:
    backgroundColor: "{colors.gray-50}"
    textColor: "{colors.navy-ink}"
    rounded: "{rounded.card}"
    padding: "12px 14px"
---

# Design System: Précis Translator

## 1. Overview

**Creative North Star: "Le papier de cabinet"**

Précis se présente comme un document bien tenu : du papier blanc ou ivoire, une encre marine, un tampon bleu pour ce qu'on peut faire, un filet d'or pour ce qui mérite d'être remarqué. Les titres en Cormorant Garamond donnent la voix éditoriale ; tout ce qui se manipule (boutons, compteurs, listes, fenêtres) parle en DM Sans, net et compact. Le site promet de garder la mise en page ; son interface prouve le soin par l'ordre, pas par l'ornement.

L'identité est sobre et vérifiable. Rien ne clignote, rien ne vend plus que ce qui existe. Le bleu porte l'action, le marine porte l'autorité (hero, section À propos, en-têtes de page), l'or reste rare : italique d'un mot dans le hero, sceau du hibou. Les gris ardoise (gray-50 à gray-900) structurent tout le reste.

Ce système refuse le SaaS générique : pas de dégradés violets, pas de cartes à icône répétées à l'infini, pas de chiffres ronds non sourcés, pas de mode sombre.

**Key Characteristics:**
- Serif éditoriale pour les titres, sans-serif pour l'interface.
- Bleu d'encre unique pour l'action ; or réservé à l'accent rare.
- Surfaces blanches sur gray-50, filets gray-200, ombres teintées marine.
- Fenêtres compactes (400–440 px), voile marine flouté.
- Pastilles en pilule pour les statuts et les rubriques.

## 2. Colors

Une palette froide d'encre et de papier, avec un seul accent chaud.

### Primary
- **Bleu tampon** (stamp-blue) : boutons principaux, liens, icônes d'en-tête de fenêtre, filet gauche des titres de section, étiquettes de section.
- **Bleu vif** (stamp-blue-bright) : survol du bouton principal et anneau de focus (2 px, décalage 2 px).
- **Lavis bleu** (blue-wash) : fond des pastilles, des éléments actifs du menu, des bandeaux d'information.

### Secondary
- **Or du sceau** (seal-gold, seal-gold-light) : italique du hero, sceau de la section À propos. Jamais sur un bouton, jamais en fond.

### Neutral
- **Encre marine** (navy-ink) : titres, texte de marque, fonds pleine page (hero, À propos), voile des fenêtres à 45 %.
- **Papier ivoire** (ivory-paper) et blanc : surfaces de lecture.
- **Gris ardoise** gray-50 → gray-900 : fonds de page (50), fonds de contrôle (100), filets (200), puces (300), texte secondaire (500), texte de lecture (700), corps (900).

### Named Rules
**The One Ink Rule.** Une seule couleur d'action : le bleu tampon. Une deuxième couleur saturée sur un bouton ou un lien est une erreur.
**The Rare Gold Rule.** L'or occupe moins de 2 % d'un écran. S'il apparaît sur une fenêtre ou un panneau, il est de trop.
**The Defined Gray Rule.** Seuls gray-50, 100, 200, 300, 500, 700, 900 existent. gray-400 et gray-600 sont référencés dans le code sans être définis : ne pas s'en servir.

## 3. Typography

**Display Font:** Cormorant Garamond (repli Georgia, serif)
**Body Font:** DM Sans (repli system-ui)
**Label/Mono Font:** DM Mono (numéros de section, codes)

**Character:** une serif littéraire, légère et italique quand elle s'émeut, posée sur une sans-serif géométrique et calme. Le contraste dit « document » et « outil » en même temps.

### Hierarchy
- **Display** (400, clamp 2–3.2rem, 1.15) : titres de section de la vitrine, filet bleu de 4 px à gauche, un mot en italique bleu possible.
- **Heading page** (Cormorant 600, 26 px ; 20–22 px sous 900 px) : en-têtes des pages de lecture (légal, extension, et la page Nouveautés).
- **Heading dialog** (DM Sans 700, 18 px) : titres de fenêtre, précédés d'une icône lucide de 20 px en bleu.
- **Body** (15,5 px, 1,75, gray-700) : paragraphes de lecture, mesure ≤ 72 caractères.
- **Body UI** (13 px) : sous-titres de fenêtre, lignes de panneau, boutons md.
- **Label tag** (11 px, 700, capitales, 0,12em) : étiquettes de section et forfaits.

### Named Rules
**The Two Voices Rule.** Cormorant pour ce qu'on lit, DM Sans pour ce qu'on manipule. Jamais de Cormorant dans un bouton, une pastille ou un compteur.

## 4. Elevation

Surfaces plates par défaut ; les ombres sont teintées marine (rgba(13,27,62,…)), toujours décalées vers le bas, jamais un halo coloré. sm pour un contrôle actif, md pour la barre de navigation fixée, lg/xl pour les panneaux flottants, ombre propre aux fenêtres (0 24px 70px, 28 %).

### Named Rules
**The Flat-Until-Lifted Rule.** Une carte posée sur la page n'a qu'un filet gray-200. L'ombre n'apparaît que pour ce qui flotte : barre fixée, tiroir, fenêtre.

## 5. Components

### Buttons
- **Shape:** rayon 9 px (ui-btn), 10 px dans les fenêtres, 12 px sur les pages de lecture (ext-btn, hauteur ≥ 44 px).
- **Primary:** fond bleu tampon, texte blanc, 600. Survol : bleu vif et ombre 0 4px 14px rgba(26,77,199,.28).
- **Secondary:** blanc, texte et filet bleus ; survol lavis bleu.
- **Ghost:** transparent, gray-500, filet gray-200 ; survol gray-50.
- **Focus:** contour 2 px bleu vif, décalage 2 px.

### Chips / Badges
- Pilule 100 px, 11 px/600, 3 px 10 px. Variantes : défaut (lavis bleu), succès (vert), avertissement (ambre), « bientôt » (gris).

### Cards / Containers
- **Carte de document** : fond gray-50, filet gray-200, rayon 12, padding 12/14.
- **Bloc de quota** : fond blanc, filet gray-100, rayon 10, barre de progression de 5 px.
- **Carte de page de lecture** : filet gray-200, rayon 16–20, ombre sm au plus.

### Dialogs
- Voile marine à 45 % flouté de 3 px ; carte blanche rayon 18, padding 26/24, ombre 0 24px 70px rgba(13,27,62,.28).
- Largeur min(400–440 px, 92vw). Fermeture : X lucide 18 px en haut à droite.
- En-tête : icône 20 px bleue + titre 18/700, sous-titre 13 px gray-500. Action principale pleine largeur.

### Navigation
- Barre de 72 px ; liens 14/500 gray-700, actif bleu avec soulignement 1,5 px ; logo hibou + « récis » en Pinyon Script. Menu mobile sous 1100 px, lignes de 48 px.

### Account panel (signature)
- Tiroir droit min(440px, 96vw). En-tête dégradé 158° gray-50 → #eef2ff, avatar teinté, forfait en capitales, blocs de quota, pied à deux boutons.

### E-mail card (signature)
- Carte 540 px, liseré haut de 4 px à la couleur du niveau, logo + « Précis » + pastille de bandeau en capitales, titre 22/700, bouton pleine largeur rayon 10, pied gris 12 px. Tableaux et styles en ligne uniquement.

## 6. Do's and Don'ts

### Do:
- **Do** réutiliser les classes existantes (ui-btn, Badge, legal-page, ext-*, compte) avant d'en créer.
- **Do** écrire chaque chiffre affiché à partir d'une source du code ou du README.
- **Do** garder les cibles tactiles à 44 px au moins sur mobile.
- **Do** utiliser les icônes lucide en trait de 2, à 16–20 px.

### Don't:
- **Don't** utiliser de dégradés violets, de glassmorphism ni de mode sombre.
- **Don't** mettre de l'or sur un contrôle ou un fond.
- **Don't** reprendre « 100 % », « 50+ langues » ou « traducteurs humains certifiés » : ces affirmations ne sont pas sourcées.
- **Don't** présenter la traduction de scans comme ouverte au public tant que le README dit le contraire.
- **Don't** utiliser gray-400 ou gray-600.
