# Revue — panneau de compte et bibliothèque (G.6c.a)

Source : audit du diff frontend contre `docs/integration-nouveautes.md` (fiche),
`docs/etude-nouveautes.md` §11 et la maquette `docs/maquettes/nouveautes/panneau-compte.html`.
Décisions de l'utilisateur : ligne verrouillée → proposition de forfait (`setPayFor`) ;
confirmation de « Tout effacer » dans le menu.

| n° | Fichier | Classe | Correction | Statut |
|----|---------|--------|------------|--------|
| 1 | DocumentLibrary.tsx | état sans affichage conforme | compteur `.n` seulement si liste visible | corrigé |
| 2 | DocumentLibrary.tsx, RowMenu.tsx | confirmation hors norme + état collé | confirmation = 2e état du menu ; remise à zéro à la fermeture | corrigé |
| 3 | DocumentCard.tsx | information manquante | langues · archivé | corrigé |
| 4 | index.css | contraste | couleurs grises au lieu de l'opacité | corrigé |
| 5 | DocumentLibrary.tsx | largeur du tiroir | `min(420px, 100vw)` | corrigé |
| 6 | DocumentCard.tsx | action de ligne | verrouillé → proposition de forfait | corrigé |
| 7 | DocumentCard.tsx | nom accessible masque l'état | `aria-describedby` au lieu d'`aria-label` | corrigé |
| 8 | RowMenu.tsx | focus perdu | focus rendu au bouton / ligne voisine | corrigé |
| 9 | RowMenu.tsx | calcul de position | mesurer depuis le haut du bouton | corrigé |
| 10 | index.css | valeur en dur | jetons `--red-700`, `--red-50`, `--shadow-menu`, `--radius-sm` | corrigé |
| 11 | AccountPanel.tsx | lien sans style | lien Forfaits retiré à la demande de l'utilisateur | rejeté (caduc) |
| 12 | AccountPanel.tsx | repli intempestif | ignorer `relatedTarget` nul | corrigé |
| 13 | DocumentLibrary.tsx | état collé | recherche remise à zéro à la fermeture | corrigé |
| 14 | index.css | CSS mort | supprimer `.bal .l…` | corrigé |
| 15 | index.css | règles redéfinies | fusionner `.bal`, `.p-foot` | corrigé |
| 16 | DocumentCard.tsx | texte en dur | clé i18n | corrigé |
| 17 | DocumentLibrary.tsx | texte de secours en dur | retirer le 2e argument de `t` | corrigé |
| 18 | locales | clé morte | supprimer `account.credits_inline` | corrigé |
| 19 | DocumentCard.tsx | entrée de menu hors maquette | pas d'« Aperçu » en cours de traduction | corrigé |
| 20 | DocumentLibrary.tsx | région sans nom | `aria-labelledby` + `tab` sur `.n` | corrigé |
| 21 | AccountPanel.tsx | `aria-controls` orphelin | conditionnel | corrigé |
| 22 | DocumentLibrary.tsx | icône | `Files` au lieu de `FolderOpen` | corrigé |
| 23 | format.ts | date relative | `Math.floor`, commentaire juste | corrigé |
| 24 | index.css | cible tactile | `::after` agrandi | corrigé |
| F1 | integration-nouveautes.md §4, §1.2 | fiche en retard sur le code | clés `nouveautes.panel.*`, signature `formatRelative(iso, locale, now)` | corrigé |
| I1 | DocumentCard.tsx:209,273 | région vive annoncée à l'insertion (créé par n° 7) | annoncer seulement un changement d'état (useRef) ou une zone `aria-live=polite` unique ; plus de `alert` pour un état déjà affiché | corrigé (passe 2) |
| I2 | index.css:2903-2905 | sélecteur trop large (`.t span` touche `.base`/`.ext`) | `.t b .base, .t b .ext { display:block; font-size:inherit; color:inherit }` — défaut aussi dans la maquette | corrigé (passe 2) |
| m1 | RowMenu.tsx:65,129,192 | fonction capturée gardée en état | garder la clé de l'entrée, relire `entries` à la validation | corrigé (passe 2) |
| m2 | locales fr/en:243 | clé morte | supprimer `library.preview_of` | corrigé (passe 2) |
| m3 | index.css:2872,2894,2917,2920 ; DocumentLibrary.tsx:229 | valeur en dur | `--white`, `--radius` | corrigé (passe 2) |
| m4 | integration-nouveautes.md:187 | fiche en retard | ajouter clear_confirm_question, archived_row, ext_text, download_named, pages_abbr, archive_note(_link), storage_required, unlock_label, close | corrigé (passe 2) |
| m5 | index.css:2913,2939 | cibles chevauchantes ≤520px | débordement horizontal 2px ou écart 6px | corrigé (passe 2) |
| m6 | index.css:3005 | cible < 44 px | `::after` vertical -15px | corrigé (passe 2) |
| m7 | DocumentCard.tsx:232 | format non localisé | `Intl.NumberFormat(locale,{style:'percent'})` | corrigé (passe 2) |
| m8 | DocumentCard.tsx:224,254 | état verrouillé muet | `library.unlock_hint` en texte caché dans la sous-ligne | corrigé (passe 2) |
| m9 | RowMenu.tsx:165,189-213 | focus perdu quand les entrées changent | refocaliser la 1re entrée ou fermer | corrigé (passe 2) |
| m10 | RowMenu.tsx:186 | question jamais lue | description sur « Confirmer l'effacement » | corrigé (passe 2) |
| D1 | backend translate.py:493 | reprise d'un document archivé | hors périmètre frontend | corrigé en G.8 : 403 `stockage_requis` avant tout débit, message traduit côté front (`useStreamingTranslation.ts`) |
| C1 | index.css:2910 + maquette:73 | état sans affichage (icône écrasée à 0 px, texte coupé sans « … ») | `.t .st` en bloc avec ellipse, icône en ligne | corrigé (captures G.6c.b) |
