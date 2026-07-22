"""Version du moteur de rendu PDF — entre dans les clés de cache.

POURQUOI CE FICHIER EXISTE
--------------------------
Le résultat d'une traduction était mis en cache sous une clé faite du nom, du
hash du contenu, de la langue, de la qualité et de la sélection de pages. Aucune
de ces cinq valeurs ne bouge quand on CORRIGE LE MOTEUR. Un document déjà
traduit continuait donc à servir éternellement le PDF d'avant le correctif :
P15 à P20 livrés, et l'utilisateur voyait toujours l'ancienne mise en page.

Le cache n'était pas de trop : il était MALHONNÊTE. Il prétendait que la sortie
ne dépendait que de l'entrée, alors qu'elle dépend aussi du code qui la produit.
`v2_pages.json` ne stocke d'ailleurs pas que la traduction — il stocke les
DÉCISIONS du moteur (`align`, `container_bbox`, ~55 fois par page). Le rejouer,
c'est rejouer la géométrie d'une version antérieure.

QUAND LA CHANGER
----------------
À tout correctif qui peut changer un PIXEL du rendu : géométrie, alignement,
regroupement en paragraphes, reflow, choix de police. Une modification qui ne
touche ni le rendu ni le découpage (journalisation, tests, commentaires) ne la
concerne pas.

Ne pas la changer quand il le fallait, c'est resservir un rendu périmé sans que
rien ne le signale — le bug est SILENCIEUX, et c'est ce qui le rend coûteux :
on croit avoir corrigé, l'utilisateur voit le contraire, et on cherche le
défaut dans le moteur alors qu'il est dans la clé.
"""

# Historique — une ligne par incrément, pour que la raison survive au commit.
#   v20 : état à la livraison de P15-P17 (colonnes justifiées, corridors)
#   v21 : P18-P20 — légendes centrées, cadre surplombant, listes numérotées
#   v22 : P21-P26 — satellites exposants, graisse pondérée, padding cellule,
#         plancher global, césure >=3, glossaire de document. Le bump avait été
#         OUBLIÉ à leur livraison : les rendus d'avant correctif continuaient
#         d'être servis.
#   v23 : aperçu PPTX — les rendus en cache ont pu être produits par des moteurs
#         PPTX concurrents qui partageaient un dossier temporaire. Un tel rendu
#         peut contenir la traduction d'UNE AUTRE LANGUE : il ne suffit pas de
#         corriger le moteur, il faut rendre ces fichiers introuvables.
#   v24 : contrat des balises de runs (runtags) — un run non couvert ou recopié
#         en langue source n'affiche plus l'original collé à la traduction. Le
#         rendu d'un PPTX change, les anciens sont périmés.
#   v25 : aperçus OLE Excel — la feuille est rendue sur UNE page (le graphique
#         posé à côté du tableau n'est plus jeté avec la 2e page) et l'image
#         prend les proportions de son cadre (plus d'étirement).
#   v26 : parties PARTAGÉES (slideLayout, slideMaster) extraites et injectées
#         une seule fois par document. Leur identité change (`slide0_…`) et le
#         texte des masques n'est plus celui de la dernière diapositive traitée :
#         le rendu diffère, les caches antérieurs sont périmés.
#   v27 : aperçus OLE TRANSPARENTS. L'image de remplacement était un aplat
#         opaque là où l'EMF d'origine ne peint rien : toute forme posée sous
#         le cadre OLE (flèche, filigrane, bandeau) disparaissait. Le pixel
#         change partout où le cadre survole autre chose que le fond.
#   v28 : apercu progressif page par page. Le PDF d'apercu part du document
#         d'ORIGINE puis chaque page traduite REMPLACE la sienne. Ce qu'un
#         cache anterieur contient n'a plus la meme signification.
ENGINE_VERSION = "v28"
