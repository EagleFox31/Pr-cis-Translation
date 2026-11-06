# Étude : présenter l'extension Précis et la faire installer sans effort

Date : 02/11/2026. Complète `docs/etude-extension-navigateur.md` §9.

## 1. Besoin

L'utilisateur doit obtenir l'extension en un minimum de gestes, idéalement
« télécharger et lancer », et la découvrir au bon endroit dans le site.

## 2. Existant

- `extension/` : Manifest V3, version 0.1.0, installation manuelle seulement
  (mode développeur, `extension/README.md`). Aucune icône déclarée dans `manifest.json`.
- `src/config.ts` : adresse locale par défaut, à basculer pour la production.
- Site : aucune page, aucun lien ni bandeau ne présente l'extension.
- Décision du 31/10 : Edge et Chrome d'abord, groupe d'essai, puis stores.

## 3. Ce que les navigateurs autorisent

| Navigateur | Fichier téléchargé depuis notre site | Conséquence |
|---|---|---|
| Chrome (Windows, Mac) | Refusé, sauf postes gérés par une politique d'entreprise | Chrome Web Store obligatoire |
| Edge | Boutique officielle gratuite, examen jusqu'à 7 jours ouvrés | Edge Add-ons |
| Firefox | Autorisé si le fichier est signé par Mozilla | Vrai « télécharger et installer », plus tard |

Depuis 2018, un site ne peut plus installer directement : le bouton ouvre la
fiche de la boutique. Le site peut en revanche détecter si l'extension est déjà
présente (`externally_connectable`).

## 4. Options comparées

| Option | Gestes pour l'utilisateur | Pour | Contre |
|---|---|---|---|
| A. Boutiques + page Précis | Clic sur notre bouton, puis « Ajouter » | Confiance, mises à jour automatiques | Examen à chaque version, 5 $ uniques chez Chrome |
| B. Programme `.exe` | Télécharger, lancer, passer l'alerte Windows, accepter dans le navigateur | Impression de simplicité | Passe quand même par la boutique, certificat à acheter, alertes, Windows seul |
| C. ZIP + mode développeur | 5 à 6 gestes techniques | Immédiat, aucun examen | Alarmant, pas de mise à jour, réservé aux essais internes |
| D. Fichier Firefox signé | Clic, puis « Ajouter » | Sans boutique | Firefox seul, portage à vérifier |
| E. Déploiement d'entreprise | Aucun : le service informatique installe | Idéal pour une formation en groupe | Clients gérés uniquement |

## 5. Recommandation

**Option A.** Un seul bouton sur le site, qui reconnaît le navigateur. Le `.exe`
est écarté : il ajoute des gestes et des alertes sans éviter la boutique. Pour
le groupe d'essai, une fiche Chrome « non répertoriée » remplace le ZIP. Les
options D et E viennent plus tard, à la demande.

## 6. Où présenter l'extension

| Endroit | Contenu | Pour qui |
|---|---|---|
| Page publique `/extension` (pièce centrale) | Démonstration avant/après, bouton d'installation, prix, permissions, données, questions fréquentes | Tous, y compris depuis un moteur de recherche |
| Menu et pied de page | Lien « Extension navigateur » | Visiteurs et clients |
| Section de `/home` | Bloc court menant à la page | Visiteurs |
| Bandeau dans l'app, une seule fois | Proposition refermable, sur ordinateur, masquée si déjà installée | Clients connectés |
| Page de bienvenue après installation | Se connecter, épingler l'icône, premier essai | Nouveaux installés |
| Téléphone | Pas de bouton : « à installer sur ordinateur », avec envoi du lien | Visiteurs mobiles |

## 7. Parcours visé

1. Sur `/extension`, le bouton « Ajouter à Edge » ou « Ajouter à Chrome ».
2. La fiche de la boutique s'ouvre : « Ajouter ».
3. La page de bienvenue s'ouvre : connexion et épinglage.
4. Sur une page en langue étrangère : un clic sur l'icône, puis « Traduire ».

## 8. Impacts

- Extension : adresse de production, retrait de `localhost`, icônes, page de
  bienvenue, détection par le site, connexion des comptes Google à vérifier.
- Site : page `/extension` traduite (normes des pages publiques), liens, bandeau.
- Juridique : politique de confidentialité à compléter pour l'extension.
- Boutiques : captures, justification de chaque permission, compte éditeur.

## 9. Risques

- L'accès facultatif à « tous les sites » peut allonger l'examen.
- Chaque correctif attend un nouvel examen : prévoir les versions à l'avance.
- Lien Edge ou Chrome erroné selon le navigateur détecté : prévoir un lien vers
  l'autre boutique sur la page.

## 10. Décisions du 02/11/2026

1. **Option A validée**, `.exe` abandonné : boutiques Chrome et Edge, bouton sur
   notre site.
2. **Nom visible : Précis.** Comptes au nom de la structure qui exploite le
   service, à créer par le propriétaire du produit (pas de compte personnel).
3. **Lancement par lien seulement**, puis public : « Unlisted » sur Chrome,
   « Hidden » sur Edge. Les deux options sont confirmées par la documentation
   officielle (voir Sources).

## Sources

- https://developer.chrome.com/docs/extensions/how-to/distribute/install-extensions
- https://developer.chrome.com/docs/extensions/mv2/inline-faq
- https://developer.chrome.com/webstore/register
- https://blog.chromium.org/2020/03/new-developer-dashboard-and.html?m=0
- https://learn.microsoft.com/en-us/microsoft-edge/extensions/publish/create-dev-account
- https://learn.microsoft.com/en-us/microsoft-edge/extensions/publish/publish-extension
- https://extensionworkshop.com/documentation/publish/self-distribution/
- https://developer.chrome.com/docs/webstore/cws-dashboard-distribution
