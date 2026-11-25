# Invitations par e-mail — étude d'intégration

*20/10/2026. Étude rédigée **après** une première implémentation (branche
`feat/invitations`, non fusionnée) : elle revoit les choix faits et liste ceux
qui restent à trancher avant la fusion.*

---

## 1. Le besoin

Depuis n'importe quel compte, saisir une ou plusieurs adresses e-mail et
envoyer à chacune un message soigné, à la marque Précis, qui invite à découvrir
l'application (https://precis-translator.trigenys.com/).

Trois contraintes en découlent :

- **Le message part sous notre nom.** Chaque abus (spam, hameçonnage déguisé)
  abîme la réputation d'envoi du domaine, donc aussi la livraison des codes
  de connexion.
- **La personne invitée n'a rien demandé.** Le message doit dire qui l'envoie,
  pourquoi, et qu'aucun compte n'a été créé.
- **L'API ne doit pas révéler qui a déjà un compte.**

## 2. Options comparées

### 2.1 Qui envoie le message

| Option | Pour | Contre |
|---|---|---|
| **A. Notre serveur SMTP, expéditeur « Précis », `Reply-To` = l'inviteur** | E-mail de marque, mise en page maîtrisée ; les réponses vont à l'inviteur | Engage la réputation du domaine ; exige des garde-fous |
| B. Expéditeur = l'adresse de l'inviteur | Paraît plus personnel | **Usurpation** : échoue à SPF/DKIM/DMARC, finit en spam ou est rejeté |
| C. Lien `mailto:` ou partage natif (Web Share) | Aucun risque côté serveur, rien à stocker | Pas de marque, rendu laissé au client mail, aucun suivi |

**Retenu : A**, avec C en complément (voir § 4, point 2).

### 2.2 Où placer le point d'entrée

| Option | Remarque |
|---|---|
| **Pied du panneau Bibliothèque, au-dessus de « Aide & support »** (fait) | Toujours accessible, discret, réutilise le modèle de `SupportModal` |
| Après une traduction réussie | Le moment où l'on a envie de recommander ; un rappel ponctuel, pas une bannière permanente |
| Page « Mon compte » | Peu visitée |

**Recommandé :** garder le pied du panneau et ajouter **un** rappel ponctuel
après la première traduction réussie (non fait, à valider).

### 2.3 Garde-fous anti-abus (faits)

| Règle | Valeur | Raison |
|---|---|---|
| Débit | 5 requêtes/min par IP | Empêche le script de rafale |
| Adresses par envoi | 10 | Une invitation n'est pas une campagne |
| Quota | 20 invitations/jour/compte | Plafond de l'usage normal |
| Renvoi (révisé le 16/11, § 6) | même compte → même adresse : 10 min d'écart, 3 par 7 jours ; une adresse : 5 par 7 jours, tous comptes | Renvoi possible si l'e-mail se perd, sans relances en rafale |
| Comptes existants | écartés **sans le dire** | Pas d'énumération des inscrits |
| Contenu | nom et mot échappés, sujet sur une ligne | Pas de lien piégé ni d'injection d'en-tête |
| Échec SMTP | aucune trace enregistrée, 503 si tout échoue | Le quota ne paie pas les pannes |

## 3. Ce qui est en place

- `POST /api/invitations` (`backend/app/api/invitations.py`), table
  `invitations` (migration 0013).
- E-mail fr/en dans la langue de l'interface de l'inviteur, logo embarqué,
  version texte, « pourquoi vous recevez ce message »
  (`backend/app/core/email.py`, `email_content.py`).
- Fenêtre de saisie en pastilles (virgule, Entrée, collage d'une liste) et mot
  facultatif (`frontend/src/components/invite/`).

## 4. Points à trancher avant la fusion

1. **Fournisseur d'envoi.** Le volume d'invitations s'ajoute aux codes de
   connexion. Avec une boîte Gmail en SMTP, la limite est d'environ 500
   messages/jour, et le risque de blocage est réel. Comme l'infrastructure est
   déjà sur AWS, je recommande **Amazon SES** avec SPF, DKIM et DMARC sur
   `trigenys.com`. Il suffit de changer `SMTP_*`, sans toucher au code.
2. **Repli « copier le lien ».** Un bouton dans la fenêtre pour partager le lien
   soi-même (WhatsApp, etc.), utile en Afrique où l'e-mail n'est pas le canal
   principal. Coût faible. *Recommandé.*
3. **Conservation des adresses.** La table garde l'adresse de l'invité pour le
   contrôle des doublons. Au regard du RGPD, la garder plus longtemps que
   nécessaire n'est pas justifié. *Recommandé :* une purge des lignes de plus
   de 30 jours, à lancer avec les tâches de nettoyage existantes.
4. **Attribution / parrainage.** Ajouter `?ref=<id>` au lien pour savoir quelles
   invitations convertissent, voire offrir des pages en récompense. Le
   parrainage récompensé change le cadre juridique (message promotionnel) :
   *à décider, hors de cette branche.*
5. **Rappel après traduction** (§ 2.2) : oui ou non.

### Décisions (20/10/2026)

1. Fournisseur : **SMTP actuel conservé**. SES reste l'option si les envois
   saturent ou partent en indésirables.
2. Bouton « Copier le lien » : **fait** (`InviteModal`, lien = origine du site).
3. Purge à 30 jours : **faite** (`purger_invitations`, au démarrage et à chaque
   envoi).
4. Attribution `?ref=` : non retenue dans cette branche.
5. Rappel après traduction : non retenu.

## 5. Vérifications restantes

- `backend/tests/test_invitations_api.py` à lancer sur une base (garde-fous de
  bout en bout).
- Vérification de la fenêtre dans le navigateur.
- `alembic upgrade head` au déploiement (migration 0013).

## 6. Révision (16/11) : renvoi d'une invitation

### Constat

La règle « même adresse : une fois par 7 jours » s'applique **tous inviteurs
confondus**, et l'interface affiche quand même « envoyé ». Exemple : Paul
invite Marie lundi, l'e-mail tombe en spam ou se perd ; mardi Paul réessaie,
rien ne part, et Paul croit que c'est reparti. Pire : si Jeanne a invité Marie
la veille, l'invitation de Paul n'est jamais envoyée. Un envoi refusé par le
serveur libère déjà la trace (§2), mais un e-mail accepté puis perdu (spam,
filtre) ne peut plus être renvoyé.

### Pratique courante (Slack, Notion, GitHub, Dropbox)

- Le doublon se compte **par couple inviteur → adresse**, pas par adresse seule.
- **Renvoi permis** avec un délai d'attente entre deux envois et un nombre
  maximal de renvois sur une période.
- Un **plafond par adresse, tous inviteurs confondus**, protège le destinataire
  du harcèlement (plus large que le plafond par couple).
- Le quota journalier par compte reste le garde-fou contre le spam.

### Options

| Option | Pour | Contre |
|---|---|---|
| A. Garder la règle actuelle | Rien à faire | Invitation perdue = impossible à renvoyer ; un tiers bloque l'envoi d'un autre |
| B. Doublon par couple inviteur → adresse (7 j), sans renvoi | Simple | Toujours aucun renvoi si l'e-mail se perd |
| **C. B + renvoi encadré + plafond par adresse** | Conforme à l'usage ; renvoi possible ; destinataire protégé | Trois compteurs au lieu d'un |

### Choix recommandé : C

| Règle | Valeur proposée |
|---|---|
| Délai entre deux envois du même inviteur à la même adresse | 10 min |
| Envois du même inviteur à la même adresse | 3 par 7 jours (1 envoi + 2 renvois) |
| Envois à une même adresse, tous inviteurs confondus | 5 par 7 jours |
| Quota par compte | 20/jour (inchangé) |
| Comptes existants | toujours écartés sans le dire (anti-énumération, inchangé) |
| Envoi refusé par le serveur | trace effacée, ne compte pas (inchangé) |

### Impacts

- Données : aucune migration ; la table `invitations` a déjà `inviter_id`,
  `email`, `created_at`. Index simples sur `email` et `created_at` : suffisants
  (table purgée à 30 jours).
- Code : la requête `recentes` de `backend/app/api/invitations.py` devient deux
  comptages (couple, adresse) et un contrôle du dernier envoi ; tests associés.
- Interface : message « Déjà invité » quand l'inviteur relance trop tôt ou
  dépasse 3 envois (429, `detail.code` = `renvoi_trop_tot` / `renvoi_limite`) ;
  le reste de la réponse reste muet sur ce qui a été écarté.
- RGPD : conservation 30 jours inchangée.

### Décisions (16/11/2026)

1. Valeurs retenues : 10 min / 3 par 7 j / 5 par 7 j.
2. Message à l'inviteur pour SON propre renvoi : oui (ne révèle rien sur les
   comptes, il sait déjà qui il a invité).

Fait : `backend/app/api/invitations.py`, `InviteModal.tsx` (+ traductions fr/en),
`backend/tests/test_invitations_api.py` (25/25).
