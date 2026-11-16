# Étude : forfaits dans le panneau de compte (16/11/2026)

Demande : afficher la Bêta avec les forfaits dans le panneau latéral, une ligne par forfait,
choisir lequel est utilisé en premier, et une barre repliée qui montre le forfait actif
(nom, expiration ou renouvellement, pages disponibles/total).

## Ce qui existe

- Panneau : `frontend/src/components/library/AccountPanel.tsx`.
  - Ligne repliée : nom du forfait et pages disponibles.
  - Dépliée : une barre, les pages du mois, les pages achetées, la date de renouvellement et la date d'expiration.
  - La Bêta n'y apparaît pas.
- Données :
  - `GET /api/auth/me/usage` (`backend/app/services/usage.py:203`) donne le forfait (gratuit ou payant), son quota, les pages achetées et la date de renouvellement.
  - `GET /api/beta/me` (`useBeta`) donne l'accès Bêta : son état, sa date d'expiration et un quota par format (PDF en pages, PowerPoint en diapositives, Word en pages, Excel en feuilles et en mots).
- Ce qu'un client peut avoir en même temps, au plus trois soldes :
  1. **Bêta** : un quota par format, valable jusqu'à une date, puis perdu.
  2. **Forfait** : gratuit ou payant, jamais les deux. Le gratuit repart le 1er de chaque mois. Le payant repart chaque mois à la date d'achat et expire à une date fixe.
  3. **Pages achetées** : elles n'expirent jamais.
- Ordre de décompte actuel :
  - Bêta d'abord, si la case « utiliser mes crédits Bêta » est cochée (`TranslationSection.tsx:87`, cochée d'office) et que le format est couvert (`translate.py:345`).
  - Puis le forfait, puis les pages achetées (`extension.py:96`, règle « forfait d'abord »).
  - Le choix Bêta oui/non existe déjà côté serveur (`use_beta`). Le choix entre forfait et pages achetées n'existe pas.

## Question 1 : quel solde est actif par défaut ?

Recommandation : **celui qui expire le premier passe en premier**. C'est l'ordre actuel ; on ne le change pas, on l'affiche.

Exemple : Paul a 20 pages Bêta (fin le 30/11), le forfait Starter (80 pages sur 100, qui repartent le 5/12) et 50 pages achetées.
Il envoie un PDF de 10 pages, qui est pris sur la Bêta. Les pages Bêta non utilisées seraient perdues le 30/11, alors que les pages achetées restent.

L'ordre inverse (pages achetées d'abord) ferait perdre des pages au client. Il ne sert à rien.

Cas particulier : un format que la Bêta ne couvre pas (une image, par exemple) passe directement au forfait.
La ligne repliée affiche donc le solde actif **pour un document ordinaire** (PDF).

## Question 2 : changer le solde actif depuis le panneau

- Le choix ne porte que sur **Bêta ou forfait**, car c'est le seul que le serveur sait appliquer.
- Les pages achetées restent une réserve automatique. Elles s'affichent sur leur ligne, mais on ne peut pas les sélectionner.
- Une préférence unique, gardée dans le navigateur, sert à deux endroits :
  - le panneau, avec un bouton radio par ligne ;
  - la case Bêta de la zone de traduction, qui lit la même préférence.
- Cocher l'un met donc l'autre à jour. Cela règle aussi l'ancien point 4 : le client voit où partent ses pages et peut changer avant l'envoi.
- Sans préférence enregistrée : la Bêta si elle est active, sinon le forfait.

## Question 3 : présentation

**Ligne repliée** (la barre visible en permanence), sur deux étages qui tiennent en largeur de panneau :

```
Bêta · PDF                         18 / 20 pages   ▾
████████████████████░░   expire le 30 nov.
```

- Nom du solde actif, avec le format principal pour la Bêta.
- Pages disponibles / total.
- Barre du solde actif.
- Date unique :
  - gratuit : « renouvelé le 1er déc. » ;
  - payant : « expire le … » ;
  - Bêta : « expire le … ».

**Dépliée** : une ligne par solde, l'actif en premier et coché.

```
◉ Bêta              expire le 30 nov.
   PDF 18/20 · PPT 9/10 · Word 5/5 · Excel 2/3
○ Starter           80 / 100 pages · repart le 5 déc. · expire le 5 mars
  Pages achetées    50 (sans expiration, utilisées après le forfait)
```

- La Bêta reprend l'affichage compact par format déjà prêt (`BetaAllowances compact`). Un seul nombre ne peut pas résumer des pages, des diapositives et des mots.
- Accès Bêta expiré ou révoqué : la ligne est grisée avec son état et ne peut pas être choisie.
- Client sans accès Bêta, quand le programme est ouvert : une ligne « Programme Bêta — postuler » mène à `/beta`. C'est le lien demandé entre la Bêta et les forfaits.

## Choix ouverts

1. Format affiché pour la Bêta en ligne repliée :
   - **le format principal du client** (recommandé, connu via `primary_format`) ;
   - ou le format qui a le plus de crédits.
2. Ligne « postuler à la Bêta » pour les clients sans accès :
   - **oui, seulement quand les candidatures sont ouvertes** (recommandé) ;
   - ou jamais.

## Travaux

- Front seulement :
  - `AccountPanel.tsx` : lignes, radio, ligne repliée ;
  - un petit module de préférence partagé avec `TranslationSection.tsx` ;
  - le CSS du panneau ;
  - les clés de traduction fr et en.
- Aucun changement serveur : `use_beta` existe déjà.
- Vérification par Playwright à trois largeurs, dans quatre situations :
  - gratuit seul ;
  - payant et pages achetées ;
  - Bêta, payant et pages achetées ;
  - Bêta expirée.
- Point à confirmer pendant l'implémentation : que devient un forfait payant à son expiration (retour au gratuit attendu, `payments.py:303`).
