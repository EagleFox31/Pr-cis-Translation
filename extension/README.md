# Précis — extension navigateur (prototype)

Extension MV3 pour Edge et Chrome : traduit le texte d'une page, puis les images contenant du texte, en s'appuyant sur le compte Précis (connexion, crédits).

- Texte : API de traduction intégrée au navigateur (Chrome 138+, gratuit) ou « Qualité Précis » (crédits).
- Images : envoyées à Précis après accord (bandeau dans la page), débit seulement si l'image est effectivement traduite.
- Vidéos : en pause, bouton « Traduire cette image » (1 crédit).
- « Afficher l'original » rétablit la page.

## Installation manuelle

```bash
cd extension
npm install
npm run build
```

Puis `edge://extensions` ou `chrome://extensions` : activer le mode développeur, « Charger l'extension non empaquetée », choisir le dossier `extension/dist`.

À la première traduction sur un site, le navigateur demande l'accès à ce site. Si la fenêtre de l'extension se ferme à ce moment, rouvrir l'extension et cliquer de nouveau sur « Traduire cette page ».

## Basculer entre local et production

Dans `src/config.ts`, `API_BASE` (et l'adresse du site pour la page des tarifs) vaut `http://localhost:8000` par défaut. Pour la production, mettre `https://precis-translator.com`, puis relancer `npm run build` et recharger l'extension.

## Commandes

- `npm run typecheck` : vérification des types.
- `npm test` : tests de la logique pure (`src/lib`), Node 22.
- `npm run build` : génère `dist/`.

## Couvert et limites

Couvert : texte visible, attributs `alt`, `title`, `placeholder`, `aria-label`, texte SVG, shadow DOM ouvert, texte ajouté après coup, images (`img`, fonds CSS, canvas), vidéos en pause.

Limites assumées du prototype :

- un cadre (iframe) d'une autre origine non accordée n'est pas traité ;
- le shadow DOM fermé n'est pas accessible ;
- les boîtes `alert` / `confirm` du navigateur ne sont pas traduites ;
- les PDF ne sont pas traités ;
- les images animées (source qui change en boucle) sont ignorées ;
- les images servies par un autre domaine que le site peuvent être illisibles pour l'extension (essai depuis la page, soumis aux règles CORS du site) ;
- l'API de traduction du navigateur peut nécessiter le téléchargement préalable d'un modèle de langue ; en cas d'échec, utiliser « Qualité Précis ».
