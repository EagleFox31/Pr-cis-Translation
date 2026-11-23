"""Redessin des aperçus des objets incorporés (étape 6.11.4).

Un objet incorporé (classeur dans une diapositive, document dans un classeur…)
s'affiche par une IMAGE figée à sa création : traduire l'objet ne change rien à
ce qu'on voit tant que cette image n'est pas refaite. Ce module la refait
depuis l'objet TRADUIT, par LibreOffice, au mieux :

* classeur : la zone visible de l'objet (`oleSize`) de la feuille active,
  ajustée sur une page, format % explicite (méthode CFAO, étude § 4) ;
* document, présentation : la première page / diapositive, rognée au contenu,
  gardée seulement si ses proportions restent à 10 % de l'aperçu d'origine
  (décision D3) — sinon l'aperçu d'origine reste ;
* tous les objets d'un même appel passent en UNE invocation de LibreOffice
  (démarrage amorti), sous `preview_lock`, avec un nouvel essai si un profil
  neuf s'est arrêté sans convertir ;
* cache par empreinte du contenu rendu : la traduction progressive puis la
  passe finale redemandent le même aperçu, il n'est calculé qu'une fois.

Rien ici ne lève : un objet qu'on ne sait pas redessiner garde son aperçu.
"""
from __future__ import annotations

import hashlib
import io
import logging
import os
import subprocess
import tempfile
import threading
import zipfile
from collections import OrderedDict
from dataclasses import dataclass

from lxml import etree

from engines import office

logger = logging.getLogger(__name__)

# Change dès que le rendu change : invalide le cache.
VERSION_RENDU = "1"
# Écart de proportions toléré entre la page rendue et l'aperçu d'origine (D3).
ECART_RATIO_MAX = 0.10
DELAI = 120
_CACHE_MAX = 64

_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PARSER = etree.XMLParser(resolve_entities=False, no_network=True)


@dataclass
class Demande:
    """Un aperçu à redessiner : `cle` libre (l'appelant s'y retrouve)."""
    cle: str
    type: str               # "xlsx" | "docx" | "pptx"
    octets: bytes           # l'objet traduit
    ratio: float | None     # largeur / hauteur du cadre d'affichage


_cache: OrderedDict[str, bytes | None] = OrderedDict()
_cache_garde = threading.Lock()


def vider_cache() -> None:
    with _cache_garde:
        _cache.clear()


# --------------------------------------------------------------------------- #
# Copies de rendu
# --------------------------------------------------------------------------- #

def _zip_stable(parties: dict[str, bytes]) -> bytes:
    """Zip à date fixe : un même contenu donne les mêmes octets."""
    sortie = io.BytesIO()
    with zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED) as z:
        for nom, octets in parties.items():
            info = zipfile.ZipInfo(nom, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, octets)
    return sortie.getvalue()


def _parties(octets: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(octets)) as z:
        return {i.filename: z.read(i) for i in z.infolist() if not i.is_dir()}


def forcer_une_page(xml: bytes) -> bytes:
    """`fitToPage` + A4 paysage sur une feuille, éléments à leur place.

    `sheetPr` se place en tête de feuille ; `pageSetup` après le contenu, avant
    les éléments qui le suivent dans le schéma : on le remplace en place s'il
    existe, sinon on l'insère avant le premier de ces éléments."""
    racine = etree.fromstring(xml, _PARSER)
    pr = racine.find(f"{{{_S}}}sheetPr")
    if pr is None:
        pr = etree.Element(f"{{{_S}}}sheetPr")
        racine.insert(0, pr)
    sp = pr.find(f"{{{_S}}}pageSetUpPr")
    if sp is None:
        sp = etree.SubElement(pr, f"{{{_S}}}pageSetUpPr")
    sp.set("fitToPage", "1")
    ps = racine.find(f"{{{_S}}}pageSetup")
    if ps is None:
        ps = etree.Element(f"{{{_S}}}pageSetup")
        apres = ("headerFooter", "rowBreaks", "colBreaks", "customProperties",
                 "cellWatches", "ignoredErrors", "smartTags", "drawing",
                 "legacyDrawing", "legacyDrawingHF", "drawingHF", "picture",
                 "oleObjects", "controls", "webPublishItems", "tableParts", "extLst")
        suivant = next((e for e in racine
                        if isinstance(e.tag, str) and etree.QName(e).localname in apres), None)
        if suivant is None:
            racine.append(ps)
        else:
            suivant.addprevious(ps)
    for attribut in list(ps.attrib):
        if attribut.startswith(f"{{{_R}}}"):
            del ps.attrib[attribut]          # réglages imprimante : partie absente du rendu
    ps.set("paperSize", "9")
    ps.set("orientation", "landscape")
    ps.set("fitToWidth", "1")
    ps.set("fitToHeight", "1")
    return etree.tostring(racine, xml_declaration=True, encoding="UTF-8", standalone=True)


def _absolu(ref: str) -> str:
    import re
    return re.sub(r"\$?([A-Za-z]+)\$?(\d+)", lambda m: f"${m.group(1).upper()}${m.group(2)}", ref)


def _cible_feuille(parties: dict[str, bytes], rid: str) -> str | None:
    rels = parties.get("xl/_rels/workbook.xml.rels")
    if rels is None:
        return None
    for e in etree.fromstring(rels, _PARSER):
        if e.get("Id") == rid:
            cible = (e.get("Target") or "").lstrip("/")
            return cible if cible.startswith("xl/") else "xl/" + cible
    return None


def copie_de_rendu_classeur(octets: bytes) -> bytes:
    """Copie à imprimer d'un classeur : feuille active seule, zone visible de
    l'objet (`oleSize`) en zone d'impression, une page, format % explicite.
    Le classeur livré n'est pas touché."""
    parties = _parties(octets)
    classeur = etree.fromstring(parties["xl/workbook.xml"], _PARSER)
    feuilles = classeur.find(f"{{{_S}}}sheets")
    liste = [] if feuilles is None else list(feuilles.iterfind(f"{{{_S}}}sheet"))
    vue = classeur.find(f"{{{_S}}}bookViews/{{{_S}}}workbookView")
    try:
        active = int(vue.get("activeTab", "0")) if vue is not None else 0
    except ValueError:
        active = 0
    if not 0 <= active < len(liste):
        active = 0
    # L'objet n'affiche que la feuille active : les autres ne s'impriment pas.
    for i, f in enumerate(liste):
        if i != active:
            f.set("state", "hidden")
    chemin = _cible_feuille(parties, liste[active].get(f"{{{_R}}}id") or "") if liste else None
    # Feuille graphique : ni cellules ni zone d'impression, le graphique
    # remplit déjà la page.
    graphique = (chemin or "").startswith("xl/chartsheets/")
    taille = classeur.find(f"{{{_S}}}oleSize")
    if liste and not graphique and taille is not None and taille.get("ref"):
        a, _, b = taille.get("ref").partition(":")
        nom = liste[active].get("name", "").replace("'", "''")
        noms = classeur.find(f"{{{_S}}}definedNames")
        if noms is None:
            noms = etree.Element(f"{{{_S}}}definedNames")
            feuilles.addnext(noms)
        for d in list(noms):
            if d.get("name") == "_xlnm.Print_Area" and d.get("localSheetId") == str(active):
                noms.remove(d)
        zone = etree.SubElement(noms, f"{{{_S}}}definedName")
        zone.set("name", "_xlnm.Print_Area")
        zone.set("localSheetId", str(active))
        zone.text = f"'{nom}'!{_absolu(a)}:{_absolu(b or a)}"
    parties["xl/workbook.xml"] = etree.tostring(classeur, xml_declaration=True,
                                                encoding="UTF-8", standalone=True)
    if not graphique and chemin in parties:
        parties[chemin] = forcer_une_page(parties[chemin])
    if "xl/styles.xml" in parties:
        parties["xl/styles.xml"] = _pourcentages_explicites(parties["xl/styles.xml"])
    return _zip_stable(parties)


def _pourcentages_explicites(xml: bytes) -> bytes:
    """Les formats % intégrés (9, 10) suivent la langue de LibreOffice
    (« 85 % ») ; Excel écrit « 85% ». Un format explicite s'affiche pareil."""
    racine = etree.fromstring(xml, _PARSER)
    # Identifiants libres : les formats propres au classeur partent de 164.
    libre = 1 + max([163] + [int(f.get("numFmtId")) for f in racine.iter(f"{{{_S}}}numFmt")
                             if (f.get("numFmtId") or "").isdigit()])
    remplace = {"9": (str(libre), "0%"), "10": (str(libre + 1), "0.00%")}
    vus = set()
    for e in racine.iter(f"{{{_S}}}xf"):
        n = e.get("numFmtId")
        if n in remplace:
            e.set("numFmtId", remplace[n][0])
            vus.add(n)
    if not vus:
        return xml
    formats = racine.find(f"{{{_S}}}numFmts")
    if formats is None:
        formats = etree.Element(f"{{{_S}}}numFmts")
        racine.insert(0, formats)
    for n in sorted(vus):
        f = etree.SubElement(formats, f"{{{_S}}}numFmt")
        f.set("numFmtId", remplace[n][0])
        f.set("formatCode", remplace[n][1])
    formats.set("count", str(len(formats)))
    return etree.tostring(racine, xml_declaration=True, encoding="UTF-8", standalone=True)


def copie_de_rendu(type_: str, octets: bytes) -> bytes:
    """Copie à convertir, stable octet pour octet (sert d'empreinte)."""
    if type_ == "xlsx":
        return copie_de_rendu_classeur(octets)
    return _zip_stable(_parties(octets))


# --------------------------------------------------------------------------- #
# PDF -> PNG
# --------------------------------------------------------------------------- #

def completer_au_ratio(im, ratio_cible: float):
    """Complète l'image de vide TRANSPARENT, centrée, jusqu'à `ratio_cible`.
    Jamais rognée : l'application étire l'image sur tout le cadre, une image
    aux mauvaises proportions y apparaîtrait déformée."""
    from PIL import Image
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    actuel = im.width / max(1, im.height)
    if abs(actuel - ratio_cible) < 0.01:
        return im
    if actuel < ratio_cible:
        larg, haut = int(round(im.height * ratio_cible)), im.height
    else:
        larg, haut = im.width, int(round(im.width / ratio_cible))
    fond = Image.new("RGBA", (max(larg, im.width), max(haut, im.height)), (0, 0, 0, 0))
    fond.paste(im, ((fond.width - im.width) // 2, (fond.height - im.height) // 2))
    return fond


def rendre_png(pdf: bytes, ratio_cible: float | None = None,
               premiere_seulement: bool = False, dpi: int = 150,
               marge: int = 8):
    """PNG rogné à ce qui est PEINT (alpha > 0), transparent ailleurs.

    LibreOffice ne peint pas de fond (mesuré) : le rendu RGBA direct laisse
    voir ce que l'utilisateur a posé sous le cadre, comme l'EMF d'origine.
    Pages empilées verticalement (classeur), ou la première seule.
    Rend (png, ratio du contenu avant complément) ou None."""
    try:
        import fitz
        import numpy as np
        from PIL import Image
        doc = fitz.open(stream=pdf, filetype="pdf")
        try:
            morceaux = []
            for i, page in enumerate(doc):
                if premiere_seulement and i > 0:
                    break
                pix = page.get_pixmap(dpi=dpi, alpha=True)
                im = Image.frombytes("RGBA", (pix.width, pix.height), pix.samples)
                masque = np.asarray(im.getchannel("A")) > 0
                if not masque.any():
                    continue
                ys, xs = np.where(masque)
                morceaux.append(im.crop((max(0, int(xs.min()) - marge),
                                         max(0, int(ys.min()) - marge),
                                         min(im.width, int(xs.max()) + marge + 1),
                                         min(im.height, int(ys.max()) + marge + 1))))
        finally:
            doc.close()
        if not morceaux:
            return None
        if len(morceaux) == 1:
            out = morceaux[0]
        else:
            out = Image.new("RGBA", (max(m.width for m in morceaux),
                                     sum(m.height for m in morceaux)), (0, 0, 0, 0))
            y = 0
            for m in morceaux:
                out.paste(m, (0, y))
                y += m.height
        ratio_contenu = out.width / max(1, out.height)
        if ratio_cible and ratio_cible > 0:
            out = completer_au_ratio(out, ratio_cible)
        buf = io.BytesIO()
        out.save(buf, "PNG", optimize=True)
        return buf.getvalue(), ratio_contenu
    except Exception as exc:  # noqa: BLE001
        logger.warning("Rendu PNG impossible : %s", exc)
        return None


# --------------------------------------------------------------------------- #
# Redessin groupé
# --------------------------------------------------------------------------- #

def _convertir_tous(fichiers: list[str], dossier: str) -> None:
    """UN appel LibreOffice pour tous les fichiers ; un nouvel essai si rien
    n'est sorti (profil neuf : LibreOffice le crée puis s'arrête)."""
    cmd = [office.SOFFICE_PATH, "--headless", "--norestore", "--nolockcheck",
           office.profil_argument(), "--convert-to", "pdf", "--outdir", dossier, *fichiers]
    for _essai in range(2):
        with office.preview_lock:
            subprocess.run(cmd, capture_output=True, timeout=DELAI * len(fichiers))
        if any(os.path.exists(_pdf_de(f, dossier)) for f in fichiers):
            return


def _pdf_de(fichier: str, dossier: str) -> str:
    return os.path.join(dossier, os.path.splitext(os.path.basename(fichier))[0] + ".pdf")


def _accepte(type_: str, ratio_contenu: float, ratio: float | None) -> bool:
    """D3 : une page de document ou une diapositive n'est gardée que si ses
    proportions restent proches de l'aperçu d'origine."""
    if type_ == "xlsx" or not ratio:
        return True
    return abs(ratio_contenu / ratio - 1) <= ECART_RATIO_MAX


def redessiner(demandes: list[Demande]) -> dict[str, bytes]:
    """{cle: png} des aperçus redessinés ; une demande absente du résultat
    garde son aperçu d'origine."""
    if not demandes or not office.SOFFICE_PATH:
        return {}
    resultats: dict[str, bytes] = {}
    a_rendre: dict[str, tuple[bytes, list[Demande]]] = {}
    for d in demandes:
        try:
            copie = copie_de_rendu(d.type, d.octets)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Copie de rendu impossible (%s) : %s", d.cle, exc)
            continue
        ratio = round(d.ratio, 3) if d.ratio else None
        empreinte = hashlib.sha1(copie + f"|{d.type}|{VERSION_RENDU}|{ratio}".encode()).hexdigest()
        with _cache_garde:
            if empreinte in _cache:
                _cache.move_to_end(empreinte)
                png = _cache[empreinte]
                if png:
                    resultats[d.cle] = png
                continue
        a_rendre.setdefault(empreinte, (copie, []))[1].append(d)
    if not a_rendre:
        return resultats
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as dossier:
        fichiers = {}
        for i, (empreinte, (copie, ds)) in enumerate(a_rendre.items()):
            chemin = os.path.join(dossier, f"objet{i}.{ds[0].type}")
            with open(chemin, "wb") as f:
                f.write(copie)
            fichiers[empreinte] = chemin
        try:
            _convertir_tous(list(fichiers.values()), dossier)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redessin des aperçus impossible : %s", exc)
            return resultats
        for empreinte, chemin in fichiers.items():
            d = a_rendre[empreinte][1][0]
            png = None
            pdf = _pdf_de(chemin, dossier)
            if os.path.exists(pdf):
                with open(pdf, "rb") as f:
                    rendu = rendre_png(f.read(), d.ratio, premiere_seulement=d.type != "xlsx")
                if rendu and _accepte(d.type, rendu[1], d.ratio):
                    png = rendu[0]
                # Un rendu, ou un refus D3, est mis en cache : même verdict demain.
                # Un échec de rendu (PDF vide ou illisible) sera retenté.
                if rendu:
                    with _cache_garde:
                        _cache[empreinte] = png
                        while len(_cache) > _CACHE_MAX:
                            _cache.popitem(last=False)
            if png:
                for d in a_rendre[empreinte][1]:
                    resultats[d.cle] = png
    return resultats
