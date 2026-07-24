"""
Aperçu d'ESSAI — ce qu'un plan gratuit a le droit de recevoir.

POURQUOI CE MODULE EXISTE
-------------------------
Le verrou d'essai n'a longtemps vécu que dans le navigateur : le serveur
envoyait le PDF traduit EN CLAIR et le client le repeignait
(`filter: brightness(15%)`). Mesuré : un compte `free` appelant /partial
recevait « 200, 454 882 octets, application/pdf — 1 page, 782 mots
EXTRACTIBLES, 31 dessins ». Autrement dit, pas « il peut copier le texte » :
il repartait avec LE FICHIER, identique à celui d'un client payant, en trois
clics dans l'onglet Réseau. Repeindre une image ne protège rien quand
l'original est déjà dans la mémoire de l'onglet.

CE QUE ÇA PROTÈGE, ET CE QUE ÇA NE PROTÈGE PAS
----------------------------------------------
Le pixel est copiable par nature : une capture d'écran restera toujours
possible, aucune technologie web n'y peut rien. On ne protège donc PAS le fait
de REGARDER — on protège le fait de REPARTIR AVEC UN DOCUMENT EXPLOITABLE :
texte sélectionnable, mise en page réutilisable, fichier propre.

Après rastérisation, le document n'est plus que des pixels : aucun mot du texte
traduit n'est extractible (mesuré : 782 -> 0). AUCUNE couche texte ne subsiste,
pas même le filigrane : il est CUIT dans les pixels (double rastérisation), donc
on ne le retire pas en supprimant des objets texte. Plus de polices, plus de
vecteurs. Pour en tirer un document, il faudrait l'OCR —
c'est-à-dire refaire soi-même, en moins bien, le travail qu'on vend. Le vol
devient plus cher que l'abonnement : c'est le seul niveau de protection honnête
pour du contenu affiché dans un navigateur.

Le projecteur au survol continue de fonctionner : il a besoin de pixels nets en
local, et il en a. C'est ce qui a fait écarter l'assombrissement côté serveur,
qui l'aurait tué.
"""
from __future__ import annotations

import fitz

from app.config import BRAND_NAME, BRAND_TAGLINE, PUBLIC_SITE

# Résolution de l'aperçu d'essai. Assez pour juger la mise en page et lire au
# projecteur ; pas de quoi produire une réimpression propre. Ce n'est pas un
# réglage de qualité, c'est le curseur du teaser.
TRIAL_DPI = 110

# Filigrane = MINI-PUBLICITÉ. Deux lignes : la marque, puis le métier + l'adresse
# du site. Le contenu est DYNAMIQUE (`app.config`) : changer de domaine ne touche
# pas ce moteur. Il ne « protège » pas à lui seul (on peut recadrer), mais il rend
# toute fuite IDENTIFIABLE — et, cuit dans les pixels (voir plus bas), il n'est
# plus une couche de texte qu'on détache : l'enlever demande de retoucher l'image.
_MARK_BRAND = BRAND_NAME
_MARK_SUB = f"{BRAND_TAGLINE} · {PUBLIC_SITE}"
_MARK_BRAND_SIZE = 19
_MARK_SUB_SIZE = 10
_MARK_STEP = 300          # pas de la trame, en points (banderoles espacées)
_MARK_COLOR = (0.10, 0.20, 0.55)
_MARK_OPACITY = 0.15


def rasterize_for_trial(pdf_bytes: bytes, pages=None,
                        dpi: int = TRIAL_DPI) -> bytes:
    """Rend en IMAGES filigranées les pages TRADUITES de `pdf_bytes`.

    `pages` : numéros 1-basés des pages effectivement traduites. None = toutes.

    On ne rastérise QUE ce qu'on a produit. Les autres pages du PDF partiel sont
    des copies conformes de l'original, que l'utilisateur possède déjà : les
    protéger n'a aucun sens, et coûte cher. Mesuré sur un document de 84 pages :
    5 544 ms et 9,6 Mo à tout rastériser, contre ~190 ms pour la seule page
    traduite — or le client recharge le partiel APRÈS CHAQUE PAGE. Un compte
    `free` n'a droit qu'à 1 page traduite : le cas courant est donc une page.

    Les pages gardent leurs dimensions d'origine : le viewer, la pagination et
    le zoom du client n'ont rien à savoir de tout ceci.

    En cas d'échec, on RELÈVE : renvoyer le PDF clair « pour ne pas casser
    l'aperçu » transformerait un bug en fuite silencieuse. L'appelant décide.
    """
    src = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        cibles = None if pages is None else {int(p) for p in pages}
        for i in range(len(src)):
            if cibles is not None and (i + 1) not in cibles:
                continue                      # copie de l'original : rien à cacher
            page = src[i]
            rect = page.rect
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            # On VIDE la page (texte, polices, vecteurs disparaissent) avant d'y
            # reposer son image : sans ce nettoyage, la couche texte survivrait
            # SOUS le pixmap — invisible à l'œil, intacte au copier-coller.
            page.clean_contents()
            src.delete_page(i)
            page = src.new_page(pno=i, width=rect.width, height=rect.height)
            page.insert_image(page.rect, pixmap=pix)
            _stamp(page)

            # CUISSON DU FILIGRANE. `_stamp` pose le texte en COUCHE, détachable
            # d'un coup en supprimant les objets texte. On re-rastérise donc la
            # page tamponnée en une image, qu'on repose seule : le filigrane vit
            # désormais dans les PIXELS. L'enlever demande de retoucher l'image
            # (bien plus cher qu'un simple « supprimer la couche texte »).
            baked = page.get_pixmap(dpi=dpi, alpha=False)
            src.delete_page(i)
            page = src.new_page(pno=i, width=rect.width, height=rect.height)
            page.insert_image(page.rect, pixmap=baked)
        return src.tobytes(garbage=3, deflate=True)
    finally:
        src.close()


def _stamp(page: fitz.Page) -> None:
    """Trame de mini-publicités en diagonale sur toute la page.

    Chaque motif porte DEUX lignes (marque, puis métier + site). Les deux
    tournent autour du MÊME point d'ancrage (`morph=(base, rot)`) pour rester
    solidaires — sinon chacune pivoterait sur elle-même et le bloc se disloquerait.
    """
    rot = fitz.Matrix(1, 1).prerotate(45)
    r = page.rect
    y = -int(r.height)
    while y < r.height + _MARK_STEP:
        x = 0
        while x < r.width + _MARK_STEP:
            base = fitz.Point(x, y)
            try:
                page.insert_text(base, _MARK_BRAND, fontsize=_MARK_BRAND_SIZE,
                                 fontname="hebo", color=_MARK_COLOR,
                                 fill_opacity=_MARK_OPACITY, morph=(base, rot))
                page.insert_text(fitz.Point(x, y + 14), _MARK_SUB,
                                 fontsize=_MARK_SUB_SIZE, fontname="helv",
                                 color=_MARK_COLOR, fill_opacity=_MARK_OPACITY,
                                 morph=(base, rot))
            except Exception:
                pass          # un filigrane manqué ne doit pas perdre la page
            x += _MARK_STEP
        y += _MARK_STEP
