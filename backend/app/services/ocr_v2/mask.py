"""Masque des pixels de lettres (étude §5).

On n'efface que les lettres, pas la boîte entière : +2,6 dB en moyenne sur le
banc, et une flèche qui traverse le texte reste en place.
"""
import cv2
import numpy as np

# Plancher de distance de couleur (Lab) : sous ce seuil, Otsu segmenterait le
# bruit d'un fond uni.
DISTANCE_MIN = 18.0
# Un segment horizontal ou vertical plus long que cette part de la boîte est un
# trait du schéma, pas une lettre.
PART_TRAIT = 0.35
DILATATION = 2
# Débord examiné autour de la boîte pour reconnaître un trait qui la traverse.
MARGE_TRAIT = 4


def _couleur_fond_bord(roi):
    bord = np.concatenate([roi[0], roi[-1], roi[:, 0], roi[:, -1]]).astype(np.float32)
    return np.median(bord, axis=0)


def _pixels_du_trait(roi, long, interieur, fond):
    """Pixels de `long` qui ont la couleur de leur trait, ou un mélange de
    celle-ci et du fond (anticrénelage d'un trait de 2 px : la médiane tombe
    entre les deux rangées et n'en reconnaît aucune).

    Seuls comptent les segments qui sortent de la boîte `interieur` (tranches
    dans `roi`) : une barre de lettre y reste, un trait de schéma la traverse.
    Là où une lettre recouvre le trait, la rangée reste continue et l'ouverture
    la garde en entier : sans le filtre de couleur, les pixels de lettre posés
    sur le trait sortiraient du masque et resteraient visibles.
    """
    garde = np.zeros(long.shape, bool)
    dedans = np.zeros(long.shape, bool)
    dedans[interieur] = True
    n, etiq = cv2.connectedComponents(long.astype(np.uint8))
    for i in range(1, n):
        sel = etiq == i
        if not (sel & ~dedans).any():
            continue
        px = roi[sel]
        d = np.linalg.norm(px - fond, axis=1)
        coeur = np.median(px[d >= np.median(d)], axis=0) - fond
        t = np.clip((px - fond) @ coeur / max(float(coeur @ coeur), 1.0), 0, 1)
        garde[sel] = np.linalg.norm(px - fond - t[:, None] * coeur, axis=1) < DISTANCE_MIN
    return garde


def masque_couleur(image, boites, proteger_traits=True, dilatation=DILATATION):
    """Masque `uint8` (255 = lettre) des boîtes `(x, y, w, h)`.

    1. distance de couleur au fond mesuré sur le BORD de la boîte : marche pour
       un texte clair, sombre ou coloré sans règle d'inversion ;
    2. seuil d'Otsu sur cette distance, avec un plancher ;
    3. retrait des traits longs horizontaux et verticaux qui sortent de la
       boîte (schéma, tableau) ;
    4. dilatation : sans elle, l'anticrénelage laisse un liseré visible.
    """
    mask = np.zeros(image.shape[:2], np.uint8)
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB).astype(np.float32)
    H, W = mask.shape
    for x, y, w, h in boites:
        roi = lab[y:y + h, x:x + w]
        if roi.size == 0:
            continue
        fond = _couleur_fond_bord(roi)
        dist = np.linalg.norm(roi - fond, axis=2)
        haut = max(float(dist.max()), 1.0)
        d8 = np.clip(dist / haut * 255, 0, 255).astype(np.uint8)
        seuil, _ = cv2.threshold(d8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        seuil = max(seuil / 255 * haut, DISTANCE_MIN)
        txt = (dist > seuil).astype(np.uint8) * 255
        if proteger_traits:
            # Boîte élargie de MARGE_TRAIT : un trait qui la traverse en sort.
            y0, x0 = max(y - MARGE_TRAIT, 0), max(x - MARGE_TRAIT, 0)
            grand = lab[y0:min(y + h + MARGE_TRAIT, H), x0:min(x + w + MARGE_TRAIT, W)]
            txt_g = (np.linalg.norm(grand - fond, axis=2) > seuil).astype(np.uint8) * 255
            longueur = max(25, int(PART_TRAIT * max(w, h)))
            # Bord à 0 : par défaut OpenCV prolonge l'image au-delà du bord.
            horiz = cv2.morphologyEx(txt_g, cv2.MORPH_OPEN, np.ones((1, longueur), np.uint8),
                                     borderType=cv2.BORDER_CONSTANT, borderValue=0)
            vert = cv2.morphologyEx(txt_g, cv2.MORPH_OPEN, np.ones((longueur, 1), np.uint8),
                                    borderType=cv2.BORDER_CONSTANT, borderValue=0)
            interieur = (slice(y - y0, y - y0 + h), slice(x - x0, x - x0 + w))
            garde = _pixels_du_trait(grand, (horiz > 0) | (vert > 0), interieur, fond)
            txt[garde[interieur]] = 0
        mask[y:y + h, x:x + w] = np.maximum(mask[y:y + h, x:x + w], txt)
    if dilatation:
        mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=dilatation)
    return mask


def anneau(mask, largeur=8, exclure=None):
    """Couronne de `largeur` px autour du masque, hors pixels `exclure`."""
    d = cv2.dilate(mask, np.ones((2 * largeur + 1, 2 * largeur + 1), np.uint8))
    a = (d > 0) & (mask == 0)
    if exclure is not None:
        a &= exclure == 0
    return a


def composantes(mask):
    """Zones du masque (lettres voisines regroupées), une par une."""
    n, lab = cv2.connectedComponents((cv2.dilate(mask, np.ones((9, 9), np.uint8)) > 0).astype(np.uint8))
    for i in range(1, n):
        yield (lab == i) & (mask > 0)
