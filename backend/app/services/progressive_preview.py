"""L'aperçu qui se remplit page par page.

LE FLUX, EN DEUX TEMPS
----------------------
1. **SOCLE** — le document d'ORIGINE, converti une fois en PDF. Affichable
   immédiatement : l'utilisateur voit tout le document, en langue source, dès
   la première seconde.
2. **GREFFE** — chaque page traduite est convertie SEULE, et remplace la page
   correspondante du socle. Le document se traduit sous les yeux.

POURQUOI C'EST POSSIBLE MAINTENANT
----------------------------------
Une campagne précédente avait mesuré 11 s par diapositive isolée et conclu que
le page-par-page coûtait 288 s contre 17 s pour le deck entier. La conclusion
était juste, la CAUSE était fausse : ce n'était pas le poids des médias, mais le
PROFIL LibreOffice, reconstruit à chaque appel.

MESURÉ, profil partagé (cf. `engines/office.py`) :

    profil neuf ...................... 6,99 s
    profil réutilisé ................. 2,66 s
    UNE diapositive, profil chaud .... 1,58 s     <- 7x plus rapide

Mesuré aussi, et **faux** : élaguer les médias d'une diapositive isolée
(12,7 Mo -> 0,5 Mo) ne gagne RIEN. LibreOffice ne lit pas les images que rien ne
référence. Ne pas réécrire cette optimisation-là.

LE PRIX, ET CE QUI NOUS EN PROTÈGE
----------------------------------
26 x 1,58 s = 41 s de calcul contre 2,66 s pour le deck entier : quinze fois
plus de CPU par document. Invisible pour un utilisateur, ruineux pour cent.

D'où la COALESCENCE, qui vit dans l'appelant : un seul convertisseur par job,
qui prend à chaque tour TOUTES les pages en attente. Seul, l'utilisateur reçoit
ses pages une par une ; sous charge, la conversion prend du retard, les pages
s'accumulent et partent par lots — le système glisse de lui-même vers le régime
économe, sans seuil à deviner.
"""
from __future__ import annotations

import os
import tempfile
import time
from typing import Callable

import fitz


class ProgressivePreview:
    """Le PDF d'aperçu d'un job, et la façon dont il se remplit.

    L'objet ne connaît ni LibreOffice ni le moteur PPTX : il reçoit deux
    fonctions. C'est ce qui le rend vérifiable sans convertir quoi que ce soit,
    et réutilisable pour un autre format.

    :param extraire: `(chemin_sortie, pages) -> None` — écrit un document ne
        contenant QUE ces pages, traduites.
    :param convertir: `(octets_du_document) -> octets_pdf`.
    """

    def __init__(self, extraire: Callable[[str, set[int]], None],
                 convertir: Callable[[bytes], bytes], extension: str = "pptx"):
        self._extraire = extraire
        self._convertir = convertir
        self._extension = extension
        self._socle: bytes | None = None
        self._pages: dict[int, bytes] = {}

    # ── État ─────────────────────────────────────────────────────────────
    @property
    def pret(self) -> bool:
        """Le socle est-il posé ? Avant lui, il n'y a rien à montrer."""
        return self._socle is not None

    @property
    def pages_traduites(self) -> int:
        return len(self._pages)

    @property
    def liste_pages(self) -> list[int]:
        """Pages greffées, donc montrées traduites dans le dernier assemblage."""
        return sorted(self._pages)

    @property
    def pages_socle(self) -> int:
        """Nombre de pages du document d'origine. 0 tant qu'il n'est pas posé."""
        if self._socle is None:
            return 0
        with fitz.open(stream=self._socle, filetype="pdf") as d:
            return d.page_count

    # ── Construction ─────────────────────────────────────────────────────
    def poser_socle(self, pdf_origine: bytes) -> bytes:
        """Installe le document d'origine comme état initial."""
        self._socle = pdf_origine
        return self.assembler()

    def greffer(self, pages: list[int]) -> bytes:
        """Convertit ces pages et remplace les leurs dans le socle.

        UNE seule conversion pour tout le lot — c'est ce qui fait que le retard
        se paie en débit, jamais en latence par page.

        Lève si le nombre de pages rendues ne correspond pas à ce qui était
        demandé : sans cet appariement certain, on afficherait la traduction
        d'une page en face d'une autre. Mieux vaut ne rien greffer et réessayer
        au tour suivant que mentir sur ce qu'on montre.
        """
        if not pages:
            return self.assembler()
        if self._socle is None:
            raise RuntimeError("greffe demandée avant le socle")

        ordonnees = sorted(set(pages))

        # PREMIÈRE garde : la page demandée existe-t-elle dans le document ?
        #
        # Le comptage seul ne suffit PAS, et le test l'a prouvé : demander une
        # page inexistante produit un document vide, que LibreOffice rend en UNE
        # page blanche. `1 == 1` — la garde de comptage passait, et une page
        # fantôme était enregistrée comme traduite. Compter, c'est vérifier une
        # conséquence ; vérifier l'existence, c'est vérifier la cause.
        hors = [n for n in ordonnees if not (1 <= n <= self.pages_socle)]
        if hors:
            raise ValueError(
                f"page(s) {hors} hors du document ({self.pages_socle} pages)")
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            lot_path = os.path.join(td, f"lot.{self._extension}")
            self._extraire(lot_path, set(ordonnees))
            with open(lot_path, "rb") as f:
                rendu = self._convertir(f.read())

        with fitz.open(stream=rendu, filetype="pdf") as lot:
            # SECONDE garde, en profondeur. Elle couvre le cas où une page
            # EXISTE mais ne produit rien au rendu : le lot serait alors décalé
            # et chaque traduction atterrirait en face de la mauvaise page.
            #
            # HONNÊTETÉ : aucun test ne l'atteint aujourd'hui — la garde
            # d'existence ci-dessus tire la première, et je n'ai pas su
            # fabriquer un document dont une page se rende « à vide ». Elle est
            # conservée parce que le défaut qu'elle empêche est SILENCIEUX (une
            # traduction affichée sous une autre page) et qu'elle ne coûte
            # qu'une comparaison. À supprimer si l'on démontre qu'elle ne peut
            # pas se déclencher.
            if lot.page_count != len(ordonnees):
                raise ValueError(
                    f"{lot.page_count} page(s) rendue(s) pour "
                    f"{len(ordonnees)} demandée(s) : appariement incertain")
            for i, num in enumerate(ordonnees):
                une = fitz.open()
                une.insert_pdf(lot, from_page=i, to_page=i)
                self._pages[num] = une.tobytes()
                une.close()
        return self.assembler()

    def assembler(self) -> bytes:
        """Socle + pages traduites. Quelques millisecondes.

        On repart TOUJOURS du socle plutôt que de muter le PDF précédent : une
        greffe ratée ne peut pas laisser l'aperçu dans un état intermédiaire, et
        l'ordre des pages est vrai par construction plutôt que par récurrence.
        """
        if self._socle is None:
            raise RuntimeError("aucun socle posé")
        with fitz.open(stream=self._socle, filetype="pdf") as sortie:
            for num, page_pdf in sorted(self._pages.items()):
                idx = num - 1
                if not (0 <= idx < sortie.page_count):
                    continue          # page hors du document : on n'invente pas
                with fitz.open(stream=page_pdf, filetype="pdf") as une:
                    sortie.delete_page(idx)
                    sortie.insert_pdf(une, from_page=0, to_page=0, start_at=idx)
            return sortie.tobytes()


class ApercuParPage:
    """L'aperçu d'un deck SANS socle : chaque page rendue vit seule sur disque.

    POURQUOI PLUS DE SOCLE (docs/etude-apercu-par-page.md) : convertir le deck
    ENTIER (TSA, 75 diapositives) a coûté 107 s et 1 494 Mo à LibreOffice, ce
    qui tuait le serveur à 1 Go. Une diapositive seule : 200 à 300 Mo ; cinq
    d'un coup : 642 Mo. On convertit donc `par_conversion` diapositives au plus
    à la fois, et rien d'autre.

    Une page rendue est écrite dans `dossier/{n}.pdf` et n'occupe plus la
    mémoire. Une page pas encore rendue est montrée « en attente » : une page
    blanche au format de la diapositive, pour que le lecteur ne saute pas.

    :param extraire: `(chemin_sortie, pages) -> None`, comme `ProgressivePreview`.
    :param convertir: `(octets_du_document) -> octets_pdf`.
    :param total: nombre de pages du document.
    :param taille: (largeur, hauteur) d'une page en points.
    """

    def __init__(self, extraire: Callable[[str, set[int]], None],
                 convertir: Callable[[bytes], bytes], dossier: str, total: int,
                 taille: tuple[float, float], extension: str = "pptx",
                 par_conversion: int = 1):
        self._extraire = extraire
        self._convertir = convertir
        self._dossier = dossier
        self._total = total
        self._taille = taille
        self._extension = extension
        self._par_conversion = max(1, par_conversion)
        self._pretes: set[int] = set()

    def chemin_page(self, num: int) -> str:
        return os.path.join(self._dossier, f"{num}.pdf")

    @property
    def liste_pages(self) -> list[int]:
        """Pages rendues, donc montrées traduites dans le dernier assemblage."""
        return sorted(self._pretes)

    @property
    def pages_traduites(self) -> int:
        return len(self._pretes)

    def reprendre(self, pages: list[int]) -> list[int]:
        """Pages déjà rendues sur disque (job relancé) : elles ne sont pas
        reconverties. Renvoie celles qui manquent encore."""
        manquent = []
        for n in pages:
            if os.path.isfile(self.chemin_page(n)):
                self._pretes.add(n)
            else:
                manquent.append(n)
        return manquent

    def greffer(self, pages: list[int]) -> bytes:
        """Rend ces pages, `par_conversion` au plus par appel à LibreOffice,
        les range sur disque, puis renvoie l'aperçu assemblé.

        Mêmes gardes que `ProgressivePreview.greffer` : une page hors du
        document, ou un rendu dont le nombre de pages ne correspond pas, lève
        AVANT d'écrire quoi que ce soit pour ce lot.
        """
        ordonnees = sorted(set(pages))
        hors = [n for n in ordonnees if not (1 <= n <= self._total)]
        if hors:
            raise ValueError(
                f"page(s) {hors} hors du document ({self._total} pages)")
        os.makedirs(self._dossier, exist_ok=True)
        for i in range(0, len(ordonnees), self._par_conversion):
            lot_nums = ordonnees[i:i + self._par_conversion]
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
                lot_path = os.path.join(td, f"lot.{self._extension}")
                self._extraire(lot_path, set(lot_nums))
                with open(lot_path, "rb") as f:
                    rendu = self._convertir(f.read())
            with fitz.open(stream=rendu, filetype="pdf") as lot:
                if lot.page_count != len(lot_nums):
                    raise ValueError(
                        f"{lot.page_count} page(s) rendue(s) pour "
                        f"{len(lot_nums)} demandée(s) : appariement incertain")
                for j, num in enumerate(lot_nums):
                    une = fitz.open()
                    une.insert_pdf(lot, from_page=j, to_page=j)
                    ecrire_atomiquement(self.chemin_page(num), une.tobytes())
                    une.close()
                    self._pretes.add(num)
        return self.assembler()

    def assembler(self) -> bytes:
        """Pages rendues + pages « en attente », dans l'ordre du document.

        Lit chaque page depuis le disque : la mémoire ne tient que le PDF de
        sortie (environ 0,2 Mo par page), jamais le deck converti.
        """
        largeur, hauteur = self._taille
        with fitz.open() as sortie:
            for num in range(1, self._total + 1):
                chemin = self.chemin_page(num)
                if num in self._pretes and os.path.isfile(chemin):
                    with fitz.open(chemin) as une:
                        sortie.insert_pdf(une, from_page=0, to_page=0)
                else:
                    sortie.new_page(width=largeur, height=hauteur)
            return sortie.tobytes()


def taille_diapositive(chemin_pptx: str) -> tuple[float, float]:
    """Format des diapositives d'un PPTX, en points (16:9 par défaut)."""
    import re
    import zipfile
    try:
        with zipfile.ZipFile(chemin_pptx) as z:
            xml = z.read("ppt/presentation.xml").decode("utf-8", "replace")
        m = re.search(r'<p:sldSz[^>]*\bcx="(\d+)"[^>]*\bcy="(\d+)"', xml)
        if m:
            return int(m.group(1)) / 12700, int(m.group(2)) / 12700
    except (OSError, KeyError, zipfile.BadZipFile):
        pass
    return 960.0, 540.0


def ecrire_atomiquement(chemin: str, donnees: bytes) -> None:
    """Écrit sans jamais exposer un fichier à moitié écrit.

    Un lecteur (`/partial`) peut arriver à tout instant : sans le passage par un
    temporaire et le renommage, il lirait un PDF tronqué et le signalerait comme
    corrompu.
    """
    tmp = chemin + ".tmp"
    try:
        with open(tmp, "wb") as f:
            f.write(donnees)
        # Windows : remplacement refusé tant qu'un lecteur ou l'antivirus tient
        # le fichier. L'aperçu se rattrapera à l'écriture suivante ; il ne doit
        # pas faire échouer la traduction.
        for _ in range(50):
            try:
                os.replace(tmp, chemin)
                return
            except PermissionError:
                time.sleep(0.1)
    except BaseException:
        # Disque plein : le temporaire à moitié écrit ne doit pas rester.
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
