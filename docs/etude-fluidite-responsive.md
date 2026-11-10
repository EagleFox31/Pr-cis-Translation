# Étude — fluidité et responsive de l'application (mission F)

Date : 10/11/2026 · branche `perf/fluidite-responsive`

## 1. Besoin
Navigation fluide (pas de blocage ni de lag), chaque page utilisable sur mobile,
navigation mobile simple, toutes les interfaces vérifiées.

Critères d'acceptation :
- aucune page avec défilement horizontal à 375 / 768 / 1024 / 1440 px ;
- cibles tactiles ≥ 44 px de haut à ≤ 768 px pour la navigation (langue, menu) ;
- `/home` sur mobile moyen (CPU ×4, 1,6 Mb/s) : premier affichage < 3 s,
  temps de blocage total (TBT) divisé par 2 au moins ;
- tsc / lint / build verts, mêmes mesures avant/après.

## 2. Mesures de départ (Playwright)
Scripts : scratchpad de session `audit.py` (14 routes × 4 largeurs, visiteur +
admin simulé) et `perf.py` (build de prod via `vite preview`).

### Chargement de `/home` (build de prod)
| Profil | 1er affichage (FCP) | LCP | TBT | JS transféré | /home → /extension |
|---|---|---|---|---|---|
| Mobile bridé (CPU ×4, 1,6 Mb/s) | **6,9 s** | **8,6 s** | **6,7 s** (une tâche de 3,5 s) | 315 Ko gzip | 1,9 s |
| Bureau | 1,1 s | 1,1 s | 0,4 s | 315 Ko gzip | 0,4 s |

À cela s'ajoute l'**écran de démarrage** : 3 s imposées à **chaque** chargement
de page (`SplashScreen.tsx:16`, `App.tsx:58`), y compris sur `/login`,
`/admin/*` ou au retour d'un lien e-mail.

### Taille du code
- Paquet principal `index-*.js` : **818 Ko** (non compressé) ; seules 7 pages
  sont chargées à la demande (`App.tsx:20-26`). Home, Login, Register,
  VerifyEmail, les 4 pages admin, la page carte, `PdfViewer`, `PaymentModal`,
  les modales (support, invitation) et `motion` (21 fichiers) sont dans le
  paquet de départ, même pour un visiteur qui ne les ouvre jamais.
- Les deux langues (fr 60 Ko + en 56 Ko de JSON) sont incluses d'office
  (`i18n.ts:5-6`).
- CSS unique de 129 Ko.
- `/api/pricing` appelé 3 fois au chargement de `/home` (3 composants).

### Responsive
- **Aucun défilement horizontal** sur les 56 combinaisons page × largeur.
- Aucune erreur JS (hors simulation).
- Cibles tactiles trop petites à 375/768 px, sur toutes les pages : sélecteur
  de langue `FR`/`EN` (37×26), bouton menu (32×24) ; pied de page : liens
  légaux (h 19), e-mail, réseaux (h 23) ; Login/Register : liens « Mot de
  passe oublié », « Créer un compte », « Se connecter » (h 17-20).
- Navigation mobile : un seul tiroir `MobileMenu` déjà partagé par `Navbar`
  (accueil) et `AppBar` (admin, intégrations) → pas de second modèle à retirer ;
  à vérifier : contenu identique, fermeture au changement de page, focus.
- Accueil mobile : sélecteur de langue sans état actif visible (FR et EN
  gris), titre justifié avec de grands blancs (« mise   en   page »).

## 3. Options
| Option | Pour | Contre |
|---|---|---|
| A. Découpage par route (`lazy` sur toutes les pages hors Home) + modales et `PdfViewer` chargés à l'ouverture + préchargement au survol/intention | gain fort sur le 1er chargement, peu risqué, conventions déjà en place (`Suspense`) | un court délai à la 1re ouverture d'une page, compensé par le préchargement |
| B. Écran de démarrage : seulement à la 1re visite (session) et ≤ 1 s, jamais sur une page profonde | supprime 3 s perçues partout | change un élément de marque (à valider) |
| C. Langue chargée à la demande (seule la langue active au départ) | −55 Ko | bascule FR/EN asynchrone (court délai) |
| D. Remplacer `motion` par CSS | paquet plus léger | réécriture de 21 fichiers, risque visuel : **écarté** |
| E. SSR / prérendu complet | meilleur FCP | lourd, hors périmètre : **écarté** (prérendu existant gardé pour `/extension`) |

## 4. Choix recommandé
A + B + C, puis responsive (cibles tactiles, sélecteur de langue, pied de
page, titre mobile), puis dé-doublonnage de `/api/pricing` (cache partagé).
Profilage de la tâche de 3,5 s pendant l'étape A pour confirmer qu'il s'agit
de l'évaluation du paquet + rendu de Home (sinon : correctif ciblé).

## 5. Impacts et risques
- Aucune donnée, migration ni sécurité touchées ; i18n : clés inchangées.
- Prérendu `/extension` (`scripts/prerender.mjs`) à re-vérifier après le découpage.
- Risque : « flash » de chargement entre pages → `Suspense` avec squelette
  discret + préchargement.

## 6. Point à trancher
- Écran de démarrage (B) : 1re visite seulement, ≤ 1 s (recommandé), ou le
  supprimer, ou le garder tel quel.
