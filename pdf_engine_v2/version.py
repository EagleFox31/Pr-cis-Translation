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
ENGINE_VERSION = "v21"
