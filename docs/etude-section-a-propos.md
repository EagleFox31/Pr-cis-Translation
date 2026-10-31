# Étude : section « À propos » de l'accueil

## 1. Besoin
La section « À propos » est le dernier écran de l'accueil, juste avant le pied de page. Le visiteur y arrive après avoir vu le produit et les tarifs, avec une seule question : **« Puis-je confier mes documents et mon argent à ces gens-là ? »**. La section doit y répondre en un écran, avec des faits vérifiables.

Critères d'acceptation :
- On lit qui édite Précis, où est l'entreprise et comment la joindre, sans quitter l'écran.
- Chaque affirmation se vérifie, dans le produit ou par un lien. Aucune formule creuse.
- Tout tient sur 1266 × 900, pied de page compris ; la section s'empile sur mobile (390 px).
- Mêmes jetons visuels que le reste du site (`section-tag`, `section-title`, `--navy`).

## 2. Existant
| Élément | Constat |
|---|---|
| `components/about/AboutSection.tsx` | Deux colonnes : à gauche le texte, à droite la mascotte. Le pied de page est intégré à la section, qui occupe un plein écran avec accroche au défilement (`index.css` : `min-height: 100vh`, `scroll-snap`). |
| Texte (`about.*`) | Il présente Trigenys Group (Douala, logiciel, cloud, données, AgenStudio, Trigenys Insight) mais **ne parle pas de Précis**. AgenStudio et Insight sont cités sans lien. |
| Valeurs (`val_*`) | Trois mots (Ingénierie, Fiabilité, Sécurité) avec trois sous-titres de 3 à 4 mots. Ce sont des promesses sans preuve. « Cybersécurité intégrée » ne renvoie à rien de visible. |
| Mascotte | `Identite Precis.png` apparaît déjà sur l'écran de démarrage et sur les pages de connexion. Ici, elle n'apporte aucune information. |
| Pied de page | Les liens Mentions légales, CGU et Confidentialité pointent vers `#` : ils sont **morts**. |
| Contact | Aucune adresse e-mail publique, aucun lien LinkedIn ou Facebook dans le site. |
| Faits produit vérifiés dans le code | Les documents sont gardés dans la bibliothèque et l'utilisateur peut les supprimer (`api/documents.py`, `delete_document`). Une traduction arrêtée garde le travail déjà fait, qui n'est pas facturé deux fois. Le paiement se fait par Mobile Money (Fapshi) ou par carte (Paddle). Il n'y a **aucune suppression automatique** des fichiers. La traduction passe par un **service d'IA externe** (DeepSeek, `config.py`). |

## 3. Ce que dit la recherche
- On consulte une page « À propos » d'abord pour **vérifier qu'une entreprise existe vraiment**. On y cherche une adresse, un moyen de contact, des personnes réelles, et un ton direct plutôt que publicitaire (travaux de Nielsen Norman Group, cités indirectement par les sources ci-dessous ; l'article d'origine n'a pas été relu).
- Une preuve placée **à côté** de l'affirmation qu'elle soutient pèse plus qu'une liste de valeurs.
- Pour un outil qui traite des documents, les éléments de confiance qui reviennent sont : ce que deviennent les fichiers (durée de conservation, suppression), qui les traite (sous-traitants), et une page de confidentialité qui existe vraiment.
- Les témoignages et les logos de clients comptent beaucoup, mais seulement s'ils sont **réels**. Précis est en bêta : il n'y en a pas encore, donc on n'en met pas.

Ces sources sont surtout des blogs marketing. Elles convergent toutefois sur ces points, qui sont aussi du bon sens.
Sources : [NN/g, cité par Data & Design](https://dataanddesign.substack.com/p/learning-to-design-about-us-pages), [Alphonso Labs](https://www.alphonsolabs.com/about-page-essential-elements-2026/), [Ritner Digital](https://www.ritnerdigital.com/blog/the-best-about-us-pages-dont-start-with-we-were-founded-in), [Bluente, sécurité de la traduction](https://www.bluente.com/blog/document-translation-security-compliance), [GTS Trust Center](https://www.gts-translation.com/about-us/gts-translation-trust-center/), [Flighted](https://www.flighted.co/blog/10-saas-landing-page-best-practices-that-actually-convert).

## 4. Options comparées
| Option | Pour | Contre |
|---|---|---|
| A. Garder la structure, retoucher le texte | Rien à coder | Pas de contact, des valeurs sans preuve, une mascotte inutile : la question de confiance reste sans réponse |
| B. **Deux colonnes : récit court + engagements prouvés à gauche, fiche d'identité de l'éditeur à droite** | Répond à la question de confiance sur un seul écran, avec des faits vérifiables ; même grille qu'aujourd'hui | Il faut une adresse de contact publique et des pages légales réelles |
| C. Page « À propos » séparée (équipe, histoire, presse) | Place pour tout dire | Trop tôt : une équipe de 2 à 10 personnes en bêta remplirait une page de vide |

## 5. Recommandation : option B
```
┌─────────────────────────────────────────────┬──────────────────────────────┐
│ À PROPOS                                    │  ┌ L'éditeur ──────────────┐ │
│ Précis, conçu par Trigenys Group            │  │ Trigenys Group          │ │
│ [Pourquoi Précis, en une ou deux phrases]   │  │ Douala, Cameroun        │ │
│                                             │  │ Fondée en 2026          │ │
│ ✓ Vos documents restent à vous              │  │ ✉ contact@…             │ │
│   bibliothèque privée, suppression à tout   │  │ in LinkedIn · Insight   │ │
│   moment                                    │  │ AgenStudio              │ │
│ ✓ Vous payez ce qui est traduit             │  └─────────────────────────┘ │
│   travail arrêté conservé, jamais facturé   │   [Nous écrire]              │
│   deux fois                                 │                              │
│ ✓ Payer comme vous voulez                   │                              │
│   Mobile Money ou carte bancaire            │                              │
├─────────────────────────────────────────────┴──────────────────────────────┤
│ © 2026 Précis by Trigenys Group      Mentions légales · CGU · Confidentialité │
└────────────────────────────────────────────────────────────────────────────┘
```
1. **Titre** : « Précis, conçu par Trigenys Group ». C'est le produit qui est porté par l'entreprise, et non l'inverse.
2. **Récit (au plus deux phrases)** : *pourquoi* Précis existe, et non la liste des métiers du groupe. La liste détaillée (logiciel, cloud, données…) reste sur LinkedIn et Insight, accessibles par un lien.
3. **Trois engagements prouvés**, à la place des trois valeurs. Chacun est vrai dans le produit aujourd'hui :
   - documents dans une bibliothèque privée, que l'utilisateur supprime quand il veut ;
   - travail conservé en cas d'arrêt, jamais facturé deux fois ;
   - Mobile Money ou carte.
   Aucune promesse invérifiable, par exemple « supprimés sous 24 h », qui serait fausse.
4. **Fiche d'identité de l'éditeur** à la place de la mascotte : raison sociale, ville et pays, année de création, contact, liens vers LinkedIn, Trigenys Insight et AgenStudio. Ce sont exactement les signes que le visiteur cherche pour vérifier que l'entreprise existe.
5. **Bouton « Nous écrire »** : il ouvre l'adresse de contact. Pour un utilisateur connecté, il peut renvoyer vers le support existant.
6. **Pied de page** : remplacer les liens morts par de vraies pages (Mentions légales, CGU, Confidentialité). Ce travail est hors de cette section (voir § 8), mais un lien mort, au moment précis où l'on vérifie la confiance, produit l'effet inverse.

**Écarté** : témoignages et logos clients (aucun n'est réel pour l'instant), chiffres d'usage (aucun n'est publiable), mot « leader » et superlatifs, mascotte répétée.

## 6. Impacts
- Code : `AboutSection.tsx` seulement, plus quelques règles CSS. Les styles en ligne passent en classes `about-*` dans `index.css`, comme les autres sections.
- i18n : les clés `about.*` sont réécrites en fr et en en. Les clés `val_*` sont remplacées par `pledge_*`, et de nouvelles clés `identity_*` et `contact` apparaissent.
- Serveur et données : aucun changement.
- Sécurité et juridique : n'affirmer rien sur le traitement des données au-delà de ce qui est vrai (voir point 4 du § 7).

## 7. Points tranchés par l'utilisateur
1. **Contact** : `contact@trigenys.com` (lien e-mail et bouton « Nous écrire »). Téléphone et WhatsApp passent par `VITE_CONTACT_PHONE` / `VITE_CONTACT_WHATSAPP` dans `frontend/.env` ; tant qu'une variable est vide, sa ligne n'apparaît pas.
2. **Pourquoi Précis** : pas d'angle français / anglais. Le texte décrit le vrai défi : Précis reprend la méthode des traducteurs de métier (lire tout le document, fixer une terminologie, garder la mise en page) et l'automatise.
3. **Visage humain** : aucun nom. L'entreprise reste anonyme.
4. **Confidentialité** : rien dans la section sur le prestataire de traduction. Ce point ira dans la future page Confidentialité, et la section ne promet rien de contraire.
5. **Liens** : LinkedIn et Facebook de Trigenys Group. Trigenys Insight renvoie vers insight.trigenys.com ; AgenStudio reste sans lien (pas de site en ligne). Téléphone et WhatsApp : la ligne MTN, renseignée dans `frontend/.env`.
6. **Rien qui dessert** : pas d'année de création, pas de délai de réponse promis.
7. **Finition (retour après la première version)** : texte en une phrase de méthode, justifié ; e-mail · LinkedIn · Facebook sur une ligne ; la mascotte revient, la tête au-dessus de la fiche ; « Nous écrire » ouvre une fenêtre. Utilisateur connecté : la fenêtre d'assistance existante. Visiteur : l'assistance exige un compte, donc une fenêtre de contact (e-mail, WhatsApp et téléphone si renseignés), en panneau bas sur mobile.

## 8. Hors périmètre, à prévoir
Pages Mentions légales, CGU et Confidentialité, à créer sur une branche dédiée, avec une validation juridique. Elles devraient exister avant l'ouverture publique.
