# Fiche d'intégration : Fonctionnalités, fenêtres « Nouveautés », panneau du compte, e-mail

Maquettes de référence : `docs/maquettes/nouveautes/{page,modale-accueil,modale-depuis,panneau-compte,email}.html` et `commun.css`.
Étude : `docs/etude-nouveautes.md`. Ce document la corrige sur trois points : il n'y a pas de journal (la page s'appelle « Fonctionnalités ») ; il n'y a ni « Plus tard » ni « J'ai compris » (la croix seule) ; la fenêtre « depuis » montre tous les éléments avec un défilement interne (pas de limite à 5).
Règle : aucune valeur codée en dur dans le CSS final ; une valeur absente des jetons passe par un jeton à créer (§1.3).

---

## 1. Correspondance maquette → fichiers

### 1.1 Backend

| Élément | Fichier | Nature | Réutilise |
|---|---|---|---|
| Catalogue FR/EN (`FONCTIONNALITES`, `VERSION`, `DATE_VERSION`) | `backend/app/content/nouveautes.py` | nouveau | contenus de `app/content/` |
| Test du catalogue : ids uniques, FR et EN complets, domaine dans {documents, visionneuse, extension, compte}, type dans {nouveaute, amelioration, correctif}, dates ISO | `backend/tests/test_nouveautes_catalogue.py` | nouveau | pytest |
| `users.nouveautes_vues_le`, `abonne_nouveautes`, `abonne_nouveautes_le`, `langue` ; table `nouveautes_envois` | `backend/alembic/versions/0024_nouveautes.py` + `backend/app/models/user.py` | nouveau / modif | chaîne Alembic |
| `GET /api/nouveautes?lang=` (public), `GET /a-voir`, `POST /vues`, `PUT /abonnement {actif}`, `GET` et `POST /desabonnement?jeton=` | `backend/app/api/nouveautes.py` + enregistrement du routeur | nouveau | dépendance d'authentification existante |
| `abonne_nouveautes`, `nouveautes_vues_le` dans la réponse utilisateur | `backend/app/api/auth.py` (`_user_response`, vers l.434) | modif | — |
| Gabarit e-mail (bande, pastille, rubriques, bouton, pied de désabonnement) | `backend/app/services/email.py` (`_carte`) + `email_content.py` | modif | `_carte` |
| Envoi par version, idempotent via `nouveautes_envois` | `backend/scripts/envoyer_nouveautes.py` | nouveau | — |

### 1.2 Frontend

| Maquette / bloc | Fichier | Nature | Réutilise |
|---|---|---|---|
| `page.html` | `frontend/src/pages/FonctionnalitesPage.tsx` + `frontend/src/fonctionnalites.css` (importé par la page, comme `extension-page.css`) | nouveau | navbar publique, `FooterSection` |
| Route paresseuse | `frontend/src/lib/routes.ts` : `fonctionnalites: memo(() => import('../pages/FonctionnalitesPage'))` + `'/fonctionnalites'` dans `PAR_CHEMIN` | modif | `memo`, `avecReprise` |
| Déclaration de la route | `frontend/src/App.tsx`, bloc l.79-99, avant `*` | modif | — |
| Prérendu + sitemap | `frontend/seo/site.json` (entrée `path: /fonctionnalites`, `source: fonctionnalites`) + branche dans `describe()` de `frontend/scripts/prerender.mjs` (l.94-153) | modif | branche `extension` comme modèle |
| Lien du pied | `frontend/src/components/about/AboutSection.tsx` l.154-160 (tableau `links`) | modif | — |
| Lien du menu mobile | `Navbar.tsx` l.26-36 (lien `href: '/fonctionnalites'`, comme `extensionLink`) + icône dans la table de `MobileMenu.tsx` l.23 (`Sparkles`) | modif | — |
| `modale-accueil.html` + `modale-depuis.html` (un composant, deux modes) | `frontend/src/components/nouveautes/NouveautesModal.tsx` | nouveau | structure d'`InviteModal.tsx` (portail, voile, role dialog, Échap) |
| Bus d'ouverture | `frontend/src/components/nouveautes/nouveautesBus.ts` | nouveau | copie de `inviteBus.ts` (`enAttente`) : `openNouveautes(mode)`, `subscribeNouveautes` |
| Données et abonnement | `frontend/src/hooks/useNouveautes.ts` (catalogue, a-voir, `marquerVu`, `setAbonnement`) | nouveau | `services/api.ts` |
| Montage | `App.tsx` l.102 : ajouter `<NouveautesModal />` dans le `Suspense` qui contient `SupportModal` et `InviteModal` ; import paresseux `avecReprise` comme l.16-17 | modif | — |
| Déclenchement automatique | `frontend/src/pages/Home.tsx` (après l'écran de démarrage) | modif | — |
| Interrupteur | `frontend/src/components/ui/Switch.tsx` (role switch, `aria-checked`, tailles `md` 40×24 et `sm` 32×20) | nouveau | — |
| Tiroir (`panneau-compte.html`) | `frontend/src/components/library/DocumentLibrary.tsx` | modif lourde | `Drawer` (`width="min(420px, 100vw)"`), `EmptyState`, `LazyPaymentModal`, `openInvite`, `openSupport` |
| En-tête, solde, ligne Nouveautés | `frontend/src/components/library/AccountPanel.tsx` | réécriture | `Avatar`, `ProgressBar`, `/api/auth/me/usage` |
| Ligne de document | `frontend/src/components/library/DocumentCard.tsx` | réécriture du rendu, logique conservée | `motion.article` (layout, sortie), `STATUTS_REPRENABLES`, `isTrialFor` |
| Menus « … » (ligne et liste) | `frontend/src/components/library/RowMenu.tsx` | nouveau | — |
| Date relative | `frontend/src/lib/format.ts` : `formatRelative(iso, locale, now)` | modif | `Intl.RelativeTimeFormat`, `Intl.DateTimeFormat` |
| Langue source | `frontend/src/hooks/useDocumentLibrary.ts`, `toMeta` l.97-116 : `sourceLang: d.source_lang` | modif | `_doc_response` l'expose déjà |
| Styles du panneau | `frontend/src/index.css` : remplacer `.compte*` (l.~2849), `.biblio*` (l.~2954), `.libdoc*` (l.~3029) par `.p-head`, `.bal`, `.news`, `.docs-head`, `.find`, `.doc`, `.acts`, `.menu`, `.p-foot` | modif | — |
| RGPD | `frontend/src/content/legal/fr.ts` et `en.ts` : finalité « e-mail des nouveautés », base : consentement, retrait par lien ou interrupteur | modif | — |
| Textes | `frontend/src/locales/fr/translation.json` et `en/translation.json` | modif | — |

### 1.3 Jetons

Existants à utiliser : `--navy`, `--navy-mid`, `--blue`, `--blue-bright`, `--blue-light`, `--gray-50/100/200/300/500/700/900`, `--font-display`, `--font-body`, `--font-mono`, `--shadow-sm/md/lg/xl`, `--radius` (12), `--radius-lg` (20), `--transition`, `--nav-h`, `--frame-pad`.

Manquants, à ajouter en fin de `:root` dans `index.css` :

| Jeton | Valeur | Usage |
|---|---|---|
| `--gray-400` | `#94a3b8` | déjà utilisé par `InviteModal` sans être défini (bug existant) |
| `--blue-200` | `#93c5fd` | bordure de la pastille « nouveauté » |
| `--green-50`, `--green-200`, `--green-700` | `#f0fdf4`, `#bbf7d0`, `#15803d` | pastille « amélioration » |
| `--red-50`, `--red-700` | `#fef2f2`, `#b91c1c` | échec, Supprimer, Tout effacer |
| `--radius-sm` | `10px` | lignes, recherche, bouton principal, carré d'icône |
| `--radius-dialog` | `18px` | fenêtres |
| `--shadow-dialog` | `0 24px 70px rgba(13,27,62,.28)` | fenêtres |
| `--shadow-menu` | `0 12px 32px rgba(13,27,62,.16)` | menus |
| `--shadow-drawer` | `-12px 0 40px rgba(13,27,62,.18)` | tiroir |
| `--veil` | `rgba(13,27,62,.45)` (avec `blur(3px)`) | voile |
| `--z-veil`, `--z-dialog` | `1200`, `1201` | alignés sur `.contact-overlay` et `InviteModal` |

Les tailles de police (11 à 15 px) restent des valeurs littérales, comme partout dans `index.css` (pas d'échelle typographique en jetons).

---

## 2. Données affichées

### 2.1 Origine

| Donnée | Source | Existe ? |
|---|---|---|
| Titre, résumé, détail, date, domaine, type des éléments | `GET /api/nouveautes?lang=` (fr ou en) | à créer |
| « Version 1.7.0 · 9 novembre 2026 » | `VERSION` et `DATE_VERSION` du catalogue, dans la même réponse | à créer |
| Comptes du sommaire | calcul côté client | — |
| Fenêtre « depuis » : éléments, nombre, « depuis le 20 octobre 2026 » | `GET /api/nouveautes/a-voir` : `{depuis, elements[]}` (date postérieure à `nouveautes_vues_le`) | à créer |
| Fenêtre d'accueil : 4 éléments | éléments `phare=True`, triés par importance, 4 au plus | à créer |
| Icône d'un élément phare | champ optionnel `icone` (nom lucide) ; à défaut, icône du domaine | à créer |
| État des interrupteurs e-mail | `user.abonne_nouveautes` (AuthContext) | à créer (AuthUser + `_user_response`) |
| Pastille de la ligne Nouveautés | nombre d'éléments de `a-voir` | à créer |
| Avatar, nom, e-mail | `AuthUser` | oui |
| Forfait | `plans.{plan}` | oui |
| « 3 pages offertes restantes » + barre | `/api/auth/me/usage` (`free_translations_remaining`, ou `pages_remaining` / `monthly_pages`) | oui |
| Nom, extension, icône de type | `DocMeta.originalName`, `ext` (txt : icône `File`, et non plus `FileText`) | oui |
| « → FR » | `targetLang` ; `sourceLang` en préfixe seulement s'il ne vaut pas `auto` (aujourd'hui toujours `auto`, `translate.py:147`) | partiel |
| « N p. » | `pageCount` | oui |
| Date | `DocMeta.date` + `formatRelative` : moins de 24 h en relatif ; même année « 3 nov. » ; sinon « 3 nov. 2025 » ; `title` = `formatDate` complet | à créer |
| « Traduction en cours · 7/18 » + barre | `status`, `pagesDone`, `pageCount` | oui |

### 2.2 Éléments retirés ou absents de la maquette : destination

| Élément actuel | Destination (défaut appliqué) |
|---|---|
| Stockage utilisé / limite | retiré de l'affichage ; le quota reste appliqué par le serveur et le message d'erreur d'envoi existe |
| Renouvellement (`account.renews`) | retiré (à valider, §6) |
| Pages achetées (`account.credits`) | conservées sur la ligne de solde si `page_credits > 0` : « … · dont 5 achetées » (c'est leur seul affichage) |
| Accès bêta (`useBeta`) | retiré du panneau ; l'élément « Programme bêta » de la page renvoie vers `/beta` ; le lien `/beta` du menu mobile reste |
| Déconnexion dans l'en-tête | pied du panneau, 3e case |
| « Tout effacer » en deux temps | menu « … » de la liste ; au clic, le menu montre « Confirmer l'effacement » (danger) et « Annuler » |
| Reprendre (`interrupted`, `paused`, `cancelled`) | lien rapide de la ligne (style de « Réessayer ») + 1re entrée du menu |
| Télécharger le partiel (`livrable`) | entrée de menu « Télécharger la partie traduite » |
| Signaler un problème (`openSupport` avec `category: problem` et le document) | entrée de menu dans tous les états, juste avant le séparateur |
| États `scan_reading`, `scan_to_decide`, `resumed_status`, `viewer.stopping` | ligne d'état (2e ligne), style `st--run` |
| Taille du fichier | attribut `title` du nom |
| Vide invité (`library.empty_guest` + connexion) | état vide + bouton de connexion ; pas d'en-tête de compte, de solde ni de ligne Nouveautés ; pied réduit à « Aide & support » |
| Aperçu désactivé en échec sauf `livrable` | « Aperçu » présent dans le menu d'échec seulement si `livrable` |

Vérification en G.6b : chaque ligne de ce tableau est cochée à la main.

---

## 3. Comportements

### 3.1 Panneau du compte

| Élément | Action | Effet |
|---|---|---|
| Ligne `.open` | clic, Entrée | terminé ou livrable : aperçu (actuel) ; en cours : suivi actuel ; verrouillé : `setPayFor` |
| Actions `.acts` (souris : `hover:hover` et largeur d'au moins 521 px) | survol, `:focus-within`, menu ouvert | visibles ; `.when` en `visibility:hidden` |
| Actions en tactile (`hover:none`) ou à 520 px et moins | — | « … » toujours visible ; « Télécharger » direct masqué (il reste dans le menu) |
| Télécharger | clic | `handleDownload` ; essai non payé → `setPayFor` |
| Débloquer, Réessayer, Reprendre (`.doc--quick`) | clic | `setPayFor` ; relance actuelle ; reprise actuelle |
| « … » d'une ligne | clic | menu de l'état, focus sur la 1re entrée ; un seul menu ouvert ; clic dehors, Échap (focus rendu au bouton) ou Tab sortant ferment |
| Menu vers le haut | ouverture | si le bas du menu dépasse le bas de `.list`, classe `.menu--up` (`bottom: calc(100% - 6px); top: auto`) ; mesure dans `useLayoutEffect` |
| Mettre en pause, Annuler | clic | seulement si `doc.jobId && onStop` (règle actuelle) |
| Supprimer | clic | suppression actuelle, sans confirmation (inchangé) |
| Recherche `.find` | saisie | filtre côté client sans requête : nom en minuscules contenant la saisie nettoyée en minuscules ; compteur = total ; Échap vide le champ |
| Ligne Nouveautés `.news` | clic | s'il y a des éléments : ferme le tiroir et ouvre la fenêtre en mode `depuis` ; sinon : `/fonctionnalites` |
| Interrupteur « E-mail » `.mailopt` | clic | bascule immédiate puis `PUT /abonnement` ; échec : retour à l'état précédent + toast |
| « Forfaits » | clic | ferme le tiroir, `/home#pricing` (section `id="pricing"`) |
| Pied | clic | ferme le tiroir puis `openInvite()`, `openSupport()` ou `onLogout` |

z-index : tiroir existant (1100 et 1101) ; dans la liste, menu 10 et ligne au menu ouvert 20 ; fenêtres 1200 et 1201, au-dessus du tiroir.

| État de la liste | Rendu |
|---|---|
| Chargement | 3 `SkeletonCard` de 60 px ; recherche et « … » masqués |
| Erreur | `Alert` + « Réessayer » |
| Vide | `EmptyState` (icône `files`, titre, message, formats en `small` mono) ; recherche, « … » et compteur retirés |
| Aucun résultat | `.nomatch` « Aucun document ne correspond. » |

### 3.2 Fenêtres Nouveautés

| Règle | Détail |
|---|---|
| Mode | `accueil` si `nouveautes_vues_le` est nul ; `depuis` si `a-voir` n'est pas vide ; sinon rien |
| Apparition automatique | connecté, sur `/home`, après l'écran de démarrage, aucune traduction en cours, aucune autre fenêtre ouverte, jamais sur les pages d'autorisation de l'extension, une fois par session (`sessionStorage`) |
| Fermeture (croix, voile, Échap) | `POST /vues` (fermer = vu) |
| Bouton principal | `POST /vues`, fermeture, puis `/fonctionnalites` (accueil) ou `/fonctionnalites#<ancre de l'onglet>` (depuis) |
| Onglets | tablist, flèches gauche et droite, Home, End, `tabindex` itinérant ; onglet vide omis ; nouveauté → `#fonctionnalites`, amélioration → `#ameliorations`, correctif → `#correctifs` |
| Ligne d'abonnement (depuis) | absente si abonné ; clic : `aria-checked=true` + `PUT` ; 260 ms plus tard, remplacée par « Vous recevrez les nouveautés » (`aria-live=polite`) ; échec : retour à l'état initial + toast |
| Option (accueil) | même `PUT` |
| Animation | `rise .35s` seulement sous `prefers-reduced-motion: no-preference` |
| Chargement, erreur | ouverture seulement après réception des données ; en cas d'erreur, rien ne s'ouvre et `/vues` n'est pas appelé |
| Focus | sur la croix à l'ouverture, piégé, rendu à l'élément d'origine |

### 3.3 Page Fonctionnalités

| Élément | Comportement |
|---|---|
| Données | `GET /api/nouveautes?lang=` ; nouvel appel au changement de langue |
| Groupes, domaines | ordre fixe ; domaine vide omis ; tri par date décroissante ; 1er élément du 1er groupe ouvert (`details open`) |
| Sommaire | IntersectionObserver, `rootMargin` = `-90px 0px -70% 0px`, sur les domaines ; groupe actif en `aria-current="true"` ; sous-liste visible pour le groupe actif |
| Ancre à l'arrivée | `#fonctionnalites`, `#ameliorations`, `#correctifs`, `#<groupe>-<domaine>` : défilement après le rendu ; `scroll-margin-top` = `nav-h` + 24 px (+ 60 px sous 900 px) |
| Sous 900 px | `.side` en `display: contents` ; abonnement puis sommaire en onglets collants (`top` = `nav-h`, z-index 5, sous la navbar à 1000) |
| Sous 520 px | pastilles du sommaire masquées ; date en 3e ligne |
| Abonnement | connecté : interrupteur + `PUT` ; invité : bouton « Se connecter pour être averti » vers `/login` avec retour sur la page |
| États | chargement : 3 blocs squelettes ; erreur : `Alert` + « Réessayer » ; vide : impossible (catalogue testé) |

---

## 4. Clés i18n (FR et EN dans les deux fichiers, aucun texte en dur)

Le contenu des éléments vient de l'API dans la langue demandée, pas des fichiers de traduction.

| Préfixe | Clés |
|---|---|
| `fonctionnalites.` | `meta_title`, `meta_description`, `title`, `version` (« Version {{version}} · {{date}} »), `subtitle`, `groups.<groupe>.title` et `.intro` (fonctionnalites, ameliorations, correctifs), `domains.<domaine>` (documents, visionneuse, extension, compte), `toc_label`, `count_aria` (« {{count}} éléments »), `subscribe.title`, `subscribe.hint`, `subscribe.login`, `load_error`, `retry` |
| `nouveautes.` | `welcome.title`, `welcome.subtitle`, `welcome.optin`, `since.title`, `since.subtitle` (« {{count}} changements depuis le {{date}}. », pluriels `_one` et `_other`), `since.tabs_label`, `tabs.nouveaute`, `tabs.amelioration`, `tabs.correctif`, `optin.title`, `optin.hint`, `optin.done`, `cta`, `close`, `subscribe_error` |
| `nouveautes.panel.` | `title` (« Nouveautés »), `count` (« {{count}} élément(s) », pluriels `_one` et `_other`), `email` (« E-mail ») |
| `library.` | nouvelles : `list_options`, `search_placeholder`, `search_aria`, `no_match`, `empty_title`, `empty_message`, `empty_formats`, `status_running`, `status_failed`, `unlock_hint`, `report_problem`, `download_partial_menu`, `row_options` (« Options de {{name}} »), `relative_now`, `clear_confirm_question`, `archived_row`, `ext_text`, `download_named` (« Télécharger {{name}} »), `pages_abbr` (« {{count}} p. »), `archive_note`, `archive_note_link`, `storage_required`, `unlock_label`, `close` ; réutilisées : `title`, `confirm_clear`, `cancel`, `preview`, `download`, `unlock`, `retry`, `resume`, `pause`, `cancel_translation`, `delete`, `scan_reading`, `scan_to_decide`, `resumed_status`, `empty_guest`, `download_partial` |
| `footer.` | `features_page` (« Fonctionnalités ») |
| E-mail (backend, `email_content.py`, langue = `users.langue`) | `subject`, `badge`, `title`, `intro`, rubriques, `cta`, `note`, `footer`, `unsubscribe` |

Clés devenues inutiles (`account.renews`, `account.storage_*`, `beta.account_hint`, `beta.my_access`, `library.preview_of`) : à supprimer seulement si `grep` ne trouve plus aucun usage.

---

## 5. Accessibilité

| Point | Exigence |
|---|---|
| Fenêtres | `role=dialog`, `aria-modal=true`, `aria-labelledby` vers le h2 ; focus piégé ; Échap |
| Interrupteurs | `role=switch` + `aria-checked` ; nom par `aria-labelledby`, aide par `aria-describedby` ; cible d'au moins 44 px (pseudo-élément) |
| Onglets | `role=tab` et `tabpanel`, `aria-selected`, `aria-controls` ; panneau en `tabindex=0` (défilable au clavier) |
| Pastilles de compte | `aria-label` « {{count}} éléments » |
| Menus « … » | bouton avec `aria-haspopup="menu"` + `aria-expanded` ; `role=menu` et `menuitem` ; flèches haut et bas |
| Recherche | `input type=search` avec `aria-label` ; police 16 px en mobile (pas de zoom iOS) |
| Ligne en cours | `role=progressbar` + `aria-valuenow`, `aria-valuemax` ; l'échec est dit par le texte, pas seulement par la couleur |
| Sommaire | `nav` avec `aria-label`, `aria-current` |
| Cibles à 520 px et moins | boutons icône 44, entrées de menu 44, recherche 44, ligne Nouveautés 56, onglets 52, croix 44 |
| Focus | `:focus-visible` : contour 2 px `--blue-bright`, décalage 2 px (onglets 1 px, panneau d'onglet −2 px) |
| Contraste | `--gray-500` sur blanc : 4,76:1, limite basse pour du 12 px ; jamais de texte `--gray-500` sur `--gray-100` ; `--gray-300` réservé aux icônes décoratives |
| Mouvement | animations seulement sous `prefers-reduced-motion: no-preference` |

---

## 6. Points à valider (valeur par défaut appliquée)

| Point | Défaut |
|---|---|
| URL de la page | `/fonctionnalites` (même URL en EN, contenu selon la langue) |
| Date des éléments sans version | `2026-07-24`, affichée « juil. 2026 » |
| « Programme bêta » | Fonctionnalités, domaine compte |
| « Polices PDF » | Améliorations, documents |
| « PowerPoint : pause, reprise, annulation » | Améliorations, documents |
| Onglet « Nouveautés » de la fenêtre, alors que le groupe de la page s'appelle « Fonctionnalités » | « Nouveautés » conservé, ancre `#fonctionnalites` |
| La navbar a déjà une ancre « Fonctionnalités » (`#features` de l'accueil), homonyme de la page | navbar inchangée ; la page est accessible par le pied, le menu mobile, le panneau et les fenêtres |
| Lien « Forfaits » | `/home#pricing` |
| Renouvellement retiré du panneau | retiré |
| Langue source | « → EN » seule tant que `source_lang` vaut `auto` |
| Titres de la fenêtre d'accueil (« Vos documents gardent leur mise en page »…) | titres des éléments phares ; s'ils doivent différer de ceux de la page, ajouter un champ `titre_court` |

---

## 7. Étapes (branche `feat/nouveautes`)

| Étape | Contenu | Critères d'acceptation |
|---|---|---|
| G.1 | catalogue + test | `pytest tests/test_nouveautes_catalogue.py` vert ; 19 éléments ; FR et EN complets |
| G.2 | migration 0024 + modèle | `alembic upgrade head` puis `downgrade -1` sans erreur ; défauts : `abonne_nouveautes=false`, `nouveautes_vues_le=NULL` |
| G.3 | API + `_user_response` | tests : `a-voir` filtre par date ; `/vues` met la date à jour ; `PUT /abonnement` enregistre `abonne_nouveautes_le` et `langue` ; jeton HMAC invalide : 400 ; `POST /desabonnement` (un clic) : 200 |
| G.4 | e-mail + script | gabarit FR et EN conforme à `email.html` ; lien de désabonnement = jeton signé (la maquette pointe à tort vers `/compte`) ; en-têtes `List-Unsubscribe` et `List-Unsubscribe-Post` ; une 2e exécution du script n'envoie rien |
| G.5 | page + route + prérendu + liens | `/fonctionnalites` servie et prérendue ; présente dans `sitemap.xml` ; ancres fonctionnelles ; captures Playwright à 1280 et 375 px comparées à `page.html`, sans écart visible hors contenu |
| G.6a | fenêtre + bus + déclenchement | règles d'apparition du §3.2 vérifiées par Playwright ; captures à 1280 et 375 px comparées à `modale-accueil.html` et `modale-depuis.html` |
| G.6b | panneau du compte | tableau §2.2 coché ; menu ouvert vers le haut sur les 2 dernières lignes ; tactile émulé (`hasTouch`) : « … » visible ; captures à 1280 et 375 px comparées à `panneau-compte.html` (liste, en cours, échec, verrouillé, vide, aucun résultat) |
| G.7 | RGPD | section ajoutée dans `content/legal/fr.ts` et `en.ts` ; lien depuis l'e-mail |
| G.8 | vérifications | `tsc --noEmit`, `npm run lint`, `npm run build` (prérendu compris), `pytest -q`, Playwright, audit d'accessibilité (axe : aucune violation grave), relecture du diff |

---

## 8. Conflits

- L'intégration part de `perf/fluidite-responsive` APRÈS le commit de F.5b. État constaté : HEAD = `308e8bb` (morceaux paresseux résilients, bus de fenêtres avec file d'attente) ; seuls `PASSATION.md` et `README.md` sont modifiés. F.5b et F.5c (`9c41b73`) semblent donc committés, mais `PASSATION.md` indique encore F.5c « non committé » : à confirmer avant `git switch -c feat/nouveautes`.
- À committer en premier sur la branche : `docs/etude-nouveautes.md`, `docs/maquettes/`, `docs/integration-nouveautes.md`.

| Zone de collision | Avec | Précaution |
|---|---|---|
| `App.tsx` l.16-17 et 102 (fenêtres paresseuses) | F.5b (`avecReprise`) | ajouter une ligne sans réordonner |
| `lib/routes.ts` (`pages`, `PAR_CHEMIN`, `prechargerPage`) | F.5b | même schéma `memo` |
| `inviteBus.ts` et bus du support | F.5b (`enAttente`) | copier le schéma, ne pas factoriser dans cette mission |
| `index.css` (`:root`, `.compte`, `.biblio`, `.libdoc`, `.about-footer`) | F.5c | toucher seulement ces blocs ; jetons ajoutés en fin de `:root` |
| `AboutSection.tsx` l.150-160 | F.5c | un seul lien ajouté |
| `locales/*/translation.json` | toutes les branches | ajouts groupés par préfixe |
| `DocumentCard.tsx`, `DocumentLibrary.tsx`, `AccountPanel.tsx` | worktree `Precis-Translator-extension`, s'il y touche | `git diff main --stat` dans le worktree avant G.6b |
| `scripts/prerender.mjs`, `seo/site.json` | — | une branche de plus dans `describe()` |
