# Étude : analyse des images avant l'accord (extension)

## Besoin
Quand une page s'ouvre, son texte est traduit. Les images visibles sont
envoyées au serveur, qui les analyse. La demande d'accord n'annonce que le
nombre d'images **réellement traduisibles**. Une image sans texte, ou dont le
texte est déjà dans la langue voulue, n'est jamais comptée ni montrée.

## Existant
- L'extension mettait en file toutes les images de la page, cachées comprises.
  La demande d'accord annonçait « N images avec du texte possible ». N était un
  nombre d'images, pas un nombre d'images à texte.
- `POST /api/extension/image` fait la lecture (OCR), la traduction et le rendu,
  puis débite 1 crédit si l'image est remplacée. Le résultat va dans le cache
  partagé de 30 jours (`cache_images`) quand il est complet.
- Budgets par page (`limites_page`) : `analyses` (120) pour chaque OCR,
  `images` (30) pour chaque image remplacée.

## Options

| Option | Pour | Contre |
|---|---|---|
| A. Analyse = lecture seule (OCR), « traduisible » = texte trouvé | Pas d'appel au moteur de traduction avant l'accord | Compte aussi les images dont le texte est déjà dans la langue voulue. Il faut refaire l'OCR ou le garder pour la traduction |
| B. Analyse = travail complet sans débit ni renvoi d'image ; le résultat est gardé | Compte exact (« remplacée » = traduisible). La traduction après accord est instantanée | Le moteur traduit quelques mots même si l'utilisateur refuse |
| C. Analyse côté extension (OCR local) | Aucun appel serveur | Lourd, lent, et diverge du résultat du serveur |

## Choix : A (révisé le 07/11/2026, d'abord B)
B traduisait et dessinait l'image avant toute réponse de l'utilisateur, ce qui
ralentissait l'analyse (≈ 4 s contre < 1 s) et faisait du travail inutile. On
garde A : l'analyse ne fait que lire l'image ; rien n'est traduit tant que
personne ne le demande.

- `POST /api/extension/image/analyse` renvoie `{traduisible: bool}` (texte
  trouvé ou non). Il ne débite rien et ne renvoie ni l'image ni le texte, pour
  qu'on ne puisse pas s'en servir pour traduire gratuitement. Il demande que le
  compte couvre au moins une page (402 sinon) et prend le budget `analyses`.
- Les lignes lues sont gardées 15 minutes en mémoire, par compte et par image,
  sans la langue (64 entrées au plus). `/image` les reprend : traduction et
  rendu seulement, même débit, sans nouvel OCR et sans reprendre le budget
  `analyses`.
- Côté extension : images visibles → analyse (deux à la fois) → seules les
  traduisibles entrent dans la file. L'accord annonce « N images à traduire — jusqu'à
  N crédits » (une image déjà traduite pour ce compte n'est pas redébitée). S'il n'y en a aucune, rien n'est demandé. Défilement, clic ou
  redimensionnement : les nouvelles images visibles suivent le même chemin.
  Après l'accord, elles sont traduites sans nouvelle question.

## Impacts
- Données : aucune migration. La mémoire du processus est bornée (64 lectures).
- Sécurité : l'analyse ne rend aucun contenu et reste bornée par page et par
  minute (60/min).
- Coût : une lecture OCR par image visible ; aucune traduction avant l'accord.
- Limite : une image dont le texte est déjà dans la langue voulue est annoncée
  mais ni remplacée ni débitée.
- Plusieurs workers : si l'analyse et la traduction tombent sur deux workers
  différents, la mémoire ne sert pas. Le cache disque prend le relais, sinon
  l'image est refaite. Le résultat reste juste, la traduction est seulement plus
  lente.

## Risques
- La lecture d'une analyse peut être incomplète (délai dépassé). Elle reste
  propre au compte et expire au bout de 15 minutes.
