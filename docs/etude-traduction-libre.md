# Étude — Traduction libre et pages offertes téléchargeables

Branche : `feat/traduction-libre` (empilée sur `feat/retours-clients`, PR #83 non fusionnée, car les textes de tarifs y ont changé).

## 1. Besoin (règle validée le 16/11/2026)

- (a) Toute page traduite avec un forfait (5 pages offertes du Gratuit, Bêta, abonnement, pages achetées) est en clair : aperçu net et téléchargement.
- (b) Sans forfait ni solde, on peut quand même traduire. Le résultat reste en aperçu filigrané, avec les protections actuelles, sans téléchargement.
- (c) Document mixte (pages couvertes + pages libres) : les pages payées sont en clair, les pages libres en aperçu filigrané. Le client peut télécharger les pages payées seules, ou acheter les pages libres pour avoir le document complet.

Garde-fous validés : plafond par compte et par appareil (20 pages libres par 24 h), déblocage par le paiement par document existant, suppression des traductions libres non débloquées après 30 jours avec un rappel.

### Révision du 17/11/2026 : traduction libre par défaut

Le troisième bouton « Traduire en aperçu » est abandonné. Quand le solde ne suffit pas, on traduit quand même, sans rien demander. Exemple : document de 12 pages, solde de 8 pages.

- **Lancement** : les 8 pages couvertes sont débitées et en clair ; les 4 autres sont traduites en aperçu filigrané. Une ligne sous l'aperçu prévient : « 4 pages sont en aperçu (non payées). [Acheter 4 pages] ».
- **Téléchargement** :
  - le solde couvre maintenant les 4 pages : débit automatique, fichier complet ;
  - le solde en couvre une partie (ex. 1) : débit automatique de cette page, puis fenêtre « 1 page débitée de votre solde. 3 pages non payées ne seront pas dans le fichier. [Acheter 3 pages] [Continuer] » ;
  - le solde est vide : même fenêtre, sans la ligne de débit.
- **« Continuer »** : le fichier ne contient que les pages payées (8 pages ici). Rien de non payé ne sort. Si aucune page n'est payée, seul « Acheter » est proposé.
- **Débit au téléchargement** : sans confirmation, signalé dans la fenêtre.
- **Ancien encart « crédits insuffisants »** : affiché seulement au-delà du plafond (20 pages libres par 24 h), avec ses deux boutons actuels.
- Pages payées : les premières du document (pages 1 à 8 ici), les pages libres sont les dernières. Le débit au téléchargement libère les pages suivantes dans l'ordre.

## 2. Existant

| Sujet | Où | Constat |
|---|---|---|
| Droit au clair | `api/documents.py` `_may_read_clear` | `is_paid_plan(plan) or doc.paid`. Un abonné lit tout en clair : il faut ajouter la condition « aucune page libre ». |
| Calcul au lancement | `api/translate.py:446-618` | `doc_is_paid = not gratuit or achetees > 0` : les pages offertes seules restent verrouillées (contraire à (a)). |
| Manque de crédits | `api/translate.py:575-600` | 402 `need_credits` avec `pages_missing`, `partial_possible` (`covered_only`). Côté interface : `PdfViewer.tsx:655-705` (acheter / traduire les pages couvertes). |
| Anti-abus | `services/anti_abus.py` | Reconnaissance d'appareil (`machine_id`), e-mail vérifié exigé ; ne vise que les pages offertes. |
| Paiement d'un document | `api/payments.py:54-135`, `_apply_credit:475` | Devis et paiement par `document_id`, prix à la page selon la zone ; le surplus (minimum de l'opérateur) va au solde. Prix calculé sur `page_count` (document entier). |
| Relecture d'un scan | `api/documents.py:864` | 402 `insufficient_credits` si le solde ne couvre pas la relecture. Inchangé. |
| Archivage | `services/documents.py:22` | Sans stockage, un document est archivé après 30 jours, jamais effacé. |
| Tâche quotidienne | `services/beta_abuse.py:244` | Boucle de nettoyage toutes les 24 h : on y ajoute la purge. |
| Suppression d'un document | `api/documents.py:942` | Efface la fiche, puis les fichiers devenus orphelins. Réutilisée par la purge. |
| Extension navigateur | `api/extension.py` | Traduit des textes de pages web, sans aperçu ni filigrane : **hors périmètre**, la traduction libre ne s'y applique pas. |

## 3. Options et choix

| Question | Options | Choix |
|---|---|---|
| Mémoriser les pages libres | (1) booléen `paid` seul ; (2) colonne `pages_libres` | **(2)**. Exemple : sur 10 pages dont 3 couvertes, `pages_libres = 7`. Le devis porte sur 7, et l'abonné ne lit pas en clair tant que 7 > 0. |
| Compter le plafond | (1) nouveau type d'usage ; (2) colonne `kind` dans `free_grants` ; (3) table `libre_grants` | **(3)**. Les deux premières options modifieraient des calculs de quota existants. La nouvelle table est purgée après 2 jours. |
| Images remplacées en mode libre | (1) les compter comme pages libres ; (2) les désactiver | **(2)**. Leur facturation se fait après la traduction, selon le résultat : trop de cas à couvrir. Le client est prévenu (« images non traduites en aperçu »). |
| Anciens documents gratuits verrouillés | (1) les laisser ; (2) les débloquer | **(2)** : une migration débloque les documents traduits uniquement avec des pages offertes. La carte Gratuit promet déjà le téléchargement. |

## 4. Fonctionnement retenu

1. **Lancement** : si le solde ne couvre pas tout, le mode libre s'applique d'office (plus de `libre=1` à envoyer). Le serveur consomme les pages couvertes, met le reste en `pages_libres`, et vérifie le plafond (20 pages libres sur 24 h, par compte et par appareil). Au-delà : 402 `need_credits` actuel (acheter / pages couvertes).
2. **Droit au clair, par page** : une page est en clair si son numéro ≤ `page_count - pages_libres` et que le document est couvert (abonnement payant ou `doc.paid`). Aujourd'hui la règle vaut pour tout le document (`_may_read_clear`) : elle devient par page pour l'aperçu.
3. **Téléchargement** : avant de servir le fichier, le serveur débite ce que le solde peut payer et réduit `pages_libres` d'autant. Le fichier ne contient que les pages payées ; la réponse indique les pages débitées et celles restées libres pour la fenêtre « Acheter / Continuer ».
4. **Déblocage** (révisé à l'étape 5.4) : « Acheter N page(s) » règle d'abord avec le solde (`regler-libres`). Le devis ne porte que sur les pages encore libres. Les pages achetées vont au solde, qui les règle aussitôt. Le document passe en `paid` quand toutes ses pages sont réglées, et le surplus reste au solde. Le paiement ciblé d'un document non payé (bibliothèque) met toujours `paid = True` et `pages_libres = 0`.
5. **Purge** : un document avec `pages_libres > 0` est effacé 30 jours après sa création. Un e-mail de rappel part 5 jours avant.
   Règle retenue (17/11) : seul un document **sans aucune page payée** (`paid` faux) est effacé ; un document en partie payé est gardé. Un seul e-mail par compte liste ses documents. La date du rappel est notée dans `reglages` (`rappel_purge`, sans migration) seulement si l'envoi réussit. La suppression n'a jamais lieu moins de 5 jours après le rappel : un rappel en retard repousse la date. Code : `services/purge_libres.py`, branché sur la boucle quotidienne ; tests : `tests/test_purge_libres.py`.

## 5. Impacts

- Données : migration `0027` (colonne `documents.pages_libres`, table `libre_grants`) ; migration `0026` (déblocage rétroactif des pages offertes).
- Coût : une page libre fait travailler le moteur sans rien rapporter. Le plafond limite ce coût à 20 pages par jour et par appareil.
- Sécurité : protections de l'aperçu inchangées (rastérisation `rasterize_for_trial`, filigrane, pas de téléchargement).
- i18n : FR/EN pour la ligne « pages en aperçu », la fenêtre « Acheter / Continuer », le plafond et le rappel.
- E-mails : `backend/app/core/email*.py` est réservé par une autre session. Le rappel sera ajouté en dernier, après vérification que cette réservation est levée.

## 6. Risques

- Lecture de l'aperçu sans payer : risque accepté (règle b). Le plafond le borne.
- Un document supprimé alors qu'un paiement est en cours : déjà géré, le paiement revient au solde (`_apply_credit`).

## 7. Plan

1. Règle (a) : pages offertes en clair, déblocage rétroactif, tests.
2. Mode libre côté serveur : `pages_libres`, plafond, droit au clair, tests.
3. Mode libre d'office : plus de `libre=1`, ligne « N pages en aperçu » sous l'aperçu, aperçu net par page, tests.
4. Téléchargement : débit automatique, fichier limité aux pages payées, fenêtre « Acheter / Continuer », tests et navigation.
5. Déblocage : devis et paiement limités aux pages libres, tests et navigation.
6. Purge à 30 jours et rappel, tests.
7. Textes FR/EN et vérification d'ensemble (tests, build, Playwright 1280/390/320).

## 8. Décisions prises à l'étape 3 (17/11/2026)

- Le mode libre s'applique d'office, sans option à cocher, mais seulement aux PDF (hors bêta).
- Si le client demande aussi la traduction des images, le refus « crédits insuffisants » reste : les images ne passent pas en aperçu.
- « Traduire seulement les pages couvertes » traduit les pages que le solde paie, sans page en aperçu.
- Pour un PDF, le refus « crédits insuffisants » n'apparaît plus que si le plafond de 20 pages en aperçu par 24 h est atteint (`libre_limit`).
- La réponse distingue « lire en clair » (`read_clear` : document payé) et « télécharger » (`can_download` : document payé sans page en aperçu).
- Dans l'aperçu, les pages payées sont nettes et seules les pages en aperçu portent le filigrane. Ce sont toujours les dernières pages de la sélection.
- Sous l'aperçu, une ligne indique « N page(s) en aperçu seulement (non payées) » avec un bouton « Acheter N page(s) ».

## 9. Décisions prises à l'étape 5.3b (téléchargement)

- **Règlement d'office** (`POST /api/documents/{id}/regler-libres`) : au clic sur « Télécharger », le solde paie les pages libres sans rien demander. Ordre : quota mensuel du forfait payant, puis pages achetées. L'offre gratuite n'est jamais prise ici : elle ne s'applique qu'au lancement, avec ses contrôles anti-abus.
- Les pages débitées sont les **premières** pages libres ; les dernières restent libres.
- S'il reste des pages libres, le téléchargement répond 402 `reason=pages_libres`. La fenêtre propose **Acheter** (pages achetées au compte, puis nouveau règlement d'office et fichier complet) ou **Continuer** (`?sans_libres=1` : fichier sans les pages libres, nommé `_PARTIEL`).
- « Continuer » est refusé (402) si aucune page du document n'est payée : la fenêtre ne propose alors que l'achat.
