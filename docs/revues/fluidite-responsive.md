# Revue — mission F (fluidité et responsive), 10/11/2026

Passe 1 : /code-review medium sur `595c2f4..HEAD` (10 écarts). Registre :

| # | Où | Classe | Correction | Statut |
|---|---|---|---|---|
| 1 | `BibliothequeHote.tsx` | demande d'ouverture sans hôte monté | `SupportModal` / `InviteModal` montés une fois dans `App.tsx` (retirés de `Home`, `BetaPage`) | corrigé |
| 2 | `Home.tsx` (modales lazy) | demande perdue avant l'arrivée de l'hôte | `supportBus` / `inviteBus` gardent la demande et la remettent à l'abonnement | corrigé |
| 3 | `i18n.ts` | promesse d'import mémorisée même en échec | remise à zéro sur échec + journal | corrigé |
| 4 | `App.tsx` (pages lazy) | fichier de code périmé après mise en ligne → page d'erreur | `avecReprise` (`lib/routes.ts`) : un rechargement par minute au plus, puis l'erreur remonte ; appliqué à toutes les pages, aux modales et au paiement | corrigé |
| 5 | `LazyPaymentModal.tsx` | 1er clic « Payer » sans effet visible sur réseau lent ; échec = page d'erreur | préchargement au repos + `avecReprise` | corrigé |
| 6 | `splash.ts` | effet de bord dans un initialiseur d'état | calcul unique au chargement du module (`SPLASH_ATTENDU`) | corrigé |
| 7 | `Home.tsx` demande du tiroir | demande restée armée si le document n'existe plus | `charge` exposé par `useDocumentLibrary` ; demande effacée + message « Document introuvable » | corrigé |
| 8 | `BibliothequeHote.tsx` aperçu | fichier d'origine téléchargé deux fois | la promesse du tiroir est reprise par l'accueil (`prendreSource`) | corrigé |
| 9 | `pdfjs.ts` | script chargé sans `pdfjsLib` → promesse jamais réglée | garde + rejet | corrigé |
| 10 | `DocumentDemo.tsx` | pdf.js absent → démo jamais « chargée » | `setLoaded(true)` si pdf.js manque | corrigé ; « pdf.js chargé sur l'accueil » **rejeté** : la démo du haut de page en a besoin, le gain visé (plus de script bloquant dans `<head>`) est obtenu |

Vérifications : tsc, lint i18n, build OK ; Playwright sur build (`vite preview`) : support ouvert depuis le tiroir de `/admin/logs` et depuis « Contact » de l'accueil, 0 erreur de page, écran de démarrage absent à la 2e visite.

Passe 2 (contre-revue ciblée, diff + registre) :
- `supportBus` appel sans pré-remplissage perdu : **rejeté**, `prefill` vaut `{}` par défaut (objet vrai), la demande est gardée.
- `sourceEnAttente` périmé si la navigation échoue : **rejeté**, chaque aperçu du tiroir réécrit la source avant de naviguer et l'accueil ne la lit qu'à la réception d'une demande ; seul coût, un fichier gardé en mémoire jusqu'au prochain aperçu.
- `useDocumentLibrary.refresh` : `charge` non levé si la lecture lève une exception → **corrigé** (`finally`).
