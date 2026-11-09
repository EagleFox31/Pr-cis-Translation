# Étude : habiller l'interface de l'extension aux couleurs de Précis (6.9)

## Besoin et contraintes
- L'extension fonctionne, mais son interface (fenêtre du bouton, bandeau en bas de page,
  pastille de progression, bouton « Traduire cette image » sur les vidéos) est grise et
  générique : rien ne la rattache au site.
- Périmètre : **branding seulement**. Aucune modification de comportement, de texte ni de
  parcours. Pas de traduction de l'interface (hors sujet).
- Normes à suivre : celles des pages applicatives du site (`frontend/src/index.css`,
  primitives `ui-btn`, `champ`, `ui-alerte`, en-tête `auth-marque`).

## Existant
| Élément | Fichier | État |
|---|---|---|
| Fenêtre du bouton | `extension/src/popup.html` (styles en ligne) | gris ardoise `#1f2937`, police système, titre texte « Précis » |
| Bandeau + pastille | `extension/src/contenu/bandeau.ts` (`STYLE`, Shadow DOM fermé) | barre ardoise, liens `#93c5fd` |
| Bouton vidéo | `extension/src/contenu/video.ts` (`STYLE`) | ardoise translucide |
| Construction | `extension/build.mjs` | copie `manifest.json` et `popup.html` dans `dist/` |

Jetons du site réutilisés : `--navy #0d1b3e`, `--blue #1a4dc7`, `--blue-bright #2563eb`,
`--blue-light #dbeafe`, `--gold #c9a84c`, `--gray-50…900`, police de corps **DM Sans**,
marque = `Logo.png` (« P ») + « récis » en **Pinyon Script**, focus `2px solid --blue-bright`.

## Options
| Option | Pour | Contre |
|---|---|---|
| A. Recopier les jetons en variables CSS dans chaque surface, polices embarquées dans le paquet pour la fenêtre seulement | Hors ligne, aucune requête externe, aucune dépendance au site | Jetons dupliqués (≈ 15 valeurs) |
| B. Charger les polices Google depuis la fenêtre | Rien à embarquer | Requête tierce à chaque ouverture, à déclarer dans la confidentialité ; la CSP d'extension MV3 l'interdit par défaut |
| C. Injecter `@font-face` dans les pages visitées pour le bandeau | Même police partout | Modifie le document de la page hôte (le Shadow DOM n'enregistre pas de police) et exige des ressources accessibles au web : intrusif, détectable |

## Choix
**A.** Les jetons sont recopiés dans un module unique `extension/src/contenu/theme.ts`
(bandeau, vidéo) et dans `popup.html` (la fenêtre n'a pas de bundle CSS). DM Sans (400/500/600)
et Pinyon Script sont embarqués depuis `@fontsource` (licence OFL) pour la fenêtre seulement ;
le bandeau et le bouton vidéo utilisent `"DM Sans", system-ui` : DM Sans si l'utilisateur
l'a, police système sinon. Le logo `Logo.png` est copié du site.

Rendu retenu :
- fenêtre : en-tête de marque (« P » + « récis »), champs `champ__saisie`, bouton principal
  bleu, secondaire contour bleu, message d'erreur en `ui-alerte--error`, liens gris, focus visible ;
- bandeau et pastille : fond **navy**, bouton principal bleu, secondaire contour blanc
  (comme `btn-ghost` du site), liens or clair, focus visible ;
- bouton vidéo : navy translucide.

## Impacts
- Données, sécurité, backend : aucun. Aucune permission nouvelle.
- Poids du paquet : + ≈ 90 Ko (polices latines woff2 + logo).
- Les jetons dupliqués devront suivre une éventuelle évolution de la charte du site
  (commentaire de renvoi dans `theme.ts` et `popup.html`).

## Risques
- Contraste : vérifié aux couples retenus (blanc sur `#1a4dc7` ≈ 6,7:1 ; blanc sur `#0d1b3e` ≈ 17:1 ;
  `#f0d98a` sur `#0d1b3e` ≈ 12:1).
- Sites aux styles agressifs : le bandeau reste en Shadow DOM fermé, `all:initial` sur l'hôte inchangé.

## Points à trancher
Aucun : décisions de forme, prises ici. Icônes de la barre d'outils et du magasin → 6.12.
