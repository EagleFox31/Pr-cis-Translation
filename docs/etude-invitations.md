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
| Doublon | même adresse : une fois par 7 jours | Personne ne reçoit trois relances |
| Comptes existants | écartés **sans le dire** | Pas d'énumération des inscrits |
| Contenu | nom et mot échappés, sujet sur une ligne | Pas de lien piégé ni d'injection d'en-tête |
| Échec SMTP | aucune trace enregistrée, 503 si tout échoue | Le quota ne paie pas les pannes |

## 3. Ce qui est en place

- `POST /api/invitations` (`backend/app/api/invitations.py`), table
  `invitations` (migration 0010).
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
- `alembic upgrade head` au déploiement (migration 0010).
