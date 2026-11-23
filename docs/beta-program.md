# Programme Bêta Précis

L’encart Programme Bêta est visible dans la section Offres de la page principale.
Il présente les paramètres actuels du programme, sans modifier l’offre Gratuite.
La page /beta reste consultable lorsque les candidatures sont fermées.

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
Une requête qui ne précise pas `use_beta` (client d'API) utilise d'office le
quota Bêta actif s'il couvre le format ; `use_beta=0` l'écarte, `use_beta=1`
l'exige (402 `beta_inactive` sinon).
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

## Candidatures depuis la page publique

Lorsque le recrutement est ouvert, le bouton Demander à participer mène à /beta.
La personne se connecte (ou crée un compte) avec un e-mail vérifié, choisit son
format principal et décrit les documents qu’elle souhaite tester. Le parcours
de connexion par mot de passe, Google ou code conserve le retour vers /beta.
Une candidature est unique par compte et e-mail pour ce programme.

Déposer une candidature ne réserve aucune place et ne donne aucun quota.
Le candidat retrouve sa décision dans Mon accès Bêta. Le contenu des
candidatures et les adresses e-mail ne figurent jamais dans l’API publique.

Dans Administration → Bêta-testeurs, la section Candidatures permet de filtrer
et d’approuver ou de ne pas retenir une demande. Approuver crée une invitation
dans la limite de la vague actuelle ; l’accès commence à l’activation par le
testeur. Une invitation manuelle approuve aussi une candidature correspondante.
Une candidature non retenue peut être réexaminée tant qu’une place est disponible.

La première vague peut être complète tout en acceptant des candidatures pour
la seconde. Lorsque les 40 places au total sont engagées, ou que le recrutement
est fermé ou terminé, aucune nouvelle candidature n’est acceptée. Les décisions
sont consultables dans l’application ; aucun e-mail n’est envoyé automatiquement.
La migration n’ouvre pas le programme et ne crée aucun candidat réel.

## Prévention des accès multiples

La clé de boîte Bêta rapproche les variantes des adresses personnelles Gmail :
points, suffixes + et domaines gmail.com/googlemail.com ; ainsi que les suffixes
+ d'Outlook/Hotmail/Live, iCloud, Proton et Fastmail et les suffixes - de Yahoo
(clé recalculée sur les lignes existantes par la migration `0014_anti_abus`).
Les adresses jetables sont refusées. L'adresse du compte et
celle de l'invitation restent les identités de connexion et d'activation ; la
clé ne fusionne jamais des comptes. Les domaines personnalisés conservent leurs
points et suffixes. Les nouvelles candidatures et invitations d'une même boîte
sont refusées ; le verrou de campagne sérialise ces contrôles. Les anciennes
lignes restent intactes, y compris si elles comportent des alias historiques ;
une deuxième activation d'une même boîte est bloquée.

Les candidatures et premières activations enregistrent l'empreinte HMAC de
l'IP résolue par le serveur (préfixe /64 pour une IPv6) et la machine reconnue par l'anti-abus des pages
offertes (cookie signé, copie locale, empreinte de navigateur :
`docs/etude-anti-abus.md`). Les en-têtes réseau fournis par le client ne sont
pas interprétés : nginx écrase X-Forwarded-For avec l'adresse vue (ou celle
transmise par Caddy, seule source crue, à l'adresse fixe 172.30.250.10) et
uvicorn ne croit cet en-tête que venant d'une adresse privée
(`FORWARDED_ALLOW_IPS`).
Le cookie `precis_device` est signé, HttpOnly, SameSite=Lax, limité à /api et
Secure en production ; il expire après un an et ne sert pas au profilage.
L'ancien cookie `precis_beta_device` n'est plus lu : les lignes bêta antérieures
gardent leur ancienne empreinte d'appareil, sans correspondance pendant leur
fenêtre de 30 jours (IP et boîte restent contrôlées).

Les signaux réseau et navigateur sont utilisés pendant 30 jours, puis effacés
par une purge quotidienne et au démarrage. Les candidatures, décisions,
invitations et consommations sont conservées. Après suppression du compte, la
même purge remplace l'e-mail et la clé de boîte par une empreinte HMAC et efface
la motivation : le même e-mail reste bloqué pour un second essai. L'administration affiche seulement
des rapprochements et des adresses déjà accessibles aux admins : aucun hash,
cookie ou IP n'est servi dans les réponses JSON Bêta. Une candidature suivie de son activation
ne compte pas comme deux personnes.

Les éléments « Points à vérifier » regroupent boîte identique, réseau ou
navigateur commun, et au moins trois adresses liées actives dans la dernière
heure. Un rapprochement réseau ou navigateur ne refuse jamais une décision ou
une activation à lui seul. Un filtre permet d'isoler les candidatures à examiner.

Une fenêtre de dix minutes limite les nouvelles candidatures à cinq par
navigateur et vingt par IP. Ce plafond temporaire renvoie 429 et Retry-After ;
il ne rejette pas la candidature et ne consomme aucun quota. Réenvoyer une
candidature existante conserve le résultat initial. Les compteurs sont dérivés
des lignes persistées sous le verrou de campagne, même après un redémarrage.
La route Google rejoint les inscriptions e-mail avec une limite de cinq
requêtes par minute et par IP. Les connexions habituelles et les crédits payants
ne sont pas remplacés par ces signaux.

Références des règles Gmail :
- https://support.google.com/mail/answer/7436150
- https://support.google.com/mail/answer/22370
- https://support.google.com/mail/answer/10313
