"""OCR v2 : effacer le texte d'une image en ne touchant que ses lettres.

Une étape par module, chacun testable seul (voir `docs/etude-ocr-v2.md` §3) :

    mask.py   pixels des lettres dans les boîtes lues
    erase.py  remplissage, méthode choisie zone par zone (masque fantôme)
    render.py redressement, couche de texte dans le style mesuré (police, corps,
              gras, italique, couleur)
    image.py  image traduite pour l'extension (lecture, effacement, dessin de
              la traduction à la place du texte)

Les images sont des tableaux numpy BGR `uint8` (convention OpenCV) et les
boîtes des tuples `(x, y, w, h)` en pixels.
"""
from .erase import effacer
from .mask import masque_couleur

__all__ = ["effacer", "masque_couleur"]
