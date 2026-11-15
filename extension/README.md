# Précis — extension navigateur (prototype)

Extension MV3 pour Edge et Chrome : traduit le texte d'une page, puis les images contenant du texte, en s'appuyant sur le compte Précis (connexion, crédits).

- Texte : moteur Précis, par bloc avec le contexte de la page (1 500 caractères = 1 page de crédit).
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

Sans compilation : télécharger le ZIP depuis la page `/extension` du site (bouton « Télécharger l'extension », tant qu'aucune boutique n'est renseignée), le décompresser dans un dossier fixe, puis charger ce dossier de la même façon. Pas de mise à jour automatique : re-télécharger, remplacer le dossier, puis « Actualiser » sur la page des extensions.

À la première traduction sur un site, le navigateur demande l'accès à ce site. Si la fenêtre de l'extension se ferme à ce moment, rouvrir l'extension et cliquer de nouveau sur « Traduire cette page ».

## Basculer entre local et production

`npm run build` vise le poste local (API `localhost:8000`, site `localhost:3000`). `npm run build -- --prod` injecte `https://precis-translator.trigenys.com` et retire `localhost` du manifest ; rien à modifier à la main.

## Commandes

- `npm run typecheck` : vérification des types.
- `npm test` : tests de la logique pure (`src/lib`), Node 22.
- `npm run build` : génère `dist/` (local).
- `npm run package` : build de production + `precis-translator-<version>.zip`, l'archive à envoyer aux boutiques (voir `docs/fiches-boutiques-extension.md`). Monter `version` dans `manifest.json` avant chaque envoi. L'archive est aussi copiée vers `frontend/public/extension/precis-extension.zip` (gitignoré), servie par le site pour l'installation manuelle ; relancer `npm run package` avant de construire le site.

## Lien avec le site

- À l'installation, l'extension ouvre `/extension?bienvenue=1` sur le site.
- Connexion par le site uniquement (`src/connexionSite.ts`) : onglet `/extension/autoriser` + code à usage unique de 60 s + PKCE S256 + `state` ; l'extension lit le fragment de `/extension/connecte` et reçoit sa propre session (déconnexion indépendante du site). Voir `docs/etude-connexion-extension.md`.
- Le site demande si l'extension est présente (`externally_connectable`, message `precis-ping`) ; seule l'origine du site est admise.

## Couvert et limites

Couvert : texte visible, attributs `alt`, `title`, `placeholder`, `aria-label`, texte SVG, shadow DOM ouvert, texte ajouté après coup, images (`img`, fonds CSS, canvas), vidéos en pause.

Limites assumées du prototype :

- un cadre (iframe) d'une autre origine non accordée n'est pas traité ;
- le shadow DOM fermé n'est pas accessible ;
- les boîtes `alert` / `confirm` du navigateur ne sont pas traduites ;
- les PDF ne sont pas traités ;
- les images animées (source qui change en boucle) sont ignorées ;
- les images servies par un autre domaine que le site peuvent être illisibles pour l'extension (essai depuis la page, soumis aux règles CORS du site).
