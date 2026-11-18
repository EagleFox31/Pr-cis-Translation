# Étude — retours du 18/11/2026

Ordre de traitement, du plus grave au moins grave (structure > aspect > finition).

| # | Problème | Gravité | Constat |
|---|----------|---------|---------|
| 1 | Filigrane sur des pages payées avec un crédit (bêta, pages offertes) | Structure : promesse faite au client | Oubli de la règle (a) (étude traduction libre) dans deux fonctions et dans les CGU (§1) |
| 2 | Pas de mail admin quand il y a du nouveau | Structure : demandes manquées | Seuls les tickets de support envoient un mail (`api/support.py:48`). Rien pour les candidatures bêta, les nouveaux comptes ni les erreurs. |
| 3 | Analyse du document au dépôt : le formulaire compte mal le nombre de … | Structure si le devis est faux | Précision attendue de l'utilisateur |
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
