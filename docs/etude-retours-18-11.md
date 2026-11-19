# Étude — retours du 18/11/2026

Ordre de traitement, du plus grave au moins grave (structure > aspect > finition).

| # | Problème | Gravité | Constat |
|---|----------|---------|---------|
| 1 | Filigrane sur des pages payées avec un crédit (bêta, pages offertes) | Structure : promesse faite au client | Oubli de la règle (a) (étude traduction libre) dans deux fonctions et dans les CGU (§1) |
| 2 | Pas de mail admin quand il y a du nouveau | Structure : demandes manquées | Seuls les tickets de support envoient un mail (`api/support.py:48`). Rien pour les candidatures bêta, les nouveaux comptes ni les erreurs. |
| 3 | Analyse du document au dépôt : le formulaire compte mal le nombre d'images à traduire réellement (celles qui contiennent du texte lisible et traitable) | Structure si le devis est faux | Précisé le 18/11, à étudier |
| 4 | Bêta : traduction des images dans les documents, plafond par document | Offre | Exclue aujourd'hui (`api/translate.py:431`). Proposition : 30 images par document. |
| 5 | Les nouveautés ne s'affichent pas d'elles-mêmes à l'ouverture | Aspect | À analyser (`components/nouveautes/`) |
| 6 | Soldes « 5/5 » sans unité | Aspect | Afficher le restant avec son unité |
| 7 | Filigrane trop fort sur les pages libres | Aspect | Plus discret, ne pas couvrir le texte |
| 8 | Accueil : « Voir les tarifs » passe à la ligne | Finition | Probable régression du commit ba4ac58 |
| 9 | Journal prod « Script error. » (Chrome 79) | Finition | Script tiers masqué, sans effet client. L'ignorer dans `lib/errorReporting.ts:88`. |
| 10 | Badges de notification dans le menu admin | Nouveau chantier | Après le n°2, avec sa propre étude |

## 1. Filigrane sur les pages payées avec un crédit

### Constat
- Règle (a), décidée et livrée (`docs/etude-traduction-libre.md`, commit c362359) : toute page traduite avec un crédit (offert, bêta, abonnement, achat) appartient au client, nette et téléchargeable. Sa mise en œuvre est incomplète : il reste une exception bêta dans deux fonctions, et les CGU n'ont pas été mises à jour.
  - `api/documents.py:292` `_apercu_filigrane` et `:301` `pages_filigranees` : un document traduit avec des crédits bêta est **toujours** filigrané à l'aperçu, même sur un compte payant (branche `reglages_de(doc).get("beta")`, restée en place). Les pages offertes du Gratuit (`doc.paid`, depuis la règle a) sont déjà nettes, à confirmer par test.
  - CGU `frontend/src/content/legal/fr.ts:82-83` : « mention promotionnelle […] pour les comptes gratuits et pour les bêta-testeurs » ; « les traductions réalisées avec les pages gratuites se consultent en aperçu » (donc pas téléchargeables). Même idée aux lignes 275 et 299 (confidentialité, cookies).
- Incohérence en plus : juste après la traduction, l'aperçu s'affiche filigrané puis redevient net. Depuis la liste des documents, il reste filigrané. Deux chemins d'affichage n'appliquent pas la même règle.
- Le fichier téléchargé n'est jamais filigrané (bêta) : seul l'aperçu est touché.

### Règle en vigueur (a)
Seules les pages traduites **sans crédit** (mode libre) portent le filigrane.

### Options
- **A. Appliquer la règle partout** : bêta et pages offertes du Gratuit nettes et téléchargeables. On modifie les deux fonctions, on aligne l'aperçu affiché après la traduction et on met à jour les CGU (l. 82, 83, 275, 299). Effet : la mention promotionnelle ne finance plus le Gratuit ni la bêta, et les 5 pages gratuites deviennent téléchargeables.
- **B. Bêta nette, Gratuit inchangé** : seuls les crédits bêta deviennent nets. Les 5 pages offertes du Gratuit restent en aperçu filigrané. On modifie moins de code et moins de CGU.
- **C. Garder la règle, corriger seulement l'incohérence** : l'aperçu reste filigrané partout en bêta. C'est contraire à la demande.

### Décision (18/11)
**A** retenue, conforme à la règle énoncée. Tests : pour chaque cas (libre, offert, bêta, payant), on vérifie l'aperçu juste après la traduction, l'aperçu depuis la liste et le fichier téléchargé.

## 2. Mails admin quand il y a du nouveau

### Constat (code vérifié le 18/11)
Trois envois existent déjà. Tous vont aux comptes `admin`, ou à `ADMIN_ALERT_EMAIL` s'il n'y en a aucun.
- **Ticket de support** : un mail à chaque ticket (`api/support.py:48`).
- **Erreurs** : un mail seulement quand 50 erreurs non traitées se sont accumulées, au plus une fois par heure (`services/error_log.py:112`, seuil `ERROR_LOG_ALERT_THRESHOLD`). Avec peu de trafic, ce seuil n'est presque jamais atteint. C'est pourquoi on a l'impression de ne rien recevoir.
- **Solde du fournisseur IA** : alertes quand le solde baisse (`services/solde_ia.py:127`).

Rien n'est envoyé pour une candidature bêta (`api/beta.py:103`) ni pour un nouveau compte. Les comptes sont créés à quatre endroits (`api/auth.py:221, 252, 306, 594` : code par e-mail, mot de passe, Google).

Une tâche tourne déjà une fois par jour (`services/beta_abuse.py:236` `cleanup_loop`). On peut y brancher un récapitulatif quotidien.

### Ce que je propose d'envoyer

| Événement | Quand | Exemple de mail |
|-----------|-------|-----------------|
| Candidature bêta | Tout de suite, un mail par candidature | « Nouvelle candidature bêta : Marie Dupont, traductrice, 40 pages/mois » + bouton « Voir la candidature » |
| Nouveau compte | Une fois par jour, un seul mail qui regroupe tous les comptes de la veille | « 3 nouveaux comptes hier » + la liste des adresses et du mode d'inscription. Aucun mail les jours sans inscription. |
| Erreurs | Dès la 1re nouvelle erreur, puis au plus un mail par heure | « 7 nouvelles erreurs depuis 14 h 00 » + les 3 sources les plus fréquentes + bouton « Ouvrir le journal » |

Pourquoi pas un mail par erreur : une panne produit des dizaines d'erreurs en une minute. On recevrait des dizaines de mails. Avec un mail par heure au maximum, une panne donne un seul mail, puis un rappel par heure tant qu'elle dure.

Pourquoi les comptes en récapitulatif : un nouveau compte ne demande aucune action. Une candidature bêta, si (il faut l'accepter ou la refuser).

### Options
- **A. Le tableau ci-dessus** (recommandé) : rapide pour ce qui demande une action, regroupé pour le reste.
- **B. Tout en récapitulatif quotidien** : un seul mail par jour. Calme, mais une panne peut rester des heures sans être vue.
- **C. Tout en temps réel** : un mail par candidature et par compte, erreurs par heure. Plus de mails, rien n'attend.

### Réalisation (option A)
- Une fonction commune `destinataires_admin(db)` remplace les trois copies actuelles (support, journal, solde IA).
- Candidature : appel après l'enregistrement dans `api/beta.py`, sans jamais faire échouer la candidature si le mail échoue.
- Comptes : récapitulatif ajouté à `cleanup_loop`, avec la date du dernier envoi gardée en base pour ne pas envoyer deux fois après un redémarrage.
- Erreurs : le seuil par défaut passe de 50 à 1 et l'heure de pause est gardée. Le mail indique le nombre et les sources.
- Tests : un test par événement, plus un test « 20 erreurs en une minute donnent un seul mail ».

### Décision (18/11)
**A** retenue, avec les erreurs traitées selon leur gravité. Le journal enregistre déjà trois niveaux (`models/error_log.py:31` : `critical`, `error`, `warning`).

| Gravité | Exemple | Mail |
|---------|---------|------|
| Critique | Le prestataire de paiement refuse l'accès : plus personne ne peut payer (`core/payment_gateway.py:350, 526, 550`) | Tout de suite. Une même panne n'envoie qu'un mail par heure (regroupement par empreinte `fingerprint`). |
| Erreur | Une traduction échoue, une page plante chez un client | Au plus un mail par heure, qui regroupe tout : « 7 nouvelles erreurs depuis 14 h 00 » + les 3 plus fréquentes. |
| Avertissement | Script tiers masqué (« Script error. »), nouvelle tentative réussie | Pas de mail. Le nombre d'avertissements apparaît dans le récapitulatif quotidien, avec les nouveaux comptes. |

Ce qui change dans la réalisation : le seuil de 50 disparaît. Chaque nouvelle entrée du journal déclenche la règle de son niveau.

Aujourd'hui, aucune erreur n'est enregistrée au niveau `critical` : le code n'utilise que `error` et `warning`. Il faut donc choisir lesquelles passent en critique. Je propose de commencer par les trois refus d'accès des prestataires de paiement (Fapshi, Paddle). Elles bloquent tous les achats. On ajoutera d'autres cas un par un, quand une panne réelle le justifie.

## 3. Nombre d'images à traduire annoncé au dépôt

### Constat (code vérifié le 18/11)
Au dépôt, le formulaire affiche « Traduire aussi les N images qui contiennent du texte » et « Avec : jusqu'à X pages ». Ce N vient d'une **détection** seule (`services/images_document.py:227` `detecter`) : une image compte dès que le lecteur y voit **une zone qui ressemble à du texte**. Rien n'est lu à ce stade.

Pendant la traduction, une image n'est remplacée (et payée) que si au moins un bloc a été lu **et** traduit autrement (`services/ocr_v2/image.py:992`). Sont donc comptées au dépôt mais laissées telles quelles :
- un logo ou un nom de marque (« ROPER », « Green Corner ») ;
- des chiffres, des codes, des lettres seules (« A », « B », « 12 % ») ;
- un texte déjà dans la langue cible ;
- un texte trop petit ou flou pour être lu ;
- un texte posé sur un fond transparent.

### L'écart sur un exemple
Un rapport Word de 10 pages avec 8 images : 2 schémas légendés en anglais, 1 logo, 3 graphiques dont les axes n'ont que des chiffres, 2 photos avec une plaque d'immatriculation.
- Le formulaire annonce : « 8 images qui contiennent du texte », « jusqu'à 18 pages ».
- En réalité, 2 images seront traduites : le document coûte 12 pages.

Le client n'est pas surpayé : seules les images remplacées sont débitées (`services/translation_runner.py:92`). Mais le devis est faux, et le contrôle des crédits exige les 18 pages (`api/translate.py:572`) : un client qui a 12 pages se voit dire « crédits insuffisants ». De plus, la traduction libre est coupée dès qu'une image est comptée (`api/translate.py:577`).

### Options
- **A. Lire les images au dépôt et ne compter que le texte traduisible** (recommandé). Après la détection, le lecteur lit les zones trouvées. Une image compte si elle contient au moins un mot de 2 lettres ou plus qui n'est ni un chiffre ni un code. Les lignes lues sont gardées pour la traduction : la lecture n'est pas refaite. Le compte suit alors de près le résultat. Un logo avec un mot (« ROPER ») reste compté : seul le traducteur sait qu'un nom ne se traduit pas. Limite : l'analyse prend plus de temps (quelques secondes par image), dans le même délai maximal de 20 s ; au-delà, le formulaire indique « environ N images ».
- **B. Garder la détection, mais ne plus bloquer sur les images.** Le contrôle des crédits ne compte que le texte ; les images sont traduites tant que le solde le permet, les autres restent en original. Le libellé devient « jusqu'à N images ». Rapide à faire, mais le nombre affiché reste trop haut.
- **C. A et B ensemble.** Compte juste quand la lecture a le temps de se faire ; sinon, pas de blocage sur un compte incertain.

Ma recommandation : **C**. A donne un chiffre juste dans la plupart des cas ; B évite qu'un compte encore approximatif (document lourd, délai dépassé) empêche une traduction que le client peut payer.

### Option D (proposée le 19/11) : proposer les images après la traduction
Au dépôt, on détecte seulement la présence d'images, sans rien promettre. Le texte part en traduction et, en même temps, les images sont lues. À la fin, si des images ont du texte à traduire, l'écran de résultat propose : « 2 images sur 8 contiennent du texte à traduire. Les traduire ? [Traduire (2 pages)] ».

Faisabilité (code vérifié le 19/11) :
- Le document final est refait à chaque téléchargement ou aperçu à partir d'une table d'images posée à côté de la traduction (`translation_runner.py:1551` PDF, `:1606` Word/PowerPoint). Ajouter des images après coup = compléter cette table et vider le cache du rendu, sans retraduire le texte.
- Un précédent existe : « Traduire quand même » une page illisible après la fin (`translation_runner.py:1611`), débité seulement si la page est traduite.
- L'écran existant des images (`DocumentImagesPanel.tsx`, `GET/PATCH /api/documents/{id}/images`) permet déjà de remettre une image à l'original : la proposition s'y branche, pas de nouvel écran.
- Les lignes lues pendant l'analyse sont gardées (`traduire_image(..., lus=)`) : au clic, il ne reste qu'à traduire et repeindre, quelques secondes par image.

Effets :
- Le prix affiché est exact (images réellement traduisibles), et le contrôle des crédits au dépôt ne porte plus que sur le texte : plus de « crédits insuffisants » à tort, et la traduction libre n'est plus coupée par les images.
- Le client attend un peu plus s'il veut les images : un clic, puis quelques secondes par image.
- Solde insuffisant au clic : le bouton mène à l'achat de crédits ; les images restent proposées tant que le document est disponible.

Points à trancher :
- **D1. Toujours demander à la fin** (case « Traduire aussi les images » retirée du dépôt). Simple, prix toujours exact.
- **D2. Garder la case au dépôt** : cochée, les images trouvées sont traduites d'office à la fin, sans clic ; décochée, on propose comme en D1.

Recommandation : **D1**. Un seul parcours, un prix toujours juste, et le client ne paie jamais une image qu'il n'a pas vue proposée. D est préférable à C : le compte n'est plus une estimation sous délai de 20 s, et le dépôt reste rapide.

**Décision : D1 validée le 19/11.** Écarts avec la description :
- les images à texte sont lues et traduites pendant la traduction du texte, sans débit ; le clic ne fait que les poser et débiter une page par image ;
- Excel exclu (pas de mise en page d'images comparable) ;
- pas de proposition pour une sélection de pages, un document bêta ou de structure ;
- les anciens documents déjà traduits avec leurs images restent tels quels.
