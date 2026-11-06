# Étude : afficher les messages de confirmation (admin Bêta)

## Besoin

Sur `/admin/beta`, « Lien d'invitation copié. » s'affiche dans un bandeau bleu pleine largeur en haut de la page.
Le bandeau pousse tout le contenu vers le bas, puis le remonte quand il disparaît (minuterie de 4 s ajoutée le 29/10).
Il est aussi loin du bouton cliqué : l'admin clique en bas de la fiche, et la confirmation apparaît tout en haut, souvent hors de vue.

## Existant

- `AdminBetaPage.tsx` : deux messages de réussite seulement, `beta.saved` (après chaque action) et `beta.copied` (copie du lien).
  Les erreurs utilisent un autre bandeau, rouge (`beta-error`, `role="alert"`).
- Le projet a déjà une notification flottante, `components/ui/Toast.tsx` (`showToast('success', titre)`) :
  - coin haut-droit, sans décaler la page ;
  - disparaît seule (4 s, ou 6 s pour une erreur) ;
  - bouton de fermeture ;
  - couleurs succès / erreur / info / alerte.
- **Défaut trouvé :** le réceptacle des notifications (`ToastContainer`) n'est monté que dans `Home.tsx`.
  Sur les pages admin, `showToast` ne s'affiche donc nulle part.
  Exemple : le changement de forfait sur `/admin/users` (`planChange.ts`, `UserPanel.tsx`) appelle `showToast`, mais l'admin ne voit aucun message.
- `Toast.tsx` n'annonce rien aux lecteurs d'écran : pas de `role="status"` ni de `aria-live`.

## Options

| | Ce que voit l'admin | Pour | Contre |
|---|---|---|---|
| A. Bandeau + minuterie (actuel) | Bandeau en haut, qui disparaît après 4 s | Déjà fait | La page saute deux fois ; message loin du clic |
| B. Notification flottante (Toast existant) | Petite carte verte en haut à droite, par-dessus la page | Rien ne bouge ; même style que le reste du site ; répare au passage `/admin/users` | Reste un peu loin du bouton |
| C. Retour sur le bouton | « Copier le lien d'invitation » devient « ✓ Copié » pendant 2 s, puis revient | Confirmation exactement là où l'on regarde | Ne convient qu'aux actions à un seul bouton (copie) |

## Choix recommandé : B + C

- **Copie du lien → C.** Le bouton affiche « ✓ Lien copié » (icône `Check`, vert) pendant 2 s. Aucun bandeau.
- **Enregistrements → B.** Approbation, invitation, quotas, révocation, programme : `showToast('success', t('beta.saved'))`.
  Le bandeau bleu `beta-notice` et l'état `notice` disparaissent.
- **Erreurs : inchangées.** Elles restent dans le bandeau rouge fixe. L'admin doit pouvoir les lire et agir ; il ne faut pas qu'elles s'effacent toutes seules.
- **Montage global.** `ToastContainer` passe de `Home.tsx` à `App.tsx`, une seule fois pour tout le site. Cela corrige aussi les messages perdus de `/admin/users`.
- **Accessibilité.** Le conteneur des notifications reçoit `role="status"` et `aria-live="polite"`.

## Impacts

- `App.tsx` et `Home.tsx` : déplacement de `<ToastContainer />`.
- `Toast.tsx` : attributs d'accessibilité.
- `AdminBetaPage.tsx` :
  - suppression de `notice` et de sa minuterie ;
  - `showToast` après chaque enregistrement ;
  - état `copied` sur le bouton de copie.
- Locales FR/EN : clé `beta.copied` (« Lien copié » / « Link copied »).
- `beta.css` : la règle `.beta-notice` est retirée si plus rien ne l'utilise.

## Vérification

- tsc, lint, build.
- Captures Playwright :
  - clic sur la copie → « ✓ Copié », puis retour du libellé ;
  - enregistrement → notification en haut à droite, la page ne bouge pas ;
  - `/admin/users`, changement de forfait → la notification apparaît.
