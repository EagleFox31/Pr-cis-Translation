# Étude : mail à la personne invitée sur la bêta

## Constat (20/11)
Un admin a invité une personne sur la bêta, et elle n'a reçu aucun mail.
Ce n'est pas une panne : l'envoi n'a jamais été écrit.
- `POST /api/admin/beta/invitations` (`api/beta.py`) crée l'invitation en base, puis s'arrête.
- L'acceptation d'une candidature (`beta_applications.decide`) appelle le même `beta.invite`, sans mail non plus.

Aujourd'hui, on peut aussi inviter une adresse qui n'a pas de compte sur Précis.

## Décisions de l'utilisateur (20/11)
1. **Seuls les utilisateurs inscrits peuvent être invités.** Écrire à quelqu'un qui n'a pas de compte ressemblerait à du spam.
2. **Un seul champ de saisie, pour plusieurs personnes à la fois.** Dans le formulaire d'invitation de l'admin, ce champ permet deux choses :
   - **choisir** un utilisateur dans une liste de suggestions, par nom ou par adresse ;
   - **taper** une adresse directement.

   Une adresse tapée qui ne correspond à aucun compte est refusée avec un message clair.
3. **Bouton « Renvoyer » seulement si le mail n'est pas parti.** Il apparaît à côté de la personne concernée, dans le résultat de l'invitation. Il renvoie le même mail sans recréer l'invitation.

## Existant réutilisable
| Élément | Où | Usage |
|---|---|---|
| Recherche d'utilisateurs | `GET /api/admin/users?q=` (`api/admin_users.py`) | Alimente les suggestions du champ. |
| Formulaire d'invitation bêta | `frontend/src/pages/AdminBetaPage.tsx` | Le champ adresse devient un champ à sélection multiple. Pas de nouvel écran. |
| Carte de mail aux couleurs de Précis | `core/email.py` : `_carte`, `_titre`, `_bouton`, `_atouts` | Même présentation que l'invitation entre utilisateurs. |
| Textes FR/EN | `core/email_content.py` | Nouveau bloc `TEXTES_INVITATION_BETA`. |
| Langue du compte | `User.langue` | Langue du mail. |
| Activation automatique | `GET /api/beta/me` | L'accès s'ouvre à la prochaine visite connectée. |

## Règle retenue
1. **Serveur** : la route d'invitation reçoit une liste d'adresses. Chaque adresse est traitée à part, et le résultat dit, pour chacune :
   - « invité » ;
   - « aucun compte » ;
   - « déjà invité » ;
   - « plus de place ».

   Une adresse refusée ne bloque pas les autres.
2. **Mail** : il part après chaque invitation enregistrée, que ce soit une invitation directe ou une candidature acceptée.
   - Il dit « Vous êtes invité(e) à la bêta de Précis », indique les quotas et propose un bouton « Ouvrir Précis » qui mène à la connexion.
   - Il est écrit dans la langue du compte.
3. **Échec d'envoi** : l'invitation reste valable et l'échec est écrit dans le journal. L'écran admin indique « mail non envoyé » pour la personne concernée, dans le résultat de l'invitation, avec un bouton « Renvoyer ». Ce bouton appelle une route qui renvoie le mail à une personne déjà invitée (refus si elle n'est pas invitée).
4. **Écran admin** : après l'envoi, le résultat s'affiche personne par personne.

## Impacts
- **Données** : aucune migration.
- **Code** :
  - serveur : route d'invitation en liste, vérification du compte, envoi du mail, textes FR/EN ;
  - écran : champ à sélection multiple avec suggestions, et affichage du résultat.
- **Langues** : nouveaux libellés FR/EN pour l'écran et le mail.
- **Tests** :
  - une adresse sans compte est refusée ;
  - une invitation multiple renvoie un résultat par personne ;
  - le mail part à l'invitation et à l'acceptation ;
  - un échec d'envoi n'annule pas l'invitation.

## Branche
`fix/mail-invitation-beta`, partie de `main`. Elle ne dépend ni de #96 ni du travail sur les images.

## Refonte de l'écran (critique du 20/11)

La présentation livrée a été refusée (« gros boutons incohérents »). Une revue de la présentation et un contrôle automatique dans le navigateur, à 1440 et 390 px de large, confirment le refus : note 17/40, 5 critères de charge mentale sur 8 en échec.

### Défauts constatés, du plus grave au plus léger

**Bloquant**
- Le serveur ne retient pas que le mail n'est pas parti. Après un rechargement, la ligne affiche « Invitation envoyée » alors qu'aucun mail n'est parti. Aucune colonne ne porte cette information sur l'inscription.

**Majeurs**
- Dans une même ligne, trois tailles de boutons se côtoient : le gros bouton bleu « Approuver et inviter » (44 px, repris de la page publique), un bouton texte « Ne pas retenir » et des icônes de 32 px. Sur mobile, ces boutons passent sur deux ou trois lignes.
- Le bandeau rouge « mail non parti » s'affiche en haut de la page, loin de la ligne qu'il concerne. Il apparaît en même temps que le message vert « Modifications enregistrées ».
- Le champ d'invitation accepte n'importe quelle adresse tapée, alors que seuls les inscrits peuvent être invités. Ces adresses échouent donc à coup sûr.
- La fenêtre d'invitation a deux défauts d'affichage :
  - le libellé « Format principal » chevauche le texte d'aide ;
  - les adresses choisies débordent à droite sur mobile, et la liste des suggestions est coupée en bas.
- « Approuver » reste proposé sur les candidatures déjà refusées.

**Mineurs**
- Deux styles d'étiquettes d'état coexistent. « En attente » et « Non retenue » sont toutes deux grises.
- La note « approbation impossible, plus de place » est répétée sur chaque ligne. Le bouton « Inviter » reste actif quand la campagne est pleine.
- Chaque candidature occupe environ 190 px de haut, car la motivation et l'encadré « Points à vérifier » sont toujours dépliés.
- Les adresses longues sont coupées sans moyen de les lire en entier.
- Sur mobile, les icônes flottent au milieu de la ligne et les zones cliquables font 32 px au lieu de 44.
- Les libellés ne concordent pas : le bouton dit « Inviter par adresse e-mail », la fenêtre dit « Créer une invitation », et le titre « Participants » couvre aussi les candidatures.
- Le message « Modifications enregistrées » est le même pour toutes les actions.
- La fenêtre d'invitation n'a pas de bouton de fermeture visible.
- Le texte gris de la campagne sélectionnée manque de contraste : 3,9 pour 1 au lieu de 4,5.

**Finitions**
- Clavier : l'option « Ajouter x » n'est pas accessible aux flèches, et le retrait d'une adresse n'est pas annoncé.
- Les boutons de retrait d'une adresse font 24 px.
- Les contours de sélection au clavier ne sont pas homogènes.
- « Modifier les quotas » et « Révoquer » sont proposés sur les accès expirés.

### Ce qui est conservé
- La liste unique, avec les candidatures en tête.
- Le modèle de ligne de l'admin : adresse, informations, étiquette d'état, petites icônes.
- La recherche par suggestions et sa gestion au clavier.
- Le résultat de l'invitation, affiché pour chaque personne.

### Décisions à prendre
1. **Mémoriser « mail non parti »**. Recommandé : ajouter à l'inscription une colonne `mailed_at`, vide tant que le mail n'est pas parti, par une petite migration. Sans cette colonne, l'écran ne peut pas dire vrai après un rechargement. L'alternative sans migration consiste à ranger l'information dans le champ `limits`, ce qui est fragile.
2. **Candidature refusée**. Recommandé : aucune action d'approbation sur une candidature refusée. Pour revenir en arrière, on invite la personne.
3. **Motivation et points à vérifier**. Recommandé : la motivation tient sur une ligne et le texte complet s'affiche au survol. Les points à vérifier deviennent une petite étiquette d'alerte, dont le détail s'ouvre dans la fiche de la personne.
4. **Forme de l'invitation**. Recommandé : garder la fenêtre actuelle, corrigée. Elle est plus étroite, se ferme par une croix et n'accepte que des adresses choisies dans les suggestions. Celles-ci restent dans le champ, sur une ligne, avec une étiquette « +N ».

**Validé par l'utilisateur le 20/11** : les 4 recommandations (migration `mailed_at`, aucune action sur une candidature refusée, motivation sur une ligne + étiquette, fenêtre corrigée).
