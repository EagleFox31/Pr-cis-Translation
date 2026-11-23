# Étude — voile sur les pages non payées (22/11)

## Retour
Une page traduite en aperçu, non payée, ne doit pas être lisible en entier : le voile qui ne laisse voir en clair qu'un cadre sous le curseur doit s'y appliquer.

## Constat (essai en direct, compte gratuit, PDF de 10 pages, 5 pages gratuites restantes)
- Les pages 1 à 5 sont couvertes et les pages 6 à 10 sont traduites en aperçu (« pages libres »).
- Les pages 6 à 10 n'ont que le filigrane léger, sans voile : elles sont lisibles en entier.

## Cause
- Le voile se décide pour tout le document : `isTrialMode = forfait gratuit ET pas de droit au clair` (`frontend/src/pages/Home.tsx:158`).
- Dès qu'une partie du document est payée, le serveur le marque « payé » (`doc.paid`), donc le droit au clair vaut pour tout le document (`read_clear`, `backend/app/api/translate.py:768` ; `_may_read_clear`, `backend/app/api/documents.py:273`).
- Résultat : un document mixte n'a jamais de voile, même sur ses pages libres. L'étude « traduction libre » prévoyait un droit au clair page par page (`docs/etude-traduction-libre.md` §2), mais seul le filigrane a été fait page par page (`pages_filigranees`).

## Options
- **A (recommandé)** : voile page par page. Le serveur donne la liste des pages libres, la même que celle du filigrane (`pages_libres_du_document`). Dans l'aperçu, une page libre a le voile avec le cadre clair sous le curseur, et une page payée reste en clair. Effet : sur le PDF de 10 pages, les pages 1 à 5 se lisent normalement, et les pages 6 à 10 sont voilées sauf sous le curseur.
- B : voile sur tout le document dès qu'il contient une page libre. C'est plus simple, mais le client ne peut plus lire les pages qu'il a payées.

## Périmètre de A
- Serveur : ajouter les numéros des pages libres à la fin de la traduction en direct et à l'ouverture depuis « Mes documents ». Pas de migration.
- Front : `PdfViewer` applique le voile si `isTrialMode` OU si la page affichée fait partie des pages libres. Après l'achat des pages libres, la liste se vide et le voile disparaît (`noterReglement`, `Home.tsx:585`).
- Tests : serveur (liste des pages libres), plus une vérification en direct dans Edge visible (page 5 en clair, page 6 voilée, cadre sous le curseur, voile retiré après achat simulé).

## Retour 2 (22/11) : fluidité

- **Bandeau orange resté après l'achat** : non reproduit. Après l'achat, le bandeau disparaît en moins d'une demi-seconde, et il ne revient ni après un rechargement ni à la réouverture du document. Le règlement enregistré (0 page libre restante) l'emporte bien sur l'état précédent.
- **Scintillement à l'entrée d'une page voilée** : le cadre qui suit le curseur apparaissait en fondu. Or c'est son ombre qui porte le voile. Pendant ce fondu, toute la page restait donc visible un instant. Correction : le cadre s'affiche d'un coup, sans fondu.
- **Filigrane encore visible après le paiement** : le voile était retiré avant l'arrivée de la version sans filigrane. On voyait donc brièvement l'ancienne image, cette fois non voilée. Correction : le voile reste en place jusqu'à ce que la nouvelle version soit affichée.
- Au passage, une alerte technique est corrigée : deux encarts de l'aperçu portaient le même identifiant interne.

## Retour 3 (22/11) : la limite d'aperçu n'est pas annoncée

**Constat.** Au-delà de 20 pages en aperçu sur 24 heures (`anti_abus.LIBRE_MAX_PAGES`), le serveur refuse la traduction. Il renvoie bien `libre_limit: true` (`backend/app/api/translate.py:586`), mais l'interface ne s'en sert pas : elle affiche « Crédits insuffisants », sans parler de limite. Le client ne peut pas comprendre pourquoi l'aperçu lui est refusé. Rien ne l'avertit non plus avant d'atteindre la limite.

**Choix validé (A + complément).**
- Un message dédié remplace « Crédits insuffisants » quand la limite est atteinte. Titre : « Limite d'aperçu atteinte pour aujourd'hui ». Texte : « Vous pouvez traduire jusqu'à 20 pages en aperçu par 24 heures. Vous en avez déjà utilisé 16, et ce document en demande 5 de plus. » Suivent l'heure à laquelle l'aperçu redevient possible, puis les deux boutons habituels. Si le document demande à lui seul plus de 20 pages en aperçu, il n'y a pas d'heure de reprise. Le message dit alors simplement que ce document dépasse la limite.
- Le bandeau orange des pages en aperçu ajoute : « Il vous reste 4 pages d'aperçu aujourd'hui. »
- Au passage, « Traduire seulement les 5 page(s) couverte(s) » devient « Traduire seulement les 5 pages déjà payées », avec un singulier et un pluriel corrects.

**Périmètre.**
- Serveur : le refus renvoie aussi les pages déjà utilisées, la limite, les pages demandées et l'heure de reprise. Cette heure correspond au moment où assez d'aperçus anciens sortent de la fenêtre de 24 heures, en prenant le plus contraignant entre le compte et l'appareil. La réponse de lancement renvoie les pages d'aperçu restantes.
- Interface : le message dédié dans l'encart, et le complément dans le bandeau. Le nombre de pages restantes s'affiche juste après la traduction. À la réouverture depuis « Mes documents », le bandeau reste sans ce nombre, car il change d'un jour à l'autre.
- Tests : la limite atteinte (chiffres et heure de reprise), un document plus grand que la limite, et le nombre restant au lancement.

## Retour 4 (22/11) : pause et reprise quand la limite est atteinte

**Demande.** Quand la limite d'aperçu bloque un document, la traduction doit être enregistrée et rester en pause. On doit pouvoir la continuer le lendemain, après un achat ou autrement.

**Aujourd'hui.** Exemple : PDF de 10 pages, 5 pages payées, 16 pages d'aperçu déjà utilisées aujourd'hui (il en reste 4, il en faudrait 5). Le serveur refuse tout (`translate.py` ~569-593) : aucun document n'est créé, rien n'apparaît dans « Mes documents ». Le client doit acheter, ou choisir « seulement les pages payées », ce qui traduit un document de 5 pages à part et ne se reprend jamais (la sélection réduite pointe vers une autre traduction, voir le commentaire « Pas de reprise tronquée »).

**Ce qui existe déjà et servira.**
- La pause manuelle : statut « En pause », pages faites débitées, reste rendu (`jobs.py` ~451-466).
- Le bouton « Reprendre » de « Mes documents » (`DocumentCard.tsx`) : la reprise renvoie le fichier, réutilise les pages déjà traduites et ne fait payer que le reste.
- L'arrêt après N pages, mais seulement pour les scans (`_avec_budget`, `translation_runner.py` ~1285).
- Limite : une reprise n'a jamais droit à l'aperçu (`not resume_of`, `translate.py` ~555). Le lendemain, la reprise demanderait donc d'acheter tout le reste.

**Options.**
- **A. Traduire jusqu'à la limite, puis pause automatique.** Dans l'exemple : les 5 pages payées et 4 pages d'aperçu sont traduites, puis le document passe « En pause » à 9 pages sur 10. La carte dit : « En pause : limite d'aperçu atteinte. Reprise possible à partir de 14 h 32, ou dès maintenant en achetant 1 page. » « Reprendre » finit la page 10 (en aperçu si la limite le permet, sinon payée). Le client voit tout de suite le maximum de son document.
- **B. Enregistrer sans rien traduire.** Le document apparaît « En pause » à 0 page sur 10, avec la même phrase de reprise. Plus simple, mais le client n'a rien à lire, même pas les pages qu'il a payées.
- **C. Traduire seulement les pages payées, puis pause.** 5 pages sur 10, le reste attend le lendemain ou un achat. Même travail technique que A, pour moins de résultat.

Le panneau du Retour 3 reste dans les trois cas, avec un troisième choix « Mettre en pause et reprendre plus tard » (A, C) ou le comportement automatique (à trancher à l'interface).

**Travail pour A.**
1. Serveur, lancement : au lieu du refus, lancer la sélection entière avec un plafond de pages (payées + aperçu restant) ; le travail s'arrête au plafond et le document passe « En pause » avec le motif `limite_apercu` et l'heure de reprise.
2. Moteur : étendre l'arrêt après N pages (aujourd'hui réservé aux scans) aux PDF ordinaires.
3. Reprise : autoriser l'aperçu sur une reprise, en ne comptant que les pages qui restent ; les pages d'aperçu déjà faites ne sont ni recomptées ni facturées.
4. « Mes documents » : motif et heure de reprise sur la carte ; « Reprendre » avant l'heure propose l'achat des pages manquantes.
5. Tests : lancement plafonné, reprise le lendemain en aperçu, reprise après achat, double reprise, pause manuelle inchangée.

Point annexe : une pause manuelle d'un document en aperçu laisse comptées les pages d'aperçu non traduites (le plafond est noté au lancement, `record_libre`). À corriger avec A : rendre au plafond les pages d'aperçu non faites.

**Recommandation : A**, avec la correction annexe. C'est la seule option qui enregistre le travail, montre au client tout ce qui est possible aujourd'hui et se termine sans rien repayer.

## Décision du 22/11 : plus de limite journalière d'aperçu

Pour cette première version, chaque traduction compte : elle fait progresser le moteur et amène des clients. La limite de 20 pages d'aperçu par 24 heures est donc supprimée. Un client peut traduire autant de pages qu'il veut. Les pages non payées restent en aperçu seul, avec le filigrane, et ne se téléchargent pas.

Mise en œuvre : `anti_abus.LIBRE_MAX_PAGES = None` coupe la limite. Le serveur ne renvoie plus `libre_restant`, donc le bandeau « Il vous reste N pages d'aperçu » disparaît, et l'écran de limite ne s'affiche plus. Le mécanisme de pause à la limite reste dans le code, inactif : remettre un nombre suffit à le réactiver. Les pages d'aperçu restent enregistrées (`libre_grants`), ce qui garde le suivi de l'usage.
