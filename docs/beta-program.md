# Programme Bêta Précis

L'administration se trouve dans le menu Administration → Bêta-testeurs,
à l'adresse /admin/beta. Aucun programme ni participant n'est activé au
déploiement.

## Paramètres de départ

- 40 places au maximum : 20 dès l'ouverture, 40 accessibles un mois plus tard.
- Deux mois calendaires pour créer et activer les invitations.
- 30 jours d'accès à partir de l'activation individuelle, sans renouvellement.
- Par personne : 20 pages PDF, 20 diapositives PowerPoint, 10 000 mots Word,
  10 feuilles Excel et 5 000 mots Excel cumulés.

Le compteur Word mesure le texte extrait par le moteur, y compris les en-têtes,
pieds de page et zones de texte pris en charge. Il ne prétend pas compter des
pages physiques. Le compteur Excel couvre le texte extrait par le moteur :
cellules, noms d'onglets, graphiques et autres parties prises en charge.
Les balises de mise en forme et valeurs purement numériques ne sont pas des
mots ; les caractères CJK sans espace sont comptés individuellement.

## Ouvrir et gérer

1. Créer le programme : il est enregistré en brouillon, fermé.
2. Vérifier les paramètres puis ouvrir les inscriptions. Le calendrier
   démarre à cette ouverture ; le fermer et le rouvrir ne remet pas les dates
   à zéro.
3. Créer une invitation avec l'e-mail du testeur et son format principal.
4. Copier le lien /beta et le partager avec la personne. La création de
   l'invitation n'envoie pas d'e-mail automatiquement.
5. Le testeur se connecte avec cet e-mail vérifié et active son accès.

Le tableau indique l'état, la date de fin et les consommations de chaque
format. Les plafonds individuels sont modifiables. Une révocation/restauration
conserve les consommations et la date de fin ; elle ne renouvelle pas l'essai.
Les invitations jamais activées et révoquées libèrent leur place, contrairement
aux accès déjà activés, qui restent comptés dans les 40.

## Utilisation et retours

Le testeur trouve son invitation et ses quotas dans Mon accès Bêta (/beta),
également accessible depuis son compte. La case Utiliser mon quota Bêta
choisit explicitement ce budget ; la décocher utilise le forfait et les pages
achetées habituels. Un quota insuffisant ne prélève pas ces pages à sa place.
PDF et PowerPoint peuvent être limités par une sélection explicite de pages.
Word et Excel sont admis ou refusés comme documents entiers.

Les documents couverts sont lisibles et téléchargeables en clair. Les usages
restent enregistrés après suppression du document. Une traduction échouée est
remboursée une fois ; une livraison tardive après réconciliation rétablit
sa consommation. Les téléchargements ne réservent aucun nouveau crédit.
Le bouton Donner mon avis ouvre l'assistance avec un retour de bêta prérempli.

Les quotas sont contrôlés côté serveur dans la transaction de création du
document. Les importations simultanées, changements administrateur et
remboursements partagent le verrou du participant.
