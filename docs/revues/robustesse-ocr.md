# Registre : robustesse de la traduction d'images (banc public, 80 cas)

Étape fautive : L = lecture OCR, R = regroupement en blocs, E = effacement, T = traduction, P = pose.
Causes déjà connues (.13h) : A = lignes empilées fusionnées malgré une valeur en face ;
B = texte clair sur bandeau foncé ; C = noms propres / chiffres altérés par la traduction.

## Défauts par cas
| Lot | Cas | Source | Défaut | Étape | Cause |
|---|---|---|---|---|---|
| 0 | 02b06f4ef0, 03a50243ae, 05e7e7e794, 0860789380 | anciens | jugés le 10/11 (.13h) | R/E/T | A, B, C |
| 0 | 05e8ba4031 | ticket | libellés « Subtotal / Total Tax Included / Total » fusionnés en un bloc, texte qui déborde sur les pointillés | R | A |
| 0 | 05e8ba4031 | ticket | colonne des montants fusionnée en un bloc, remontée hors de ses lignes | R/P | A |
| 0 | 05e8ba4031 | ticket | montants réécrits « Rp165000.00 » → « 165000,00 IDR » : à laisser intacts | T | C |
| 0 | 05e8ba4031 | ticket | montants d'origine encore visibles sous la pose (restes 3355) | E | ? |
| 0 | 05e8ba4031 | ticket | texte posé gris clair au lieu de noir (éclairage inégal de la photo) | P | ? couleur |
| 0 | 03a50243ae | formulaire | rejeu A+2bis : titre « CREATIVE INPUT » rendu « CREATIVEINPUT » (espace perdu, non traduit) | L/T | L |
| 0 | 03a50243ae | formulaire | rejeu A+2bis : bandeaux noirs des titres de section (SPECIFICS, OBJECTIVE, TARGET, COMMUNICATION PLATFORM) perdus | E/P | B |
| 0 | 03a50243ae | formulaire | rejeu A+2bis : explication sous « Is there an offer/call to action? » centrée au lieu d’alignée à gauche | P | 2bis ancrage |
| 0 | 03a50243ae | formulaire | rejeu A+2bis : libellés d’une même colonne à des corps très différents (« Nom du client » minuscule) | P | D |
| 0 | 05e8ba4031 | ticket | rejeu A+2bis : montants traduits coupés sur 2 lignes (« 200 / 000,00 IDR ») et chevauchés ; règle : un nombre ne se coupe jamais, on réduit le corps | P | D |
| 0 | 05e8ba4031 | ticket | rejeu A+2bis : police d’origine (chasse fixe) perdue | P | H |
| 1 | 09feddeec6, 0c30278dc3 | factures | titres gras (« Invoice no », « ITEMS », « SUMMARY », en-têtes de colonnes) posés 2 à 3 fois plus petits que l'original, même quand la traduction a la même longueur | P | D taille |
| 1 | 09feddeec6, 0c30278dc3 | factures | titre « Seller: » fusionné avec l'adresse en dessous, lignes d'adresse recoupées autrement, restes pâles | R | A |
| 1 | 09feddeec6, 0c30278dc3 | factures | « Tax Id » + « IBAN » fusionnés et recoupés | R | A |
| 1 | 09feddeec6 | facture | « New Sony » → « NewSony » ; lignes 1 et 7 identiques traduites différemment | T | C |
| 1 | 0fc2332d4b | ticket | articles de rubriques différentes (« Minuman / Teh Tawar », « Lain-lain / Fu Yung Hai ») fusionnés en un bloc qui recouvre « 4.000 » | R/P | A |
| 1 | 0fc2332d4b | ticket | montants « Rp 138.000 » ×3 + « Rp 0 » empilés en un bloc, décalés par rapport aux libellés, réécrits « 138 000 Rp » | R/T | A, C |
| 1 | 0fc2332d4b | ticket | « Cash / Change » fusionnés en « Rendu en espèces » : un libellé perdu | R/T | A |
| 1 | 160dc2107a | AI2D | flèches qui traversent les étiquettes : bavures sombres après effacement | E | G effacement sur traits |
| 1 | 160dc2107a, 05e8ba4031 | AI2D, ticket | texte posé gris clair alors que l'original est noir | P | F couleur |
| 1 | 160dc2107a, tickets | AI2D, tickets | police à empattements / à chasse fixe rendue en linéale | P | H police |
| 1 | 0c30278dc3 | facture | rejeu A+2bis (mieux : Vendeur / Smith / adresse séparés) : « Tax Id … IBAN … » encore fusionnés en un bloc | R | A |
| 1 | 0c30278dc3 | facture | rejeu A+2bis : « Smith Ltd » → « Smith SARL » (nom propre altéré) | T | C |
| 1 | 0fc2332d4b | ticket | rejeu A+2bis (mieux : articles séparés) : colonne des 4 montants encore fusionnée, « Cash / Change » fusionnés en « Rendu en espèces » | R | A |
| 1 | 0fc2332d4b | ticket | rejeu A+2bis : « Minuman / Teh Tawar » → seul « Thé nature » posé sur la ligne du titre, la ligne « Teh Tawar » effacée vide | R/P | A |
| 1 | 0fc2332d4b | ticket | rejeu A+2bis : mot coupé par le ticket « B / esar » traduit en deux morceaux (« portion B » + « grand ») | R | A |
| 2 | 1c8803a384, 1e836b5e65 | AI2D | 0 pose : lettres isolées seulement (C, F, H…) — laissées, conforme (règle 1) | — | — |
| 2 | 1be4ac2a1a | diapositive | « MATERIAL DIGITAL », « Secretaria da Educação » rendus 2× plus petits | P | D taille |
| 2 | 1be4ac2a1a | diapositive | texte du logo « SÃO PAULO GOVERNO DO ESTADO » traduit et déplacé hors de sa zone | T/P | C nom propre, 2bis |
| 2 | 1be4ac2a1a | diapositive | « 1ª » gras → « 1re » maigre | P | H graisse |
| 2 | 2269f16a83 | dessin | « Lower Village » (toponyme) traduit « Basse-Village », posé gris clair | T/P | C, F |
| 2 | 2269f16a83 | dessin | note de source : original encore lisible sous la traduction | E | G restes |
| 2 | 2269f16a83 | dessin | « Département du ___ / Commune de ___ » (déjà en français) fusionnés et recoupés, soulignés effacés | R/T | A, langue cible déjà présente |
| 2 | 1ec6ec9ac4 | FUNSD | titre gras italique à empattements → linéale maigre | P | H police |
| 2 | 1ec6ec9ac4 | FUNSD | libellés (Name, Institution, Address, Telephone…) rendus 2–3× plus petits | P | D taille |
| 2 | 1ec6ec9ac4 | FUNSD | « Please type or print » posé sur le filet noir, illisible | P | B bandeau / 2bis |
| 2 | 1ec6ec9ac4 | FUNSD | « Extra banquet tickets @ $40.00 » non traduit, fantôme de l'effacement | E/T | G |
| 2 | 1ec6ec9ac4 | FUNSD | « Name of guest » remonté sous « Telephone » : décalage vertical | R | A |
| 2 | 1ec6ec9ac4 | FUNSD | rejeu A+2bis (mieux : Institution / Adresse et Téléphone / Nom de l'invité séparés, chacun sur sa ligne) : « Frais d'inscription… » centrés au lieu d'alignés à gauche, plus alignés entre eux | P | 2bis ancrage |
| 2 | 1ec6ec9ac4 | FUNSD | rejeu A+2bis, retour utilisateur : texte noir ordinaire « Please type or print » rendu en lettres blanches cernées de noir (autre style que l'original) ; défaut vu plusieurs fois | P | B / H style |
| 2 | 1ec6ec9ac4 | FUNSD | rejeu A+2bis, retour utilisateur : texte enlevé à un endroit et reposé ailleurs sans raison apparente (« Please type or print » remonté sur le filet) ; défaut vu plusieurs fois | P | 2bis ancrage |
| 3 | 288ca862b0 | tableau | 0 pose sur 61 textes, traductions présentes : corps d'origine < plancher 9 px → `placer()` n'essaie aucune taille | P | **J plancher > corps d'origine** |
| 3 | 34a6fa088e | diapositive | ukrainien (cyrillique) lu en charabia (« Φaún », « 三系 ») : rien traduit | L | **I alphabet non lu** |
| 3 | 235aa55d2c | graphique | « FY '11… » → « EX 11 / EX14 / EX'15 / EX '20 » : même motif rendu de 4 façons | T | C cohérence |
| 3 | 235aa55d2c | graphique | axe X : graisse et gris variables d'une étiquette à l'autre, plus pâles que l'original | P | F, H |
| 3 | 235aa55d2c | graphique | titre d'axe vertical « Software unit sales in millions » non traduit | L/R | **K texte vertical** |
| 3 | 235aa55d2c | graphique | « © Statista 2021 » + « Show source » fusionnés sur une ligne, déplacés, icônes orphelines | R | A |
| 3 | 35a47a2e75 | ticket | « PKT AYAM / GULAI OTAK » fusionnés → « POULET AU / CURRY CERVEAU », lignes décalées | R/T | A |
| 3 | 35a47a2e75 | ticket | « TOTAL / CHARGES » fusionnés et remontés sur la ligne de la taxe, original fantôme dessous | R/E | A, G |
| 3 | 35a47a2e75 | ticket | « 2.00 ITEMS » → « 2,00 » : nombre réécrit | T | C chiffres |
| 3 | 35a47a2e75 | ticket | « SUBTOTAL » gras et plus grand → maigre et plus petit ; chasse fixe → linéale | P | D, H |
| 3 | 35a47a2e75 | ticket | bavures grises à droite de « SOUS-TOTAL » et sous « ARTICLES » | E | G |
| 3 | 35a47a2e75 | ticket | rejeu A+2bis (nettement mieux : articles séparés, TOTAL / CHARGES laissé en place sans fantôme) : libellés centrés au lieu d'alignés à gauche, « SOUS-TOTAL » poussé à droite avec reste pâle à gauche | P/E | 2bis ancrage, G |
| 3 | 35a47a2e75 | ticket | rejeu A+2bis : « PKT AYAM » → « POULE AUX AMANDES » (invention) ; « 2.00 » → « 2,00 » | T | C |
| 4 | 3faab772c6 | DocVQA | rejeu A+2bis (nettement mieux : chaque fonction reste en face de sa personne, plus de gros bloc fusionné ni de chevauchement au milieu) : « Stettler » + « General Counsel » encore sur une ligne ; « Shimomura » + « Otsuka » fusionnés et chevauchés en bas ; « Attendees » fondu dans la ligne de date ; une ligne d'entreprise laissée en original (autre police) | R/P | A, H |
| 4 | 3651adb67f | AI2D | rejeu A+2bis (mieux : plus de « co(nsomimateur » chevauché, les 3 lignes lisibles) : « Tertiaire » séparé de « consommateur » par un trou d'une ligne, bloc centré au lieu d'aligné à gauche | P | 2bis ancrage, D |
| 4 | 3b15b9085e | graphique | rejeu A+2bis (mieux : « Nombre » reste sur sa ligne sous la valeur) : « 98.0 » gardé en original mais rogné en haut (« 98 0 » abîmé) | E | G, C chiffres |
| 3 | 3253abd41a | infographie | marques traduites : « GRUPO GLOBO/FOLHA » → « GROUPE… », « ELLE Decor » → « DÉCORATION », « Le Guardian », « Quem » → « Qui » | T | C noms propres |
| 3 | 3253abd41a | infographie | titre « WHO OWNS THE / WORLD'S NEWS? » traduit ligne à ligne → « QUI POSSÈDE LE / MONDE / ACTUALITÉS? » | R/T | A inverse (phrase coupée en blocs) |
| 3 | 3253abd41a | infographie | « WARNER MEDIA » → « WARNFR MEDIAS » : lecture fausse puis traduite | L/T | L lecture, C |
| 3 | 3253abd41a | infographie | restes 16 651 : nombreux originaux encore visibles sous les poses | E | G |
| 3 | lot 3 | banc | `manque` compte les nombres (jamais envoyés) : indicateur gonflé | banc | outil |
| 4 | 3651adb67f | AI2D | « Tertiary / consumer » et « (secondary / carnivore) » posés l'un sur l'autre → « co(nsomimateur » illisible | R/P | A, 2bis chevauchement |
| 4 | 3651adb67f | AI2D | en-têtes gras « Trophic level » → maigres et plus petits ; « Plant », « Phyto-plankton » gras → maigres | P | D, H |
| 4 | 3651adb67f | AI2D | étiquettes de gauche 15–20 % plus petites que l'original | P | D |
| 4 | 3651adb67f | AI2D | traînées pâles sous plusieurs étiquettes de gauche | E | G |
| 4 | 3651adb67f | AI2D | « Heterotrophs » vertical non traduit | L | K |
| 4 | 39e55a67cf | diapositive | titre gras étroit → maigre, autre police ; puces plus petites, grises, graisse mélangée (« Vous pouvez » gras, suite maigre) | P | D, F, H |
| 4 | 39e55a67cf | diapositive | « • You can » de l'étape 2 laissé en anglais alors que les 7 autres sont traduits | R/T | M traduction partielle |
| 4 | 39e55a67cf | diapositive | fond rouge dégradé et flèches tachés autour des poses ; « pour l'étape 2 » déborde sur la pointe de flèche | E/P | G, 2bis |
| 4 | 39e55a67cf | diapositive | texte blanc de l'étape 4 rendu gris | P | F |
| 4 | 3b15b9085e | graphique | titre à empattements → linéale ; sous-titre gras petit « Total, Number, 2019 » fusionné dans le titre à sa taille | R/P | A, D, H |
| 4 | 3b15b9085e | graphique | infobulle : « 98.0 » → « 98 0 » abîmé, « Nombre » cerné de noir, texte pâle | E/P | C chiffres, G, F |
| 4 | 3b15b9085e | graphique | étiquettes d'axe inclinées à 45° reposées à plat, pâles | P | K texte incliné, F |
| 4 | 3b15b9085e | graphique | « Source : Entrepôt de données » coupé au bord droit | P | 2bis |
| 4 | 3ba2dda38f | procédé | étiquettes plus petites (« gaz neutres », « condenseur ») ; « amine fraîche » gras, original maigre | P | D, H |
| 4 | 3ba2dda38f | procédé | trait noir épais ajouté sur la conduite sous « récupération de chaleur » | E | G |
| 4 | 3ba2dda38f | procédé | « refroidisseur » touche le symbole d'échangeur | P | 2bis |
| 4 | 3ba2dda38f | procédé | « Desorption » vertical non traduit (« Désorption ») | L | K |
| 4 | 3faab772c6 | DocVQA | tableau : fonctions de plusieurs personnes fusionnées en un paragraphe, attribuées aux mauvais noms, posées sur « M. Eiji Itoh » / « M. Toshihiro Okawa » ; noms Shimomura et Otsuka avalés dans le texte | R | **A (grave)**, 2bis |
| 4 | 3faab772c6 | DocVQA | « July 17 and 18, 1996 » + grand titre « Attendees » fusionnés en une ligne : titre perdu, fantôme dessous | R/E | A, D, G |
| 4 | 3faab772c6 | DocVQA | « JT License » → « JTLicense » (espace perdue) ; police à empattements → linéale partout | T/P | C, H |
| 4 | 3faab772c6 | DocVQA | fantômes gris dans la colonne de droite vidée | E | G |
| 5 | 47b08ac7a4 | AI2D | toutes les étiquettes 25–35 % plus petites ; « Lapin », « Souris » en gras alors que l'original est maigre | P | D, H |
| 5 | 47b08ac7a4 | AI2D | flèches abîmées : barres noires épaisses près d'« Épervier », « Moineau », « Crapaud », « Araignée » ; flèche effacée près de « Sauterelle » | E | G (trait du dessin touché) |
| 5 | 47b08ac7a4 | AI2D | soulignement vert ajouté sous « Herbe » | E | G |
| 5 | 47b08ac7a4 | AI2D | « Moineau » plus grand, posé sur la flèche | P | 2bis |
| 5 | 48d53a807a | AI2D | légende : étiquette « Largemouth Bass/Spotted bass » avalée en tête du paragraphe (« Achigan à grande bouche/Achigan tacheté Figure n° 25 ») | R | A |
| 5 | 48d53a807a | AI2D | « Terrestrial Plant Material » + « Terrestrial Insects… » fusionnés sans espace (« terrestreInsectes ») | R | A |
| 5 | 48d53a807a | AI2D | paragraphe de légende coupé en bas (finit sur « (tortues ») ; « Essai II » coupé au bord droit | P | 2bis débordement |
| 5 | 48d53a807a | AI2D | légende et en-tête à empattements gras → linéale maigre ; étiquettes plus petites ; césures ajoutées (« GASTÉ-ROPODES », « pois-sons-chats ») | P | D, H |
| 5 | 497edb0685 | infographie | titre blanc à empattements → linéale blanche cernée de noir | P | H, B |
| 5 | 497edb0685 | infographie | « Here's what you need to know right now. » + intertitre « Common symptoms of coronavirus » fusionnés : intertitre perdu, trace dessous | R/E | A, G |
| 5 | 497edb0685 | infographie | colonne de droite : 3 conseils fusionnés en un bloc, icône « Stay home » sans texte | R | A |
| 5 | 497edb0685 | infographie | intertitres, titres de rubrique, symptômes et pied de page plus petits ; corps gris ; pied blanc gras → maigre | P | D, F, H |
| 5 | 497edb0685 | infographie | pied : « 24/7 HEALTH LINE / 704-468-8888 » → « LIGNE SANTÉ / 24/7 704-468-8888 » : ordre et lignes changés, numéro rapetissé | R/T | A, C |
| 5 | 497edb0685 | infographie | « Essoufflement » descendu sous la ligne des autres symptômes | P | 2bis ancrage |
| 5 | 4e98b4491e | tableau | colonne « Group » : les 20 valeurs fusionnées en une pile « Témoin OE » décalée des lignes, grise | R | A, F |
| 5 | 4e98b4491e | tableau | en-tête « Group » → « Gro / upe » coupé en deux | P | D |
| 5 | 4e98b4491e | tableau | colonne « Parameter » non traduite (corps < plancher) | P | J |
| 5 | 48d53a807a | AI2D | rejeu A+2bis (mieux : « Achigan à grande bouche/Achigan tacheté » posé à sa place sous le poisson, plus avalé dans la légende) : légende toujours coupée en bas | P | 2bis débordement |
| 5 | 497edb0685 | infographie | rejeu A+2bis (nettement mieux : titres de rubrique séparés de leur texte ; chaque conseil de droite en face de son icône, « Stay home » retrouve son texte) : titres de rubrique très petits et maigres (« Restez chez vous » vs « Stay home » gros) | P | D, H |
| 5 | 497edb0685 | infographie | rejeu A+2bis : pied « 24/7 HEALTH LINE » laissé en anglais (avant : traduit, mais lignes inversées) | L | M |
| 5 | 4e98b4491e | tableau | rejeu A+2bis (mieux : plus de pile en haut, un « Témoin OE » par paire de lignes) : « OE » et le « Control » suivant encore fusionnés en « Témoin OE » sur une seule ligne alors que chacun a sa valeur en face ; ligne « Control » vide ; paire Glucose effacée sans texte | R | A |
| 5 | 53c98ed07b | maquette | déjà en français : aucune pose | — | conforme |
| 6 | 570746c016 | diapositive | interface en ukrainien : rien traduit (cyrillique non lu comme source) | L | I |
| 6 | 570746c016 | diapositive | seule pose : « Спеціальні символи… » remplacé par « Ω. » (texte perdu, icône lue) | L/T | L, M |
| 6 | 5721fa962e | schéma | lettres seules, rien à traduire | — | conforme |
| 6 | 5a61fa9ff0 | facture | « Invoice no: » et « Date of issue: » : corps réduit de ~40 %, titre déplacé vers la droite | P | D, 2bis |
| 6 | 5a61fa9ff0 | facture | « Seller: » fusionné avec les 3 lignes d'adresse ; « Tax Id » + « IBAN » refondus en 2 lignes autrement coupées ; fantômes de l'adresse | R/E | A, G |
| 6 | 5a61fa9ff0 | facture | intertitres « ITEMS », « SUMMARY » : corps ÷2 ; en-têtes « Qty », « Net price », « TVA » perdent la graisse ou la taille | P | D, H |
| 6 | 5a61fa9ff0 | facture | police DejaVu Sans → Roboto ; descriptions des articles plus petites, interligne serré | P | H, D |
| 6 | 5a61fa9ff0 | facture | « each » → « l'unité » remonté au-dessus de la ligne de base | P | 2bis |
| 6 | 5a61fa9ff0 | facture | « new 3DS » → « new3DS » (espace perdu) ; guillemets " " → « » | T | C |
| 6 | 5c83bbf7a5 | graphique | titre serif (Playfair) → sans ; étiquettes 1 ligne → 2 lignes ; 2 étiquettes perdent le gras | P | H, A |
| 6 | 5c83bbf7a5 | graphique | trait blanc ajouté au début de la barre rose | E | G |
| 6 | 5c83bbf7a5 | graphique | « Source : … » corps réduit, gris plus pâle | P | D, F |
| 6 | 5d645bdd94 | tableau | tableau entier non traduit (corps ~7 px < plancher 9 px) | P | J |
| 6 | 5a61fa9ff0 | facture | rejeu A+2bis (mieux côté vendeur : « Vendeur: » séparé de l'adresse) : adresse client, laissée telle quelle avant, désormais reposée : 3 lignes refondues en 2 (« Stewart, Fields et Scott 07095 Robert / Cape Marquezburgh »), corps réduit, « and » → « et » dans un nom de société ; « Apt. / 233 » recoupé côté vendeur ; « Tax Id + IBAN » toujours fusionnés | R/T/P | A, C, D |
| 7 | 5e636ab7d0 | tableau | tableau entier non traduit (corps ~8 px < plancher 9 px) | P | J |
| 7 | 64d91ab945 | dessin technique | étiquette géométrique « d' » traduite en « de » (notation, à laisser) | T | C, 1 |
| 7 | 64d91ab945 | dessin technique | trait épais sous « d' » raccourci par l'effacement | E | G |
| 7 | 6739490c68 | lettre scannée | en-têtes d'adresse (3–4 lignes) fusionnés en 2 lignes, corps réduit | R/P | A, D |
| 7 | 6739490c68 | lettre scannée | « Our Code… / Page 1 of 1 » et bloc « TO: » : lignes recoupées, police machine à écrire → sans, corps agrandi | R/P | A, H |
| 7 | 6739490c68 | lettre scannée | FROM/DATE/TEST/SPECIMEN/RECEIVED : libellés réduits, 5 valeurs fusionnées en un paragraphe, « 4 janvier 1989 » superposé | R/P | A, D, 2bis |
| 7 | 6739490c68 | lettre scannée | « Send » (virus Sendai) → « Envoyer » ; en-têtes « PVM RCV/SDA M.Pul » fusionnés et posés dans les cellules | T/R | C, A, 2bis |
| 7 | 6739490c68 | lettre scannée | « Hemagglutination Inhibition » déplacé ; « Positive Titer », note de bas : police changée, corps agrandi | P | 2bis, H |
| 7 | 6a831b29a2 | schéma de procédé | ~35 étiquettes effacées sans texte visible posé (Separator, Coke Drum, Feed, Pump, Note…) | P | N |
| 7 | 6a831b29a2 | schéma de procédé | « Pompe », « Huile légère… » : gras cerné au lieu du normal ; note rouge disparue | P | B, H, N |
| 7 | 70ced041f4 | formulaire | « From/To/CC » fusionnés sur une ligne ; libellés à puces décalés d'une ligne (Media Type + Name, Issue Date + Space/Color, Circulation + Area) | R | A, 2bis |
| 7 | 70ced041f4 | formulaire | valeurs « Tiers II & IV… » noircies en pâté illisible | P/E | B, G |
| 7 | 70ced041f4 | formulaire | valeurs et « FOR CONTROL USE ONLY » grisées ; Times → sans ; « $1.50 OFF » sur 2 lignes réduites | P | F, H, D |
| 7 | 70ced041f4 | formulaire | « Code Assigned / Job Number / Est. Redemption » fusionnés ; « * » → « • » | R/T | A, C |
| 7 | 6739490c68 | lettre scannée | rejeu A+2bis (nettement mieux : FROM/DATE/TEST/SPECIMEN/RECEIVED chacun en face de sa valeur ; en-têtes « PVM RCV/SDA M.Pul » à leur place ; adresse d'en-tête gauche en 4 lignes) : bloc « TO: » : « Company Division de toxicologie » chevauche « Bowman Gray Technical Center » ; « NC » → « Caroline du Nord » ; « 4 janvier 1989 » et « 10 sérums de rat » en tout petit corps à côté des autres valeurs | R/P/T | A, C, D |
| 7 | 6a831b29a2 | schéma de procédé | rejeu A+2bis (mitigé) : mieux « Gas » / « Reflux Drum » séparés (« Gaz », « Ballon de reflux ») ; moins bien « Sour Water » → « Acide » / « Eau » coupé en deux et inversé (avant : « Eau acide »), « To Coke Storage » → « Vers le coke / Stockage » coupé en deux traductions | T/P | A |
| 7 | 70ced041f4 | formulaire | rejeu A+2bis (mieux : « De / À / Copie à » séparés, chacun sur sa ligne) ; reste du formulaire inchangé | — | — |
| 8 | 723df50948 | schéma | Arial normal → police plus grasse et condensée ; « Plantes » plus grand que l'original | P | H, D |
| 8 | 743159ee6f | organigramme | noms vietnamiens altérés : « Dạng » → « Dang », « Thơ » → « Tho » | T | C |
| 8 | 743159ee6f | organigramme | texte gris pâle, corps réduit, recentré au lieu d'aligné à gauche ; interligne de la dernière boîte serré ; fantômes | P/E | F, D, 2bis, A, G |
| 8 | 77d62395c7 | note scannée | lignes de l'itinéraire refondues en paragraphes, colonnes des heures perdues ; « 13 février 1977 » posé deux fois | R | A, 2bis |
| 8 | 77d62395c7 | note scannée | annotation manuscrite « Cancelled reservations 10-18-76 » remplacée par un texte imprimé gris « annulé le 18-10-76 » (« reservations » perdu) ; initiales manuscrites à moitié effacées | T/P/E | M, H, G |
| 8 | 77d62395c7 | note scannée | machine à écrire → sans ; « 1:00 p.m. » → « 13 h 00 » (format changé) | P/T | H, C |
| 8 | 7d083235e3 | dessin technique | légende 2 lignes → 1 ligne plus large ; Calibri → Roboto | P | A, H |
| 8 | 848b7f8cfc | formulaire juridique | libellés alignés à gauche → alignés à droite et décalés ; Times gras → sans ; corps réduit | P | 2bis, H, D |
| 8 | 848b7f8cfc | formulaire juridique | « Case name » + « Court » fusionnés ; « Lorillard counsel / Judge / Trial date » fusionnés ; avocat 5 lignes → 2 ; fantômes | R/E | A, G |
| 8 | 77d62395c7 | note scannée | rejeu A+2bis (mitigé) : mieux « Vol Continental n° 601 » et « Vol Aloha Airlines n° 383 » chacun sur sa ligne, manuscrit « 10-18-76 » laissé tel quel (avant : remplacé par « annulé le 18-10-76 ») ; moins bien « Continental#925 (DC / 10) » coupé au milieu de « DC 10 », « 13h00 » écrit autrement que les autres heures (« 14 h 06 »), « Denver 13h00 » toujours collé à la ligne d'au-dessus ; manuscrit à moitié traduit (« Annulé » posé, « reservations » gardé en manuscrit) | R/T | A, D |
| 8 | 848b7f8cfc | formulaire juridique | rejeu A+2bis (mieux : valeur de « TRIBUNAL » en face de son libellé ; « JUGE » et « DATE DU PROCÈS » séparés) : « PLAINTIFF'S COUNSEL » → « AVOCATS DU DEMANDEUR: » + « CONSEIL: » (doublon) ; « LORILLARD » gardé en anglais au-dessus de « ENTITÉS », et rogné (« I ORII LARD ») au-dessus de « CONSEIL » ; « 415/986-5566 » coupé à mi-hauteur ; adresse 5 lignes → 3 | R/T/P | A, D, G |
| 9 | 88e7858141 | graphique | titre d'axe vertical « Unemployment rate » non traduit | L/P | K |
| 9 | 88e7858141 | graphique | « © Statista 2021 » + « Show source » fusionnés sur une ligne grise ; icône drapeau et ⓘ abîmées, reste « › » | R/E | A, F, G |
| 9 | 92a3fdb822 | facture scannée | « EFFECTIVE DATE » mal effacé : « -DATE D'EFFET » posé sur le reste « TIVE », bloc noirci | E/P | G, B, 2bis |
| 9 | 92a3fdb822 | facture scannée | « Contl. CAs. » fusionné avec le libellé ; machine à écrire → sans plus grand ; déborde sur la colonne PRIME | R/P | A, H, D, 2bis |
| 9 | 92a3fdb822 | facture scannée | « THORNTON AGENCY, INC. » + « Insurance » (script) fusionnés en sans, chevauche l'adresse ; « Assured's code » fusionné avec 004295 | R/P | A, H, 2bis |
| 9 | 92a3fdb822 | facture scannée | en-têtes, « Premiums are due… », « PLEASE RETURN… », « TELEPHONE » : gras → sans gris plus petit ; reste d'effacement sous « VEUILLEZ RETOURNER » | P/E | D, F, H, G |
| 9 | 92a3fdb822 | facture scannée | « $52.00CR. » → « 52,00 $CR. » (format changé) | T | C |
| 9 | 93031852e3 | infographie | une trentaine de petits libellés (légende, tableau, armes, sources) non traduits | P | J, M |
| 9 | 93031852e3 | infographie | « 76% » rogné et fantôme sous « VICTIMES CIVILES » ; « LAUNCHED » visible sous « DEPUIS LE SOL » ; « LANCÉS DEPUIS LES AIRS » 2 → 3 lignes grises | E/P | G, 2bis, A, F |
| 9 | 94062d9e89 | facture | titre gras réduit et recentré ; « Seller: » fusionné avec l'adresse, gras perdu ; Tax Id + IBAN fusionnés ; fantômes | R/P/E | D, 2bis, A, H, G |
| 9 | 94062d9e89 | facture | DejaVu → Roboto condensé ; titres ITEMS/SUMMARY réduits ; description 3 → 4 lignes ; « each » remonté | P | H, D, A, 2bis |
| 9 | 9661509ea5 | schéma scanné | « Fish » → « Pois-son » coupé sur 2 lignes ; libellés plus petits et plus maigres | P | A, D, H |
| 9 | 9661509ea5 | schéma scanné | traînées près de « Raton laveur » et de la flèche de « Vairons » ; tache verte au bord ; pavés blancs sur le fond imprimé | E | G |
| 9 | 92a3fdb822 | facture d'assurance | rejeu A+2bis (mitigé) : mieux « Contl. CAs. » gardé seul à sa place, description de couverture séparée ; moins bien : description recentrée au lieu d'alignée à gauche ; bloc destinataire « Citizens' Commission on Science, Law and The Food Supply » (nom d'organisme, laissé avant) désormais traduit, et mal (« sur le droit scientifique »), chevauché par « INC. Assurance » | P/T/R | 2bis ancrage, C |
| 9 | 94062d9e89 | facture | rejeu A+2bis (mieux : « Vendeur: » séparé, adresse vendeur laissée intacte comme côté client) ; « Tax Id + IBAN » toujours fusionnés, libellés de titre toujours réduits | R/P | A, D |
| 10 | 9a53216c72 | graphique | titre à empattements → sans ; sous-titre plus petit, gris, centré au lieu d'aligné à gauche | P | H, D, F, 2bis |
| 10 | 9a53216c72 | graphique | logo « Our World in Data » (blanc sur bleu foncé) : fond effacé, texte sombre sur blanc, traits parasites | E/P | B, G |
| 10 | 9a53216c72 | graphique | pays, valeurs et graduations nettement plus petits et gris ; « 0 liters » fusionné avec « Source: World Bank » ; « • » perdu dans l'URL | R/P/T | D, F, A, 2bis, C |
| 10 | a0ef2a3bb6 | capture de diapositive | tout le texte ukrainien laissé non traduit (0 pose) | L/T | I |
| 10 | a21d576c4b | schéma | lettres isolées laissées telles quelles : conforme | — | — |
| 10 | a2a35fc4f6 | formulaire scanné | « TO: » + « FROM: » fusionnés en « À: DE: », « FROM » disparu ; REGION fusionné avec la consigne ; « DIVISION » perdu ; noms de division déplacés, en gras, colonne # REPS mélangée | R/P | A, 2bis |
| 10 | a2a35fc4f6 | formulaire scanné | Times → sans, plus petit, gris ; soulignés et gras perdus | P | H, D, F |
| 10 | a2a35fc4f6 | formulaire scanné | « OCT 05 » → « 05 OCT » (format changé) | T | C |
| 10 | a2a35fc4f6 | formulaire scanné | en-têtes de tableau sur fond tramé : « Nombre de magasins » posé sur « Stores » restant, contouré ; fantômes | E/P | G, B, 2bis |
| 10 | a2a35fc4f6 | formulaire scanné | rejeu A+2bis (mieux, accepté 13/11) : « À: » et « DE: » séparés, chacun sur sa ligne ; « RÉGION: » séparé de la note « (uniquement si région partielle…) » ; « DIVISION: » réapparu ; « PARTIEL » et « # REPS: » séparés et alignés ; « Detroit West / South » gardés (avant : « Ouest / Sud ») ; reste : « Nombre de magasins » sur « Stores » (blanc cerné), « Ind/Lor Volume » traduit à moitié | P/T | B, M |
| 10 | a2d08b84ef | schéma | « Virtual Machines (VMs) » gras → normal, lignes écartées ; « Real Machine » → « Réelle » + « machine » à moitié effacé | R/E/P | H, A, G, M |
| 10 | a2d08b84ef | schéma | « Tape Drive » non traduit ; « Disk Drive », « Printer » en gris, posés sur le dessin | P | M, F, 2bis |
| 10 | a2d08b84ef | schéma | cadres de « TOP SECRET » et « UNCLASSIFIED » effacés, traînées | E | G |
| 11 | ab7cc197ea | dessin technique | titre condensé → sans, plus petit ; « Main Gear Connnect » éclaté en petit texte ; 2e « Nose Wheel Steering » à moitié effacé (traînée) ; cartouche « Zeke Air Mission… » réduit à un texte minuscule ; traits verts sur les bords de cadre et sous la légende ; pochoir © → sans ; NAVIGATION LIGHT SYSTEM déplacé | pose / effacement | D, H, G, 2bis |
| 11 | ae884036cd | graphique | « Tax revenue » (serif) perdu, fusionné avec le sous-titre ; source petite et grise ; étiquettes inclinées remises à l'horizontale, pâles | regroupement / pose | A, H, D, F, K |
| 11 | b2b5fa130a | graphique Statista | légende « Female / Male » fusionnée en « FemmesHommes », grosse, grasse, 2e pastille perdue ; titre d'axe vertical non traduit ; « Show source » fusionné avec © ; drapeau effacé | regroupement / pose | A, D, H, F, K, G |
| 11 | b30ca80cb7 | schéma (îles volcaniques) | italique perdu partout ; titre 2 éclaté sur 2 lignes ; étiquettes sur fond brun : noir détouré illisible ; « cinder cone / ash cone » fusionnés ; petites étiquettes grises ; « reef » (8) non traduit | pose / regroupement | H, A, B, D, F, J |
| 11 | b30ca80cb7 | schéma (îles volcaniques) | rejeu A+2bis (un peu mieux) : case 7 « cône de scories » et « cône de cendres » séparés, chacun à sa place | — | — |
| 11 | b3374ed8d5 | scan (tableau) | Times → sans, gras et soulignés perdus ; Regional Brands : 3 lignes en 2, alignement perdu ; tableau : colonnes mélangées (« Produits actuels Sulfate de zinc », « Cuivre Calcium »), ligne Calcium décalée ; « $115 MM » → « 115 M$ », « $11.5 MM » → « 11,5 M$ » ; « Ingredient » → « ingrédient. » | regroupement / pose / traduction | A, 2bis, H, C |
| 11 | b3374ed8d5 | scan (tableau) | rejeu A+2bis (**recul**) : liste de marques empilée (1 par ligne, rien en face) fusionnée en 4 lignes ; « General Nutrition Center » (marque) traduit en « Centre de nutrition générale » ; avant : liste intacte. Règle à ajouter : lignes courtes empilées, même marge gauche, même interligne = liste, pas de fusion | R/T | A, C |
| 12 | b5df0ac3c2 | scan dactylographié (budget) | machine à écrire → sans, gris ; en-tête de 4 lignes en 2 ; colonne des comptes décalée (« Salaires Frais / de bureau », Educational sans valeur en face, Travel + Miscellaneous fusionnés, « Total Frais juridiques », « Total TOTAL GÉNÉRAL ») ; Legal Expenses et Mr. Brobeck perdus, taches blanches ; soulignés perdus | regroupement / effacement / pose | A, 2bis, G, H, F, D |
| 12 | b5df0ac3c2 | état de dépenses | rejeu A+2bis (nettement mieux) : chaque libellé en face de son montant (avant : tassés en haut, « Total », « Frais juridiques » décalés) ; « TOTAL GÉNÉRAL » sur une ligne ; reste : sous-titre 2 lignes → 4 | R | D |
| 12 | b780d0b4e8 | infographie | titre serif → sans ; chapeau très pâle et minuscule ; ~700 caractères (textes courants) non traduits ; « Taiwan », « JAPON » noir détouré sur rouge ; « Canton » effacé en traînée rouge ; « Allied air attack routes » → « alliées » détouré, restes de l'original ; « HONG KONG ISLAND » → « ÎLE » seul ; « Sep 2, 1945 » déborde | pose / effacement / traduction | H, F, D, J, M, B, G, 2bis |
| 12 | b780d0b4e8 | infographie | rejeu A+2bis : différence non visible à l'échelle de la planche | — | — |
| 12 | bec7d225fc | dessin technique (allemand) | **repère « 4 » avalé par le titre** (« vue 4 ») et effacé du dessin ; titre noir → regular sur 2 lignes ; légende serif condensé → sans, gras irrégulier (1 et 5 seulement), alignement à gauche → escalier centré | regroupement / pose | A, C, H, 2bis, G |
| 12 | bec7d225fc | dessin technique | rejeu A+2bis (mieux) : titre sur une ligne, repère « 4 » plus avalé (avant : « …vue 4 ») | — | — |
| 12 | c0ed3caf66 | tableau d'article | « Année » coupé « An / née », « Type de VPH » sur 2 lignes ; en-têtes gras perdus, gris ; cellules (« Review », « Benign lesions »…) non traduites | pose / traduction | A, D, H, F, M, J |
| 12 | c8dd676f0f | graphique Pew | titre plus petit, 2e ligne décalée ; sous-titre serif italique → sans droit gris ; « Blancs » remonté ; « PEW RESEARCH CENTER » (nom propre) traduit en « CENTRE DE RECHERCHE PEW », plus fin | pose / traduction | D, 2bis, H, F, C |
| 12 | c8dd676f0f | graphique Pew | rejeu A+2bis (mieux) : « Blancs » en face de sa barre ; « Source » séparée de la note | — | — |
| 13 | ca0f5dc9d3 | facture | DejaVu → Roboto ; « Invoice no » nettement plus petit et décalé à droite ; Seller fusionné avec le nom de société (« Vendeur: Gregory, / Patterson and Fischer »), fantôme de la ligne effacée ; Tax Id + IBAN fusionnés, petits ; ITEMS, SUMMARY, en-têtes plus petits ; « l'unité » remonté ; traces d'effacement près des en-têtes | regroupement / pose / effacement | A, D, H, G, 2bis |
| 13 | ca0f5dc9d3 | facture | rejeu A+2bis (mieux, un défaut nouveau) : « Vendeur: » séparé du nom de société ; mais « Patterson and Fischer » → « Patterson et Fischer » (nom propre altéré) ; Tax Id + IBAN toujours fusionnés | T | C |
| 13 | cbac6dd50a | bordereau de dépôt scanné | nom et adresse de 3 lignes en 2, coupure fausse ; petites capitales serif → sans gris ; date posée sur la 1re ligne du texte légal, « 19 » avalé ; texte légal : 1re ligne en gras minuscule, le reste superposé à l'original mal effacé ; « CHECK » gras perdu ; « CREDIT » pochoir → sans gris ; ligne Source réécrite en gras avec fantôme | regroupement / effacement / pose | A, G, 2bis, H, F, D |
| 13 | cbac6dd50a | bordereau de dépôt scanné | rejeu A+2bis (mieux) : nom + « ROUTE 2, BOX 165 » sur une ligne, ville séparée, « 19 » rendu ; texte légal moins superposé mais minuscule ; « BOX » → « BOÎTE » dans l'adresse | P/T | D, C |
| 13 | ce5775bacc | organigramme (italien) | 2 textes traduits sur ~20 : titre, légende, « Divisione o brigata » restés en italien ; « Guardia Imperiale » manuscrit italique → sans | traduction / pose | M, H, F |
| 13 | d0cf437064 | schéma (lettres seules) | conforme : rien à traduire | — | — |
| 13 | d191c294df | organigramme (déjà en français) | conforme : rien à traduire | — | — |
| 14 | d24b1c2f0a | bordereau de fax scanné | valeurs Arial gras → maigres et plus petites ; libellé et valeur fusionnés sur une ligne (« À Robert H. Shaw », « Date 11 novembre 1997 », « Société Lorillard… », « Référence 17560-188 ») ; « Fax Transmittal » fusionné avec l'adresse, « New York, NY 10017 » effacé avec fantôme « 10017 » ; traînées d'effacement sous les valeurs ; en-tête capitales espacées serif → Roboto gras ; horodatage fax en autre police, point noir rogné ; note de confidentialité et « Message: » non traduits | regroupement / pose / effacement / traduction | A, 2bis, H, D, G, J, M |
| 14 | d52c29504e | ticket de caisse (photo) | police matricielle → Roboto ; gris plus clair ; lignes d'articles légèrement remontées ; « Total. » non traduit | pose | H, F, 2bis, M |
| 14 | db7a99f901 | schéma (lettres seules) | conforme : rien à traduire | — | — |
| 14 | e526aee7e7 | ticket de caisse (indonésien) | 2 articles fusionnés en un bloc qui chevauche les prix ; quantité « 1 » avalée dans le texte et effacée ; « ITEMS:8 » + « Pb1 10% » fusionnés, « Pb1 » mal lu (« En1 ») ; « Rounding / Total / DEBIT BCA » fusionnés et décalés d'une ligne par rapport aux montants ; « NASI ORG » → « RIZ RG » avec traînée ; « Before Rounding » → « e Arrondi » | regroupement / lecture / effacement | A, 2bis, C, G, L, M |
| 14 | ed2a686911 | schéma de procédé | toutes les étiquettes nettement plus petites (≈ moitié) et plus pâles ; texte sur aplats colorés plus clair ; « Neutraliser/Cooler » non traduit | pose / traduction | D, F, M |
| 15 | f4554a2eba | rapport annuel scanné (3 colonnes justifiées) | Gill Sans justifié → Roboto plus petit non justifié ; titre « DIRECTORS' RESPONSIBILITY STATEMENT » fusionné dans le paragraphe précédent, bandeau grisé déplacé ; liste 1-4 fusionnée en un bloc, numéros 2 et 3 superposés au texte, « 4. » isolé ; « Income Tax » et « Entry Tax » fusionnés dans les paragraphes ; grands vides blancs ; pied « Annual Report » italique perdu | regroupement / pose | A, 2bis, D, H, B, G |
| 15 | f4554a2eba | rapport annuel scanné (3 colonnes justifiées) | rejeu A+2bis (beaucoup mieux) : titres RESPONSABILITÉ / DÉCLARATION / FISCALITÉ séparés, liste 1-4 avec chaque numéro devant son point, « Income Tax » et « iii. Taxe à l'entrée » rendus à leur place ; reste « ii. Taxe de luxe » nettement plus grand que l'original, texte de liste petit | P | D |
| 15 | f5c95c9767 | schéma de procédé (fond noir) | « 450 °C » → « 450▯ » : symbole degré perdu (glyphe manquant) ; « catalyst », « ammonia » gras → maigre ; « épurateur » déborde de la cuve ; textes plus pâles ; « (liquide) » plus petit | pose / police | C, H, F, 2bis, D |
| 15 | f6ae2f2472 | infographie | titres Arial Black → Roboto gras ; légendes ≈ moitié plus petites ; « $100k » → « 100 k$ » ; « 45% », « 41% » gras perdu ; « CLOSED » pochoir → « FERMÉ » maigre avec traînée ; rectangles blancs d'effacement visibles sur la carte et le fond ; noms propres traduits (« NORTHERN » → « DU NORD », « Thunder Bay Chamber of Commerce » → « Chambre de commerce… ») et bleu → gris | effacement / pose / traduction | H, D, C, G, F, B, 2bis |
| 15 | fd411dc59f | frise chronologique (slovène) | légendes de colonnes voisines fusionnées en un paragraphe qui chevauche (1991 + ????) ; légendes en gras alors que l'original est maigre ; 1958 éclatée sur deux lignes séparées ; 1986 réduite à « partisane » ; « Ni nobene fotografije » → plus petit, pâle, césure « pho-tographie » ; titre recalé | regroupement / pose / traduction | A, 2bis, H, D, F, M |
| 15 | fd411dc59f | frise chronologique (slovène) | rejeu A+2bis (mieux) : chaque année avec sa légende dessous, plus de chevauchement entre colonnes ; reste légendes éclatées en morceaux espacés (1958, 1991) | R | A, D |
| 15 | fdc8e1f41c | graphique Statista | « Dallas Mavericks », « Portland Trailblazers » réécrits en petit gras serré (« Trail Blazers » : nom altéré) alors qu'ils sont à garder ; titre d'axe fusionné avec la graduation « 20 » → « 20 millions d'abonnés Twitter », posé sur les graduations ; bouton et liens plus petits ou maigres ; icône « Show source » rognée | regroupement / traduction / pose / effacement | A, 2bis, C, H, D, G |
| 15 | fdc8e1f41c | graphique Statista | rejeu A+2bis (beaucoup mieux) : titre d'axe séparé des graduations (« 15 »/« 20 » rendus, plus de « 15 millions » inventé), posé à sa place ; reste Dallas/Portland en petit gras, « Trail Blazers » altéré | P/T | C, H |

## Causes par fréquence (lots 0 à 15)
Un cas compte une fois par cause. Détail, étape fautive et ordre de correction :
`docs/etude-robustesse-ocr.md`, section Résultats.

| Cause | Cas |
|---|---|
| H police, graisse, italique | 47 |
| A lignes ou colonnes fusionnées | 43 |
| D texte trop petit | 41 |
| G restes d'effacement | 39 |
| 2bis chevauchement, ancrage | 38 |
| F couleur pâle | 29 |
| C noms, chiffres, symboles altérés | 27 |
| M traduction partielle | 13 |
| B bandeau perdu | 11 |
| J plancher 9 px | 9 |
| K vertical, incliné | 7 |
| I alphabet non lu | 3 |
| L mauvaise lecture | 3 |
| N effacé sans pose | 1 |

## Corrections
| Cause | Origine réelle | Correctif | Test |
|---|---|---|---|
| N (et part de F) | texte posé en blanc (255,255,255) sur fond blanc : le masque de mesure est dilaté, sur un corps de ~9 px la plupart de ses pixels sont du fond, le 70e centile de distance tombe à 0 et `_couleur()` rend la couleur du fond | `_couleur()` ne garde que les pixels à ≥ 80 % de la distance maximale au fond (cœur de l'encre) | `cas_couleur_petit_corps` (noir et rouge, 9 px) ; 6a831b29a2 : 62 poses, toutes en noir |
| A + 2bis | `blocs()` fusionnait les lignes empilées d'une même marge : libellé « X: » et sa valeur, rangées de tableau, champs d'adresse, en-têtes ; texte aligné à gauche posé centré | `blocs()` : libellé, valeur et nombre seuls restent à part ; rangées ayant chacune leur nombre ; test de retour à la ligne (`RETOUR`) ; interligne `dessous` ; ligne lue entre deux. Recul b3374ed8d5 (liste de marques fusionnée) corrigé par `_liste()` : ≥ 3 lignes latines courtes (≤ 4 mots) commençant par une majuscule, sans vis-à-vis, même marge, même corps, pas régulier = liste, aucune fusion | `cas_blocs` (fiche, tableau, en-tête, liste de marques, paragraphe étroit en minuscules) ; rejeu public 16 lots, interne 0–3 identique ; `_liste()` ne touche que b3374ed8d5 et 6739490c68 (adresse, ligne par ligne) |
| R1 + R2 | Texte aligné à gauche posé centré quand chaque ligne est un bloc à part (en-têtes, listes, légendes) ; liste en capitales découpée à tort | R1 : `_liste()` exige des minuscules. R2 : `_axes()` donne un même alignement aux blocs empilés d'une colonne (écart vertical ≤ `GROUPE_ECART`, corps dans un rapport ≤ `GROUPE_CORPS`, pas de trait entre eux) ; l'alignement cède s'il rapetisse le bloc ou le coupe sur plus de lignes | `cas_axes`, `capitales` ; rejeu public 16 lots : mieux 9661, 03a5, 1ec6, 3faa, bec7, 35a4 ; reculs fd41, b3374, 5c83, 35a4 vus puis corrigés ; interne 0–3 identique avec/sans `_axes`. Ouverts : libellés empilés à aligner à droite (5c83) ou à gauche (848b) |
| T3 + `_proteger` | Rangée de tableau fusionnée (libellé et valeur numérique en face) ; l'effacement d'une ligne traduite entamait l'encre d'une ligne gardée qui la chevauche, et le remplissage reprenait sa couleur (voile gris) | T3 : `_en_face`, ligne avec valeur numérique en face sur ≥ 3 rangées de même bord gauche = `rangee`. `_proteger` : encre des deux lignes répartie tache par tache vers le milieu le plus proche, part gardée retirée du masque (traits de tableau exclus, `MARGE_TRAITS`) ; `effacer(gardee=)` + `_fond_sous()` : l'encre gardée prend le fond clair voisin avant remplissage (jamais assombrie) | `cas_blocs` (Zinc/Manganese/Copper/Calcium + contre-cas) ; rejeu public : 26 cas changent, tous en gain (3253, 4e98, 77d6, 6739, d24b, b780, 848b, 47b0, 3b15, 5d64…) ; interne 0–3 identique ; ouvert : tache fsr entre deux traits (a2a3, niveau 2) |
| T1/T2 | Une ligne lue d'un seul tenant traverse deux colonnes (« ManganeseManganese Gluconate », « CCM Plus Trace Minerais Current Products ») | `couper_colonnes` (avant `_symboles`) : bords de colonne = bord gauche partagé par ≥ `GRILLE` lignes ; une ligne qui part d'un bord et franchit un autre bord confirmé (même corps, dans la grille) est coupée dans un blanc d'image ≥ `BLANC_CASE`×h près du bord, au découpage de texte le plus proche (espace ou minuscule→Majuscule) | test `cas_blocs` (grille synthétique + contre-cas encre continue / sans image) ; 98 cas : 4 changent, tous en gain (3faab, b3374, c0ed, fd411) ; interne identique ; ouvert : « nadomesti \| vandalizirana » (fd411, blanc trop étroit), en-tête « CCM Plus Trace Minerais » fusionné avec « Zinc Sulfate » (T4) |
| T4 | L'en-tête d'une colonne de tableau se fondait dans la 1re case en dessous (« CCM Plus Trace Minerais Zinc Sulfate ») | `blocs()` : ensemble `entete` = ligne hors `rangee` posée sur une rangée d'au moins `GRILLE` cases ; elle ne fusionne pas avec une rangée en dessous si la colonne compte au moins `GRILLE` rangées au même bord gauche (une seule rangée : en-tête sur deux lignes « DATE OF / INVOICE », 92a3, reste lié) | `cas_blocs` (en-tête + 3 rangées, contre-cas une rangée et sans rangée d'en-tête) ; 98 cas : seul b3374 change (gain) ; interne identique ; ouvert (b3374) : « Raw Material Costs: Ingredient. » libellé et en-tête lus d'un tenant avec un point ajouté, « CostIndex » collé (lecture), rangées non alignées à gauche (G1) |
| F1/F2 | Fiche : libellé sur deux lignes traduit en deux morceaux (« PLAINTIFF'S » / « COUNSEL: », contresens) ; adresse en face refondue de 5 en 2 lignes | `blocs()` : `haut` (ligne courte sans « : » ni rien en face, même bord gauche, interligne serré, au-dessus d'un libellé → un seul bloc) ; `champ` (valeur d'un libellé et lignes empilées dessous au même bord gauche : chaque ligne garde son saut, sauf suite de phrase en minuscule ou coupure « - » ; hors CJK) | `cas_blocs` (fiche 848b, contre-cas valeur sur deux lignes en minuscule) ; 98 cas : 848b et 70ced changent, gains (liste « CC: » : noms séparés, « S. Tesh » à la taille de l'original) ; interne identique ; ouvert : graisse qui varie d'une ligne à l'autre dans une adresse (848b) et gras ajouté (70ced) → G4 ; « LORILLARD COUNSEL: » sur 3 lignes avec un texte long → G3/F3 ; « CASENAME », « Franciseo » (lecture) |
| F4 | Effacement d'un libellé qui mordait sur une valeur laissée telle quelle (« 415/986-5566 », « LORILLARD ») | Aucun code : déjà couvert par `_proteger` (T3) et F1 (« LORILLARD » n'est plus isolé) | Rendu 848b, libellés traduits et valeurs gardées : valeurs nettes ; ouvert : libellés qui débordent à gauche de la marge (F3) |
| G1 + F3 + G2 (colonne) | Libellés empilés d'une colonne (axe de graphique, fiche) recentrés un par un ou à des corps différents ; marge droite prise au bloc, pas à la page ; fond uni ouvert serré qui comprimait le texte | `_axes` : groupes gauche/droite ≥ `COLONNE_MIN` blocs, lignes ≤ `COLONNE_LARGE`×hl, blocs d'une ligne joints par bord commun (G1). `cadre` : groupe aligné → marge de la page (848b). `poser` : en colonne, fond uni ouvert ignoré, sauf bord qui est un aplat d'une autre couleur (`_aplat` : barre de graphique, écart > `APLAT_ECART`, uni ≤ `APLAT_BRUIT`). Repli R2 : la taille ne fait plus céder (série d'un corps, F3) | `cas_axes` (colonne d'axe, contre-cas coupé), `cas_aplat` (barre, texte, fond pâle) ; public : gains f4554, 09fe, 0c30, 5a61, 3faab, b3374, f6ae, 9a53 ; recul 9a53 (« Slovenia » sur la barre) vu puis corrigé par `_aplat` ; 6739 corps 33→25 jugé acceptable ; interne identique ; ouverts (préexistants) : prix « 59 » coupé (09fe), lignes minuscules qui se chevauchent (3faab), « Drug S » coupé (b3374) |
| G3 (colonne) | Libellé de colonne qui prend une ligne de plus que l'original, ou qui rapetisse et laisse une case de tableau à moitié vide | `placer(serie=)` : rapetisser d'abord sur les lignes d'origine ; une ligne de plus seulement si elle écrit plus grand et reste dans `_bornes()` (lignes voisines, traductions posées) et `_traits()` (trait de tableau sous l'effacement) | 29 cas publics : gains (09fe, 0c30, 5a61, 497e, f4554…), 05e8 et 6739 « Carb » sans chevauchement ; compromis : 1ec6 « Name: » et 3651 plus grands ; interne identique à avant G3 ; tests 5/5 |
