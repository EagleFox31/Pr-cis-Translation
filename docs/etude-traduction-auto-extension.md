# Étude — traduction automatique dans l'extension (fenêtre popup, « toujours », proposition)

## Besoin
Le cours SCORM 937 s'ouvre par `window.open` dans une fenêtre popup Edge, sans barre d'extensions : le bouton de l'extension est inaccessible et la fenêtre ne se traduit pas. Copier le lien dans un onglet casse le suivi SCORM (lien avec l'ouvreur perdu). L'utilisateur veut aussi, comme le traducteur intégré du navigateur, qu'une page dans une autre langue propose la traduction.

Contraintes : jamais `<all_urls>` imposé (décision produit) ; origine demandée au clic ; aucune traduction (donc aucun débit) sans geste explicite de l'utilisateur ou choix « toujours » qu'il a fait.

## Existant
- `lib/suivi.ts` : suivi par onglet (`chrome.storage.session`, clé `suivi:<tabId>` = `{ langue, origine }`), écrit par le popup après « Traduire », effacé par « Original », par la fermeture de l'onglet ou par un départ vers une autre origine (`tabs.onUpdated`).
- `background.ts` : `synchroniserScripts` enregistre `content.js` (tous cadres) pour les origines suivies ; chaque nouveau document demande `{type:"suivi"}` et se traduit seul s'il reçoit une langue.
- `popup.ts` : demande la permission de l'origine, injecte `content.js`, envoie `traduire`, écrit le suivi.
- `contenu/bandeau.ts` : bandeau en Shadow DOM (`message`, `demanderAccord` avec case « Toujours pour ce site »).
- `content.js` pèse ~38 Ko.

Cause du bug : la fenêtre popup est un nouvel onglet (`tabId` différent) ; le script enregistré y tourne bien, mais `suivi:<nouvel onglet>` n'existe pas, donc il ne fait rien.

## Options

| Option | Pour | Contre |
|---|---|---|
| a. Hériter du suivi de l'ouvreur (`tabs.onCreated`, `openerTabId`) | Corrige le cours sans rien demander ; aucune permission nouvelle | Ne couvre que les fenêtres ouvertes depuis un onglet déjà traduit |
| b. « Toujours appliquer pour ce site » (stockage local, script persistant) | Couvre toute fenêtre, toute session, sans bouton | Débit automatique sur ce site : choix explicite requis |
| c. Raccourci Alt+Shift+T et menu contextuel | Secours dans une fenêtre sans barre ; `activeTab` suffit pour la page courante | Les documents suivants ne se traduisent seuls que si l'origine est déjà accordée |
| e. Détection de langue + bandeau de proposition | Confort du traducteur intégré | Exige `<all_urls>` et `content.js` sur toutes les pages |

## Choix
Les quatre, complémentaires (a, b, c, e validés le 06/11) :

1. **Héritage (a)** : à la création d'un onglet avec `openerTabId` suivi, recopier `{ langue, origine }`. `tabs.onUpdated` n'oublie plus un onglet sur une adresse non http(s) (`about:blank` initial de `window.open`) : `resteSuivi` vrai si l'adresse n'a pas d'origine web.
2. **Règle de site (b + e)** : `chrome.storage.local`, clé `site:<origine>` = `{ mode: "traduire", langue }` ou `{ mode: "original" }`. Une seule case « Toujours appliquer pour ce site », dans le popup et dans le bandeau : cochée avec « Traduire » → traduire d'office ; cochée avec « Original » → ne plus rien proposer sur ce site ; décochée dans le popup → règle retirée. Le script de suivi est enregistré pour l'union des origines suivies et des sites « traduire », avec `persistAcrossSessions: true`. Réponse `suivi` du background, dans l'ordre : suivi de l'onglet (sauf arrêt) → règle de site « traduire » (et le suivi de l'onglet est alors écrit) → proposition → rien.
   « Original » sur un site « toujours traduire » sans case cochée : arrêt pour cet onglet seulement (`suivi` avec `arret: true`), la règle reste.
3. **Secours (c)** : `commands` (Alt+Shift+T : traduit l'onglet actif, ou rétablit l'original s'il est suivi) et `contextMenus` (« Traduire cette page avec Précis », « Afficher l'original »). Même fonction que le popup, partagée dans `lib/onglet.ts`. Permissions `commands` (implicite) et `contextMenus` ajoutées.
4. **Proposition (e)** : option « Proposer la traduction automatiquement » dans le popup, **désactivée par défaut**. L'activer demande `<all_urls>` (déjà en `optional_host_permissions`) ; un script `precis-detection` (cadre principal, http/https) est alors enregistré. Le cadre principal, sans suivi ni règle, lit un échantillon de texte (2 000 caractères, ignoré sous 200), appelle `chrome.i18n.detectLanguage` et compare avec la langue cible (choix stocké, sinon langue du navigateur si proposée, sinon français) ; `<html lang>` sert de repli quand la détection n'est pas fiable. Langue différente → bandeau « Cette page est en <langue>. » + case + [Traduire] + [Afficher l'original] + fermer. Fermer = rien pour cette page.

Langue cible par défaut : celle du navigateur si elle figure dans la liste, sinon `fr`.

## Impacts
- Sécurité / vie privée : aucune permission nouvelle par défaut ; `<all_urls>` seulement sur option ; la détection est locale (API du navigateur), rien n'est envoyé au serveur avant « Traduire ».
- Coût : un site en « toujours traduire » débite ses pages sans clic, conformément au choix de l'utilisateur. La mémoire de traductions évite de redébiter une page déjà vue.
- Performance : avec l'option, `content.js` (~38 Ko) s'exécute sur chaque page ; il ne fait qu'une détection locale.
- Données : `chrome.storage.local` (règles, option) ; rien côté serveur.
- Serveur, site : aucun changement.

## Risques
- Les cadres d'une autre origine que la page ne sont couverts que s'ils ont la permission (limite existante).
- Le raccourci peut entrer en conflit avec un autre ; l'utilisateur peut le changer dans `edge://extensions/shortcuts`.
- Retirer l'option ne retire pas `<all_urls>` (le retrait pourrait emporter les origines accordées) ; on désenregistre seulement le script de détection.

## Points à trancher
Aucun bloquant. Défaut retenu pour la permission de la détection : option désactivée par défaut, à rappeler à la livraison.
