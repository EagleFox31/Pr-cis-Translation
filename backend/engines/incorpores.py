"""Objets incorporés des documents Office : repérage (6.11.1), extraction et
réécriture (6.11.2).

Un objet incorporé (classeur Excel dans une diapo, lettre Word dans un
classeur…) est un fichier rangé dans le paquet du document, affiché par une
IMAGE D'APERÇU que dessine Office. Traduire le document sans traduire l'objet
ni refaire son aperçu laisse un tableau en langue d'origine au milieu d'une
page traduite.

Ce module, commun aux trois moteurs (DOCX, XLSX, PPTX), REPÈRE les objets
(il lit le paquet et décrit chaque objet, sans rien modifier), puis sait
EXTRAIRE le fichier traduisible et le RÉÉCRIRE dans son enveloppe d'origine.
La traduction et le redessin (étapes suivantes) s'appuient sur ces briques. Voir `docs/etude-objets-incorpores.md`.

Un objet se reconnaît toujours de la même façon, quel que soit le conteneur :
son type de relation (`package` pour un fichier OOXML, `oleObject` pour un
`.bin` OLE2), son progId et l'extension du fichier. Ce qui change, c'est
l'élément XML qui l'affiche :
  - PPTX : `p:graphicFrame` → `p:oleObj` (cadre `p:xfrm/a:ext`) ;
  - DOCX : `w:object` → `o:OLEObject` + `v:shape` (style `width/height`) ;
  - XLSX : `oleObjects/oleObject` (+ `objectPr` et forme VML `_x0000_s<id>`).

L'aperçu affiché est souvent celui de la branche VML et non celui du blip
DrawingML : on relève donc TOUTES les relations du paquet qui pointent vers
l'image d'aperçu, pour pouvoir les rebrancher toutes plus tard.

Le paquet n'est pas fiable (fichier client) : on ne lit que les parties XML
utiles, on plafonne le nombre d'entrées et la taille des parties lues, et un
XML illisible fait ignorer la partie, jamais échouer le repérage.
"""
from __future__ import annotations

import contextvars
import copy
import hashlib
import io
import json
import logging
import math
import os
import threading
import posixpath
import re
import shutil
import struct
import tempfile
import uuid
import zipfile
import zlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import olefile
from lxml import etree

NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "v": "urn:schemas-microsoft-com:vml",
    "o": "urn:schemas-microsoft-com:office:office",
    "x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
}
_R_ID = "{%s}id" % NS["r"]
_R_EMBED = "{%s}embed" % NS["r"]
_O_RELID = "{%s}relid" % NS["o"]

# Ce qu'une archive abîmée peut lever à l'ouverture comme à la décompression.
_ERREURS_ZIP = (zipfile.BadZipFile, OSError, ValueError, RuntimeError, zlib.error, EOFError)

# Plafonds : un paquet client peut être une « bombe ». Le repérage ne lit que
# des parties XML ; au-delà de ces bornes, la partie (ou le paquet) est ignorée.
ENTREES_MAX = 10_000
OCTETS_PARTIE_MAX = 32 * 1024 * 1024

EMU_PAR_PT = 12_700
_UNITES_PT = {"pt": 1.0, "in": 72.0, "cm": 72 / 2.54, "mm": 72 / 25.4,
              "px": 0.75, "pc": 12.0, "": 1.0 / EMU_PAR_PT}

# Nature d'objet → ce que Précis sait en faire (étude § 3).
TRAITABLES = {"classeur", "document", "presentation"}
_EXT_NATURE = {
    ".xlsx": "classeur", ".xlsm": "classeur", ".xls": "classeur",
    ".docx": "document", ".docm": "document", ".doc": "document",
    ".pptx": "presentation", ".pptm": "presentation", ".ppt": "presentation",
    ".sldx": "presentation", ".vsdx": "visio", ".vsd": "visio", ".pdf": "pdf",
}
_PROGID_NATURE = (
    ("excel.", "classeur"), ("word.", "document"),
    ("powerpoint.", "presentation"), ("visio.", "visio"),
    ("acroexch.", "pdf"), ("acrobat.", "pdf"), ("equation.", "equation"),
    ("package", "paquet"),
    # Repère invisible d'un complément (think-cell) : pas un contenu, ni à
    # traduire ni à signaler au client. Mesuré : 154 sur un seul modèle réel.
    ("tclayout.", "marqueur"),
)


@dataclass
class ObjetIncorpore:
    """Un objet incorporé tel que le paquet le décrit."""
    conteneur: str                 # "docx" | "xlsx" | "pptx"
    partie: str                    # partie qui l'affiche (ppt/slides/slide1.xml)
    cible: str                     # chemin dans le paquet, ou URL si lié
    prog_id: str
    nature: str                    # classeur | document | presentation | paquet
                                   # | visio | pdf | equation | marqueur | autre
    format: str                    # "ooxml" | "ole2" | "autre"
    icone: bool                    # affiché en icône : aperçu à ne pas redessiner
    lie: bool                      # fichier externe : jamais suivi
    present: bool                  # la cible existe bien dans le paquet
    apercu: str | None = None      # image d'aperçu (ppt/media/image1.emf)
    ratio: float | None = None     # largeur / hauteur du cadre d'affichage
    relations_apercu: list[tuple[str, str]] = field(default_factory=list)
                                   # (fichier .rels, Id) pointant vers l'aperçu
    rid: str | None = None         # Id de la relation de la partie vers la cible
    echec: str | None = None       # posé APRÈS coup : pourquoi un objet a priori
                                   # traitable ne l'a pas été (conversion, erreur…)
    graphique: str | None = None   # classeur caché d'un graphique natif : la
                                   # partie du graphique (ppt/charts/chart1.xml)

    @property
    def raison_non_traite(self) -> str | None:
        """Pourquoi l'objet ne sera pas traduit, ou None s'il le sera."""
        if self.echec:
            return self.echec
        if self.lie:
            return "lie"
        if not self.present:
            return "absent"
        if self.nature in TRAITABLES:
            return None
        if self.nature == "paquet":
            return None if self.format == "ooxml" else "paquet"
        return self.nature


# --------------------------------------------------------------------------- #
# Lecture prudente du paquet
# --------------------------------------------------------------------------- #

class _Paquet:
    def __init__(self, zf: zipfile.ZipFile):
        self.zf = zf
        self.noms = set(zf.namelist())
        self._xml: dict[str, etree._Element | None] = {}

    def xml(self, nom: str):
        if nom in self._xml:
            return self._xml[nom]
        racine = None
        try:
            info = self.zf.getinfo(nom)
            if info.file_size <= OCTETS_PARTIE_MAX:
                parser = etree.XMLParser(resolve_entities=False, no_network=True,
                                         huge_tree=False)
                racine = etree.fromstring(self.zf.read(nom), parser)
        except (KeyError, etree.XMLSyntaxError, zipfile.BadZipFile, ValueError, zlib.error, EOFError,
                OSError, RuntimeError):
            racine = None
        self._xml[nom] = racine
        return racine

    @staticmethod
    def rels_de(partie: str) -> str:
        d, b = posixpath.split(partie)
        return posixpath.join(d, "_rels", b + ".rels")

    def relations(self, partie: str) -> dict[str, tuple[str, str, bool]]:
        """{Id: (cible résolue, Type, externe)} des relations d'une partie."""
        racine = self.xml(self.rels_de(partie))
        if racine is None:
            return {}
        base = posixpath.dirname(partie)
        out = {}
        for rel in racine:
            rid, cible = rel.get("Id"), rel.get("Target") or ""
            if not rid:
                continue
            externe = (rel.get("TargetMode") or "").lower() == "external"
            out[rid] = (cible if externe else _resoudre(base, cible),
                        rel.get("Type") or "", externe)
        return out


def _resoudre(base: str, cible: str) -> str:
    if cible.startswith("/"):
        return cible.lstrip("/")
    return posixpath.normpath(posixpath.join(base, cible))


def _nature(prog_id: str, cible: str) -> str:
    pid = prog_id.lower()
    if pid.startswith("tclayout."):
        return "marqueur"
    ext = Path(cible).suffix.lower()
    if ext in _EXT_NATURE:
        return _EXT_NATURE[ext]
    for prefixe, nature in _PROGID_NATURE:
        if pid.startswith(prefixe):
            return nature
    return "autre"


def _format(cible: str) -> str:
    ext = Path(cible).suffix.lower()
    if ext in (".xlsx", ".xlsm", ".docx", ".docm", ".pptx", ".pptm", ".sldx"):
        return "ooxml"
    if ext == ".bin":
        return "ole2"
    return "autre"


def _longueur_pt(val: str) -> float | None:
    m = re.fullmatch(r"\s*(-?[\d.]+)\s*([a-z]*)\s*", val or "")
    if not m or m.group(2) not in _UNITES_PT:
        return None
    try:
        return float(m.group(1)) * _UNITES_PT[m.group(2)]
    except ValueError:
        return None


def _ratio_style(style: str | None) -> float | None:
    """Ratio d'un style VML `width:451.5pt;height:132pt`."""
    props = {}
    for decl in (style or "").split(";"):
        k, _, v = decl.partition(":")
        props[k.strip().lower()] = v.strip()
    w = _longueur_pt(props.get("width", ""))
    h = _longueur_pt(props.get("height", ""))
    return _ratio(w, h)


def _ratio(w, h) -> float | None:
    try:
        w, h = float(w), float(h)
    except (TypeError, ValueError, OverflowError):
        return None
    ratio = w / h if w > 0 and h > 0 else None
    return ratio if ratio and math.isfinite(ratio) else None


def _forme_vml(paquet: _Paquet, partie: str, spid: str):
    """(aperçu, forme v:shape) de la forme VML `spid` liée à `partie`."""
    if not spid:
        return None, None
    for cible, typ, externe in paquet.relations(partie).values():
        if externe or not typ.endswith("/vmlDrawing"):
            continue
        racine = paquet.xml(cible)
        if racine is None:
            continue
        for forme in racine.iter("{%s}shape" % NS["v"]):
            if forme.get("id") != spid and forme.get("{%s}spid" % NS["o"]) != spid:
                continue
            img = forme.find("v:imagedata", NS)
            rid = None if img is None else (img.get(_O_RELID) or img.get(_R_ID))
            apercu = paquet.relations(cible).get(rid or "", (None,))[0]
            return apercu, forme
    return None, None


# --------------------------------------------------------------------------- #
# Repérage par conteneur
# --------------------------------------------------------------------------- #

def _objet(conteneur, partie, rels, rid, prog_id, icone, paquet,
           apercu=None, ratio=None, lie_force=False):
    cible, _typ, externe = rels.get(rid or "", ("", "", False))
    lie = externe or lie_force
    return ObjetIncorpore(
        conteneur=conteneur, partie=partie, cible=cible, prog_id=prog_id,
        nature=_nature(prog_id, cible), format="autre" if lie else _format(cible),
        icone=icone, lie=lie, present=(not lie and cible in paquet.noms),
        apercu=apercu, ratio=ratio, rid=rid or None)


def _pptx(paquet: _Paquet) -> list[ObjetIncorpore]:
    objets = []
    parties = sorted(n for n in paquet.noms if re.fullmatch(
        r"ppt/(slides|slideLayouts|slideMasters|notesSlides)/[^/]+\.xml", n))
    for partie in parties:
        racine = paquet.xml(partie)
        if racine is None:
            continue
        rels = paquet.relations(partie)
        for cadre in racine.iter("{%s}graphicFrame" % NS["p"]):
            oles = cadre.findall(".//p:oleObj", NS)
            if not oles:
                continue
            ole = oles[0]
            rid = next((o.get(_R_ID) for o in oles if o.get(_R_ID)), None)
            icone = any(o.get("showAsIcon") in ("1", "true") for o in oles)
            lie = any(o.find("p:link", NS) is not None for o in oles)
            apercu = None
            blip = cadre.find(".//a:blip", NS)
            if blip is not None:
                apercu = rels.get(blip.get(_R_EMBED) or "", (None,))[0]
            if apercu is None:
                spid = next((o.get("spid") for o in oles if o.get("spid")), "")
                apercu, _ = _forme_vml(paquet, partie, spid)
            ext = cadre.find("./p:xfrm/a:ext", NS)
            ratio = None if ext is None else _ratio(ext.get("cx"), ext.get("cy"))
            objets.append(_objet("pptx", partie, rels, rid,
                                 ole.get("progId") or "", icone, paquet,
                                 apercu, ratio, lie_force=lie))
    return objets


def _docx(paquet: _Paquet) -> list[ObjetIncorpore]:
    objets = []
    parties = sorted(n for n in paquet.noms if re.fullmatch(
        r"word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml", n))
    for partie in parties:
        racine = paquet.xml(partie)
        if racine is None:
            continue
        rels = paquet.relations(partie)
        for obj in racine.iter("{%s}object" % NS["w"]):
            ole = obj.find(".//o:OLEObject", NS)
            if ole is None:
                continue
            forme = obj.find(".//v:shape", NS)
            apercu, ratio = None, None
            if forme is not None:
                img = forme.find("v:imagedata", NS)
                if img is not None:
                    apercu = rels.get(img.get(_R_ID) or img.get(_O_RELID) or "",
                                      (None,))[0]
                ratio = _ratio_style(forme.get("style"))
            if ratio is None:
                ratio = _ratio(obj.get("{%s}dxaOrig" % NS["w"]),
                               obj.get("{%s}dyaOrig" % NS["w"]))
            objets.append(_objet(
                "docx", partie, rels, ole.get(_R_ID), ole.get("ProgID") or "",
                (ole.get("DrawAspect") or "").lower() == "icon", paquet,
                apercu, ratio, lie_force=(ole.get("Type") or "").lower() == "link"))
    return objets


# Tailles par défaut d'Excel (Calibri 11) : colonne 8,43 caractères = 64 px,
# ligne 15 pt. Sert seulement quand la forme VML ne donne pas le cadre.
_PX_EMU = 9525
_COLONNES_MAX, _LIGNES_MAX = 16_384, 1_048_576     # d'une feuille Excel
_ANCRE_MAX = 10 ** 15


def _ratio_ancre(feuille, ancre) -> float | None:
    """Ratio du cadre d'après `anchor/from` et `anchor/to` de la feuille."""
    def marque(nom):
        m = ancre.find("x:%s" % nom, NS)
        if m is None:
            return None
        try:
            valeurs = tuple(int(m.findtext("xdr:%s" % k, namespaces=NS))
                            for k in ("col", "colOff", "row", "rowOff"))
        except (TypeError, ValueError):
            return None
        # Un entier démesuré ne se convertit pas en flottant : fichier forgé.
        return valeurs if max(map(abs, valeurs)) <= _ANCRE_MAX else None
    de, a = marque("from"), marque("to")
    if not de or not a:
        return None
    fmt = feuille.find("x:sheetFormatPr", NS)
    def flt(v, defaut):
        try:
            valeur = float(v)
        except (TypeError, ValueError):
            return defaut
        return valeur if math.isfinite(valeur) else defaut
    larg_def = flt(None if fmt is None else fmt.get("defaultColWidth"), 8.43)
    haut_def = flt(None if fmt is None else fmt.get("defaultRowHeight"), 15.0)
    larg = {}
    reste = _COLONNES_MAX
    for c in feuille.iterfind("x:cols/x:col", NS):
        lo, hi = int(flt(c.get("min"), 0)), int(flt(c.get("max"), 0))
        n = max(0, min(hi - lo + 1, reste))
        for i in range(lo, lo + n):
            larg[i - 1] = flt(c.get("width"), larg_def)
        reste -= n
        if not reste:
            break
    haut = {}
    for row in feuille.iterfind("x:sheetData/x:row", NS):
        if row.get("ht"):
            haut[int(flt(row.get("r"), 0)) - 1] = flt(row.get("ht"), haut_def)
    def col_emu(i):
        return (larg.get(i, larg_def) * 7 + 5) * _PX_EMU
    def row_emu(i):
        return haut.get(i, haut_def) * EMU_PAR_PT
    w = sum(col_emu(i) for i in range(de[0], min(a[0], de[0] + _COLONNES_MAX))) - de[1] + a[1]
    h = sum(row_emu(i) for i in range(de[2], min(a[2], de[2] + _LIGNES_MAX))) - de[3] + a[3]
    return _ratio(w, h)


def _xlsx(paquet: _Paquet) -> list[ObjetIncorpore]:
    objets = []
    parties = sorted(n for n in paquet.noms
                     if re.fullmatch(r"xl/worksheets/[^/]+\.xml", n))
    for partie in parties:
        racine = paquet.xml(partie)
        if racine is None:
            continue
        rels = paquet.relations(partie)
        for ole in racine.iterfind(".//x:oleObjects//x:oleObject", NS):
            rid = ole.get(_R_ID)
            spid = "_x0000_s%s" % ole.get("shapeId") if ole.get("shapeId") else ""
            apercu_vml, forme = _forme_vml(paquet, partie, spid)
            apercu, ratio = None, None
            pr = ole.find("x:objectPr", NS)
            if pr is not None and pr.get(_R_ID):
                apercu = rels.get(pr.get(_R_ID), (None,))[0]
            apercu = apercu or apercu_vml
            if forme is not None:
                ratio = _ratio_style(forme.get("style"))
            if ratio is None and pr is not None:
                ancre = pr.find("x:anchor", NS)
                if ancre is not None:
                    ratio = _ratio_ancre(racine, ancre)
            lie = bool(ole.get("link")) and not rid
            objets.append(_objet(
                "xlsx", partie, rels, rid, ole.get("progId") or "",
                (ole.get("dvAspect") or "").upper() == "DVASPECT_ICON", paquet,
                apercu, ratio, lie_force=lie))
    return objets


_PARTIES_AFFICHAGE = {
    "pptx": r"ppt/(slides|slideLayouts|slideMasters|notesSlides)/[^/]+\.xml",
    "docx": r"word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml",
}


def _classeur_du_graphique(paquet: _Paquet, graphique: str) -> str | None:
    """Classeur OOXML incorporé qui porte les données d'un graphique, ou None
    (classeur lié, binaire 97-2003, absent)."""
    rels = paquet.relations(graphique)
    racine = paquet.xml(graphique)
    donnees = None if racine is None else racine.find("c:externalData", NS)
    rid = None if donnees is None else donnees.get(_R_ID)
    if rid not in rels:
        rid = next((k for k, (_c, t, _e) in rels.items() if t.endswith("/package")), None)
    if rid is None:
        return None
    cible, _typ, externe = rels[rid]
    if externe or _format(cible) != "ooxml" or cible not in paquet.noms:
        return None
    return cible


def a_classeur_interne(chemin_graphique) -> bool:
    """Le graphique décompressé `chemin_graphique` a-t-il son classeur caché
    dans le paquet ? Ses caches `c:strRef` sont alors réalignés sur le classeur
    traduit : le moteur du conteneur ne les envoie pas en traduction (ni
    facturés, ni traduits deux fois). Une cible absolue part de la racine."""
    chemin = Path(chemin_graphique)
    rels = chemin.parent / "_rels" / f"{chemin.name}.rels"
    if not rels.exists():
        return False
    racine = next((d for d in chemin.parents if (d / "[Content_Types].xml").exists()),
                  chemin.parent)
    try:
        liens = etree.parse(str(rels)).getroot()
    except etree.XMLSyntaxError:
        return False
    for r in liens:
        cible = r.get("Target") or ""
        if ((r.get("Type") or "").endswith("/package")
                and r.get("TargetMode") != "External"
                and cible.lower().endswith((".xlsx", ".xlsm"))
                and ((racine / cible.lstrip("/")) if cible.startswith("/")
                     else (chemin.parent / cible)).exists()):
            return True
    return False


def sous_strref(noeud) -> bool:
    """Un `c:v` de cache lié au classeur (sous un `c:strRef`)."""
    return any(etree.QName(a).localname == "strRef" for a in noeud.iterancestors())


def _graphiques(paquet: _Paquet, conteneur: str) -> list[ObjetIncorpore]:
    """Classeurs cachés des graphiques natifs (6.11.5). L'objet est rattaché à
    la partie qui AFFICHE le graphique (mêmes préfixes d'ids que les autres
    objets) ; il n'a ni aperçu ni relation propre : seul le XML du graphique
    est réaligné sur le classeur traduit. Un classeur lié n'est pas listé."""
    motif = _PARTIES_AFFICHAGE.get(conteneur)
    if motif is None:
        return []
    objets = []
    for partie in sorted(n for n in paquet.noms if re.fullmatch(motif, n)):
        for graphique, typ, externe in paquet.relations(partie).values():
            if externe or not typ.endswith("/chart"):
                continue
            cible = _classeur_du_graphique(paquet, graphique)
            if cible is None:
                continue
            objets.append(ObjetIncorpore(
                conteneur=conteneur, partie=partie, cible=cible,
                prog_id="Excel.Sheet.12", nature=_nature("", cible), format="ooxml",
                icone=False, lie=False, present=True, graphique=graphique))
    return objets


def _conteneur(noms: set[str]) -> str | None:
    if "ppt/presentation.xml" in noms:
        return "pptx"
    if "word/document.xml" in noms:
        return "docx"
    if "xl/workbook.xml" in noms:
        return "xlsx"
    return None


def _relations_vers(paquet: _Paquet, apercus: set[str]) -> dict[str, list]:
    """{aperçu: [(fichier .rels, Id)]} sur TOUT le paquet (branche VML comprise)."""
    out: dict[str, list] = {a: [] for a in apercus}
    for nom in sorted(paquet.noms):
        if not nom.endswith(".rels"):
            continue
        d = posixpath.dirname(posixpath.dirname(nom))
        partie = posixpath.join(d, posixpath.basename(nom)[:-len(".rels")])
        for rid, (cible, _t, externe) in paquet.relations(partie).items():
            if not externe and cible in out:
                out[cible].append((nom, rid))
    return out


def reperer(source) -> list[ObjetIncorpore]:
    """Liste les objets incorporés d'un DOCX, XLSX ou PPTX.

    `source` : chemin, octets ou fichier ouvert. Ne modifie rien. Un paquet
    illisible, inconnu ou démesuré donne une liste vide (au mieux)."""
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    try:
        with zipfile.ZipFile(source) as zf:
            if len(zf.infolist()) > ENTREES_MAX:
                return []
            paquet = _Paquet(zf)
            conteneur = _conteneur(paquet.noms)
            if conteneur is None:
                return []
            objets = {"pptx": _pptx, "docx": _docx, "xlsx": _xlsx}[conteneur](paquet)
            objets += _graphiques(paquet, conteneur)
            liens = _relations_vers(paquet, {o.apercu for o in objets if o.apercu})
            for o in objets:
                if o.apercu:
                    o.relations_apercu = list(liens.get(o.apercu, []))
            return objets
    except _ERREURS_ZIP:
        return []


def rapport(objets: list[ObjetIncorpore], imbriques: Sequence[dict] = ()) -> dict:
    """Résumé pour le journal et le compte rendu client (D6).

    Un objet affiché à plusieurs endroits n'est signalé qu'une fois ; les
    marqueurs de compléments ne le sont jamais. `non_traites` compte aussi les
    `imbriques` (objets dans un objet), que `total` et `natures` ignorent : ils
    ne se soustraient donc pas de `total - a_traiter`."""
    a_traiter = [o for o in objets if o.raison_non_traite is None]
    non_traites, vus = [], set()
    for o in objets:
        raison = o.raison_non_traite
        nom = posixpath.basename(o.cible) or o.cible
        if raison is None or raison == "marqueur" or (nom, raison) in vus:
            continue
        vus.add((nom, raison))
        non_traites.append({"cible": nom,
                            "partie": o.partie, "nature": o.nature,
                            "raison": raison})
    non_traites.extend(imbriques)
    natures: dict[str, int] = {}
    for o in objets:
        natures[o.nature] = natures.get(o.nature, 0) + 1
    return {"total": len(objets), "a_traiter": len(a_traiter),
            "a_redessiner": sum(1 for o in a_traiter if not o.icone and o.apercu),
            "natures": natures, "non_traites": non_traites}


# --------------------------------------------------------------------------- #
# Extraction et réécriture (étape 6.11.2)
# --------------------------------------------------------------------------- #
#
# Un objet incorporé est rangé de deux façons :
#   - directement en OOXML (`embeddings/Microsoft_Excel_Worksheet.xlsx`) ;
#   - dans une enveloppe OLE2 (`embeddings/oleObject1.bin`), qui contient soit
#     un flux `Package` (le fichier OOXML tel quel), soit un flux
#     `\x01Ole10Native` (le « paquet » d'un fichier glissé : en-tête, nom,
#     octets du fichier), soit un vrai binaire 97-2003 (`Workbook`,
#     `WordDocument`, `PowerPoint Document`).
# On extrait le fichier traduisible et l'on sait le remettre à sa place, dans
# la même enveloppe. Rien n'est exécuté : `olefile` ne lit que la structure.

PROFONDEUR_MAX = 2                       # niveaux d'objets sous le document
OCTETS_OBJET_MAX = 128 * 1024 * 1024     # décompressé, par objet (module images)
OCTETS_DOCUMENT_MAX = 512 * 1024 * 1024  # cumulé par document (à mesurer, 6.11.7)
TAUX_COMPRESSION_MAX = 100               # au-delà : bombe zip
_SEUIL_TAUX = 1024 * 1024                # un petit fichier très compressible est normal

_ANCIENS = (("workbook", "xls"), ("book", "xls"), ("worddocument", "doc"),
            ("powerpoint document", "ppt"))


@dataclass
class Extrait:
    """Fichier tiré d'un objet incorporé, prêt à être traduit."""
    objet: ObjetIncorpore
    type: str            # "xlsx" | "docx" | "pptx" | "xls" | "doc" | "ppt"
    contenu: bytes       # le fichier lui-même (pour un 97-2003 : tout le .bin)
    enveloppe: str       # "ooxml" | "package" | "ole10native" | "ancien"
    niveau: int          # 1 = objet du document, 2 = objet d'un objet
    nom: str | None = None    # nom de fichier d'origine (paquet Ole10Native)
    origine: bytes = b""      # octets de la cible telle qu'incorporée
    _ole10: tuple | None = None   # (en-tête, suite, packager ?) du flux natif


class Budget:
    """Plafond d'octets décompressés pour tous les objets d'un document."""

    def __init__(self, plafond: int = OCTETS_DOCUMENT_MAX):
        self.reste = plafond

    def prendre(self, n: int) -> bool:
        if n > self.reste:
            return False
        self.reste -= n
        return True


def _taux_suspect(decompresse: int, compresse: int) -> bool:
    return decompresse > _SEUIL_TAUX and decompresse > TAUX_COMPRESSION_MAX * max(compresse, 1)


def taille_zip_sure(octets: bytes) -> int | None:
    """Taille décompressée d'un fichier OOXML, ou None s'il faut le refuser :
    illisible, trop d'entrées, trop gros ou trop compressé (bombe zip)."""
    try:
        with zipfile.ZipFile(io.BytesIO(octets)) as zf:
            infos = zf.infolist()
    except _ERREURS_ZIP:
        return None
    total = sum(i.file_size for i in infos)
    if (len(infos) > ENTREES_MAX or total > OCTETS_OBJET_MAX
            or _taux_suspect(total, sum(i.compress_size for i in infos))):
        return None
    return total


def _type_ooxml(octets: bytes) -> str | None:
    try:
        with zipfile.ZipFile(io.BytesIO(octets)) as zf:
            return _conteneur(set(zf.namelist()))
    except _ERREURS_ZIP:
        return None


def _lire_cible(zf: zipfile.ZipFile, cible: str) -> bytes | None:
    try:
        info = zf.getinfo(cible)
    except KeyError:
        return None
    if info.file_size > OCTETS_OBJET_MAX or _taux_suspect(info.file_size, info.compress_size):
        return None
    try:
        return zf.read(info)
    except _ERREURS_ZIP:
        return None


def _ole10_decouper(flux: bytes):
    """`\\x01Ole10Native` → (en-tête, données, suite, packager ?, nom).

    Format « Packager » : taille totale, 0x0002, nom, chemin, 4 octets,
    chemin temporaire (longueur + texte), taille des données, données, puis
    éventuellement les mêmes chaînes en Unicode. Sinon : taille + données."""
    (total,) = struct.unpack_from("<I", flux, 0)
    try:
        if struct.unpack_from("<H", flux, 4)[0] == 2:
            fin_nom = flux.index(b"\0", 6)
            fin_chemin = flux.index(b"\0", fin_nom + 1)
            p = fin_chemin + 1 + 4
            (n,) = struct.unpack_from("<I", flux, p)
            p += 4 + n
            (taille,) = struct.unpack_from("<I", flux, p)
            if p + 4 + taille <= len(flux):
                nom = flux[6:fin_nom].decode("latin-1")
                return (flux[4:p], flux[p + 4:p + 4 + taille],
                        flux[p + 4 + taille:], True, nom)
    except (ValueError, struct.error):
        pass
    taille = min(total, len(flux) - 4)
    return b"", flux[4:4 + taille], flux[4 + taille:], False, None


def _ole10_recoller(flux_origine: bytes, entete: bytes, suite: bytes,
                    packager: bool, ancien: bytes, nouveau: bytes) -> bytes:
    (total,) = struct.unpack_from("<I", flux_origine, 0)
    corps = entete + (struct.pack("<I", len(nouveau)) if packager else b"") + nouveau + suite
    return struct.pack("<I", max(0, total + len(nouveau) - len(ancien))) + corps


def _flux_ole(ole) -> dict[str, list[str]]:
    return {"/".join(p).lower(): p for p in ole.listdir(streams=True, storages=False)}


def _extraire_ole2(origine: bytes):
    """(type, contenu, enveloppe, nom, _ole10) d'un .bin OLE2, ou None."""
    with olefile.OleFileIO(io.BytesIO(origine)) as ole:
        flux = _flux_ole(ole)
        if "package" in flux:
            if ole.get_size(flux["package"]) > OCTETS_OBJET_MAX:
                return None
            contenu = ole.openstream(flux["package"]).read()
            return _type_ooxml(contenu), contenu, "package", None, None
        if "\x01ole10native" in flux:
            if ole.get_size(flux["\x01ole10native"]) > OCTETS_OBJET_MAX:
                return None
            entete, contenu, suite, packager, nom = _ole10_decouper(
                ole.openstream(flux["\x01ole10native"]).read())
            return (_type_ooxml(contenu), contenu, "ole10native", nom,
                    (entete, suite, packager))
        for nom_flux, type_ancien in _ANCIENS:
            if nom_flux in flux:
                return type_ancien, origine, "ancien", None, None
    return None


def extraire(zf: zipfile.ZipFile, objet: ObjetIncorpore, niveau: int = 1,
             budget: Budget | None = None) -> Extrait | None:
    """Fichier traduisible d'un objet, ou None s'il faut le laisser tel quel.

    `niveau` : 1 pour un objet du document, 2 pour un objet d'un objet ;
    au-delà de PROFONDEUR_MAX, rien n'est extrait. Au mieux : un objet lié,
    absent, mal formé, démesuré ou d'un type non pris en charge donne None."""
    if niveau > PROFONDEUR_MAX or objet.lie or not objet.present:
        return None
    if objet.nature not in TRAITABLES and objet.nature != "paquet":
        return None
    try:
        origine = _lire_cible(zf, objet.cible)
        if origine is None:
            return None
        if origine[:8] == olefile.MAGIC:
            trouve = _extraire_ole2(origine)
            if trouve is None:
                return None
            type_, contenu, enveloppe, nom, ole10 = trouve
        else:
            type_, contenu, enveloppe, nom, ole10 = _type_ooxml(origine), origine, "ooxml", None, None
    except Exception:  # noqa: BLE001 — .bin hostile : l'objet reste tel quel
        return None
    if type_ is None:
        return None
    taille = len(contenu) if enveloppe == "ancien" else taille_zip_sure(contenu)
    if taille is None or (budget is not None and not budget.prendre(taille)):
        return None
    return Extrait(objet, type_, contenu, enveloppe, niveau, nom, origine, ole10)


def reecrire(extrait: Extrait, contenu: bytes) -> bytes:
    """Octets de la cible avec `contenu` à la place du fichier extrait, dans
    la même enveloppe. Contenu inchangé : les octets d'origine, à l'identique.

    Un binaire 97-2003 n'est jamais réécrit sur place : converti (D4), il
    remplace l'objet sous forme OOXML (étape 6.11.3)."""
    if contenu == extrait.contenu:
        return extrait.origine
    if extrait.enveloppe == "ooxml":
        return contenu
    if extrait.enveloppe == "ancien":
        raise ValueError("binaire 97-2003 : pas de réécriture sur place")
    with olefile.OleFileIO(io.BytesIO(extrait.origine)) as ole:
        racine = _lire_arbre(ole)
    nom_flux = "package" if extrait.enveloppe == "package" else "\x01ole10native"
    noeud = next(k for k in racine.enfants if k.nom.lower() == nom_flux)
    if extrait.enveloppe == "package":
        noeud.donnees = contenu
    else:
        entete, suite, packager = extrait._ole10
        noeud.donnees = _ole10_recoller(noeud.donnees, entete, suite, packager,
                                        extrait.contenu, contenu)
    return _ecrire_cfb(racine)


def remplacer_parties(paquet: bytes, table: dict[str, bytes],
                      ajouter: bool = False) -> bytes:
    """Paquet réécrit avec les parties de `table` remplacées : même ordre,
    mêmes métadonnées d'entrée. Rien à remplacer : les octets d'origine.

    `ajouter` : les parties de `table` absentes du paquet y sont AJOUTÉES, en fin
    d'archive (objet 97-2003 converti, qui devient une partie nouvelle)."""
    if not table:
        return paquet
    with zipfile.ZipFile(io.BytesIO(paquet)) as source:
        entrees = source.infolist()
        presentes = {e.filename for e in entrees}
        nouvelles = [n for n in table if n not in presentes] if ajouter else []
        if not nouvelles and not any(n in table for n in presentes):
            return paquet
        sortie = io.BytesIO()
        with zipfile.ZipFile(sortie, "w") as cible:
            for e in entrees:
                octets = table[e.filename] if e.filename in table else source.read(e)
                cible.writestr(copy.copy(e), octets)
            for nom in nouvelles:
                cible.writestr(nom, table[nom], zipfile.ZIP_DEFLATED)
    return sortie.getvalue()


# --------------------------------------------------------------------------- #
# Traduction des objets, récursive (étape 6.11.3b)
# --------------------------------------------------------------------------- #
#
# Chaque objet extrait est traduit par le moteur de SON format (xlsx, docx,
# pptx), qui relève à son tour ses propres objets : un Excel dans un Word dans
# un PowerPoint est traduit jusqu'à PROFONDEUR_MAX. Un binaire 97-2003 est
# d'abord converti par LibreOffice (D4) ; la version moderne remplace alors
# l'objet d'origine dans le document.
#
#   relever(...)    → les textes des objets (ids préfixés) et le rapport ;
#   reinjecter(...) → ce qu'il faut changer dans le paquet hôte (`Modifs`) ;
#   appliquer_*(…)  → le changement, sur un dossier extrait ou un fichier zip.
#
# Les deux premières font le MÊME parcours (mêmes objets, mêmes préfixes) : un
# id relevé à l'extraction se retrouve à l'identique à l'injection.

_TYPE_NATURE = {"xlsx": "classeur", "xls": "classeur", "docx": "document",
                "doc": "document", "pptx": "presentation", "ppt": "presentation"}
_ETIQUETTE = {"xlsx": "excel", "xls": "excel", "docx": "word", "doc": "word",
              "pptx": "ppt", "ppt": "ppt"}
_MODERNE = {"xls": "xlsx", "doc": "docx", "ppt": "pptx"}

_TYPE_PACKAGE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/package"
_NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
_CT_MODERNE = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
# progId d'un objet 97-2003 → progId de sa version moderne ; autre : inchangé.
_PROGID_MODERNE = {
    "excel.sheet.8": "Excel.Sheet.12", "excel.chart.8": "Excel.Chart.12",
    "word.document.8": "Word.Document.12", "powerpoint.show.8": "PowerPoint.Show.12",
    "powerpoint.slide.8": "PowerPoint.Slide.12",
}


logger = logging.getLogger(__name__)

# Budget du document de PREMIER niveau, partagé par les sous-moteurs : sans lui,
# chaque objet repartirait d'un budget neuf et le plafond anti-bombe ne
# vaudrait plus pour le document entier.
_BUDGET_COURANT: contextvars.ContextVar[Budget | None] = contextvars.ContextVar(
    "budget_objets", default=None)

# Conversions 97-2003 récentes, par empreinte : `relever` puis `reinjecter`
# convertissent le même binaire — une seule conversion, et des ids identiques.
_CONVERSIONS: dict[tuple[bytes, str], bytes] = {}
_CONVERSIONS_OCTETS_MAX = 64 * 1024 * 1024
_conversions_verrou = threading.Lock()


def _sans_base(objet: ObjetIncorpore) -> str:
    return ""


def _avec_budget(fonction, budget: Budget | None):
    """`fonction(budget)` avec le budget du document courant (ou un neuf au
    premier niveau), visible des sous-moteurs pendant l'appel."""
    budget = budget or _BUDGET_COURANT.get() or Budget()
    jeton = _BUDGET_COURANT.set(budget)
    try:
        return fonction(budget)
    finally:
        _BUDGET_COURANT.reset(jeton)


def _nettoyer_moteur(moteur) -> None:
    """Dossier de travail d'un sous-moteur (le moteur XLSX le garde ouvert)."""
    nettoyer = getattr(moteur, "_nettoyer", None)
    if callable(nettoyer):
        try:
            nettoyer()
        except Exception:  # noqa: BLE001
            pass


def stem(cible: str) -> str:
    """Nom de fichier d'une cible, sans dossier ni extension."""
    return posixpath.splitext(posixpath.basename(cible))[0]


def prefixe(base: str, extrait: Extrait) -> str:
    """Préfixe des ids d'un objet : `<base>excel_<nom du fichier>__`."""
    return f"{base}{_ETIQUETTE[extrait.type]}_{stem(extrait.objet.cible)}__"


class _EchecConversion(Exception):
    """Le binaire 97-2003 n'a pas pu être converti en version moderne."""


def _moderne(extrait: Extrait) -> tuple[str, bytes] | None:
    """(type, octets) du fichier OOXML à traduire, ou None si la conversion
    d'un binaire 97-2003 échoue (LibreOffice absent, fichier illisible…)."""
    if extrait.enveloppe != "ancien":
        return extrait.type, extrait.contenu
    from engines import office
    type_ = _MODERNE[extrait.type]
    cle = (hashlib.sha256(extrait.contenu).digest(), type_)
    with _conversions_verrou:
        octets = _CONVERSIONS.get(cle)
    if octets is None:
        try:
            octets = office.convertir(extrait.contenu, extrait.type, type_)
        except Exception as exc:  # noqa: BLE001 — l'objet d'origine reste tel quel
            logger.warning("Objet %s non converti : %s", extrait.objet.cible, exc)
            return None
        with _conversions_verrou:
            _CONVERSIONS[cle] = octets
            while sum(map(len, _CONVERSIONS.values())) > _CONVERSIONS_OCTETS_MAX \
                    and len(_CONVERSIONS) > 1:
                del _CONVERSIONS[next(iter(_CONVERSIONS))]
    return (type_, octets) if taille_zip_sure(octets) is not None else None


def _elements_de(noeud) -> list[dict]:
    """Les blocs de texte d'une extraction, PAR RÉFÉRENCE : tout dictionnaire
    qui porte un `id` et un `text` non vide, où qu'il soit dans le JSON. Le
    rapport des objets n'en contient pas et n'est pas parcouru."""
    if isinstance(noeud, list):
        return [e for fils in noeud for e in _elements_de(fils)]
    if not isinstance(noeud, dict):
        return []
    trouves = []
    if (isinstance(noeud.get("id"), str) and isinstance(noeud.get("text"), str)
            and noeud["text"].strip()):
        trouves.append(noeud)
    for cle, fils in noeud.items():
        if cle != "objets_rapport":
            trouves.extend(_elements_de(fils))
    return trouves


def _ouvrir(source) -> zipfile.ZipFile:
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    return zipfile.ZipFile(source)


def _retenir(zf: zipfile.ZipFile, objets: list[ObjetIncorpore], base, niveau: int,
             budget: Budget):
    """Parcours commun à `relever` et `reinjecter`.

    Rend (objets retenus, {cible: (extrait, préfixe) | None}). Une cible n'est
    extraite qu'une fois, même affichée à plusieurs endroits ; `base(objet)` à
    None écarte l'objet (ni relevé, ni compté dans le rapport)."""
    retenus: list[ObjetIncorpore] = []
    trouves: dict[str, tuple[Extrait, str] | None] = {}
    for o in objets:
        b = base(o)
        if b is None:
            continue
        retenus.append(o)
        if o.cible not in trouves:
            ex = extraire(zf, o, niveau, budget)
            trouves[o.cible] = None if ex is None else (ex, prefixe(b, ex))
    for o in retenus:
        t = trouves[o.cible]
        if t is not None:
            o.nature = _TYPE_NATURE[t[0].type]      # un « paquet » devient ce qu'il contient
        elif o.raison_non_traite is None:
            # Traitable sur le papier, mais rien n'a pu en être tiré.
            o.echec = "profondeur" if niveau > PROFONDEUR_MAX else "illisible"
    return retenus, trouves


def _sous_extraction(type_: str, octets: bytes, dossier: str, niveau: int):
    """Écrit le fichier dans `dossier`, le fait relever par le moteur de son
    format et rend (moteur, chemin du fichier, chemin du JSON, JSON)."""
    from engines import new_engine
    moteur = new_engine(type_)
    if moteur is None:
        raise ValueError(f"aucun moteur pour {type_}")
    entree = os.path.join(dossier, f"objet.{type_}")
    with open(entree, "wb") as f:
        f.write(octets)
    chemin_json = os.path.join(dossier, "extraction.json")
    try:
        moteur.extract_text(entree, chemin_json, niveau_objets=niveau + 1)
    finally:
        _nettoyer_moteur(moteur)
    with open(chemin_json, encoding="utf-8") as f:
        return entree, chemin_json, json.load(f)


def relever(source, base=_sans_base, niveau: int = 1,
            budget: Budget | None = None) -> tuple[list[dict], dict]:
    """Textes des objets incorporés de `source` (chemin, octets ou fichier).

    Rend (éléments, rapport). Chaque élément est `{"id", "text", "context"}`,
    l'id étant `base(objet)` + `excel_<fichier>__` + l'id du moteur de l'objet.
    Les objets des objets sont déjà dans la liste, à plat. Le rapport est établi
    APRÈS l'extraction : un objet qui n'a pu être traité y figure avec sa raison.
    Au mieux : un objet en échec est ignoré, jamais l'extraction du document."""
    return _avec_budget(lambda b: _relever(source, base, niveau, b), budget)


def _relever(source, base, niveau: int, budget: Budget) -> tuple[list[dict], dict]:
    objets = reperer(source)
    if not objets:
        return [], rapport([])
    elements: list[dict] = []
    imbriques: list[dict] = []
    try:
        zf = _ouvrir(source)
    except _ERREURS_ZIP:
        return [], rapport(objets)
    with zf:
        retenus, trouves = _retenir(zf, objets, base, niveau, budget)
    for cible, trouve in trouves.items():
        if trouve is None:
            continue
        ex, pref = trouve
        premier = next(o for o in retenus if o.cible == cible)
        dossier = tempfile.mkdtemp(prefix="incorpore_")
        try:
            moderne = _moderne(ex)
            if moderne is None:
                raise _EchecConversion()
            _, _, data = _sous_extraction(moderne[0], moderne[1], dossier, niveau)
            classeur = _TYPE_NATURE[ex.type] == "classeur"
            # Objets non traités de l'objet lui-même : « parent › enfant »,
            # affichés par la partie qui montre le parent.
            nom = posixpath.basename(cible) or cible
            for sous in (data.get("objets_rapport") or {}).get("non_traites", []):
                imbriques.append({**sous, "cible": f"{nom} › {sous.get('cible') or '?'}",
                                  "partie": premier.partie})
            nouveaux = []
            for el in _elements_de(data):
                contexte = {**(el.get("context") or {}), "objet": cible,
                            "partie": premier.partie,
                            "shape_type": "Excel Cell" if classeur else "Embedded Object"}
                nouveaux.append({"id": pref + el["id"], "text": el["text"],
                                 "context": contexte})
            elements.extend(nouveaux)
        except _EchecConversion:
            for o in retenus:
                if o.cible == cible:
                    o.echec = "conversion"
        except Exception as exc:  # noqa: BLE001 — au mieux : l'objet est laissé tel quel
            logger.warning("Objet %s non relevé : %s", cible, exc)
            for o in retenus:
                if o.cible == cible:
                    o.echec = "erreur"
        finally:
            shutil.rmtree(dossier, ignore_errors=True)
    return elements, rapport(retenus, imbriques)


@dataclass
class Modifs:
    """Ce qu'il faut changer dans le paquet hôte pour y remettre les objets
    traduits."""
    parties: dict[str, bytes] = field(default_factory=dict)
    # ("rel", partie_rels, rid, cible_relative, type_rel)
    # ("progid", partie_hote, rid, nouveau_progid)
    # ("defaut", extension, content_type)
    retouches: list[tuple] = field(default_factory=list)
    cibles: list[str] = field(default_factory=list)   # objets effectivement traduits
    # Ce que le client doit savoir après coup : {cible, raison}. `reinjection` :
    # l'objet reste en langue d'origine ; `apercu` : il est traduit mais son
    # image affichée reste celle d'origine. Cible None : objet non identifié.
    restes: list[dict] = field(default_factory=list)


_verrou_cumul = threading.Lock()


def cumuler(liste: list[dict], nouveaux: Iterable[dict]) -> None:
    """Ajoute sans doublon sur (cible, raison), comme `rapport` : un objet montré
    par deux diapositives n'est signalé qu'une fois. Sûr entre fils : le moteur
    PPTX progressif traite ses diapositives en parallèle."""
    with _verrou_cumul:
        vus = {(o.get("cible"), o.get("raison")) for o in liste}
        for o in nouveaux:
            cle = (o.get("cible"), o.get("raison"))
            if cle not in vus:
                vus.add(cle)
                liste.append(o)


def reste_inconnu() -> dict:
    """Réinjection perdue en bloc : on ne sait plus quels objets sont touchés."""
    return {"cible": None, "raison": "reinjection"}


def _reste(cible: str, raison: str) -> dict:
    return {"cible": posixpath.basename(cible) or cible, "raison": raison}


def _nom_libre(cible: str, type_: str, pris: set[str]) -> str:
    """`<dossier de la cible>/<nom>.<type>`, numéroté si le nom est déjà pris."""
    dossier, nom = posixpath.dirname(cible), stem(cible)
    candidat, n = posixpath.join(dossier, f"{nom}.{type_}"), 1
    while candidat in pris:
        n += 1
        candidat = posixpath.join(dossier, f"{nom}_{n}.{type_}")
    return candidat


def reinjecter(source, traductions: dict[str, str], base=_sans_base,
               niveau: int = 1, budget: Budget | None = None) -> Modifs:
    """Remet dans le paquet les objets de `source` traduits.

    `traductions` : {id relevé par `relever`: texte traduit}. Même parcours et
    mêmes préfixes que `relever`. Un objet sans changement est laissé tel quel ;
    un objet dont la remise en place échoue aussi, mais il est signalé dans
    `Modifs.restes`. Un objet 97-2003 traduit devient une partie OOXML nouvelle
    (D4) : sa relation et son progId sont réécrits ; l'ancien `.bin` reste dans
    le paquet, orphelin — Office l'ignore."""
    if not traductions:
        return Modifs()
    return _avec_budget(lambda b: _reinjecter(source, traductions, base, niveau, b), budget)


def _relire(type_: str, octets: bytes, dossier: str, niveau: int, budget: Budget):
    """`_sous_extraction` pour la réinjection. La sous-injection qui suit décompte
    les objets internes : décomptés aussi ici, ils le seraient deux fois et un
    objet relevé sans peine à l'extraction échouerait à sa remise en place."""
    jeton = _BUDGET_COURANT.set(Budget(budget.reste))
    try:
        return _sous_extraction(type_, octets, dossier, niveau)
    finally:
        _BUDGET_COURANT.reset(jeton)


def _reinjecter(source, traductions: dict[str, str], base, niveau: int,
                budget: Budget) -> Modifs:
    modifs = Modifs()
    # Seuls les objets dont un id traduit porte le nom sont ouverts.
    tous = reperer(source)
    objets = [o for o in tous
              if any(f"_{stem(o.cible)}__" in k for k in traductions)]
    if not objets:
        return modifs
    try:
        zf = _ouvrir(source)
    except _ERREURS_ZIP:
        cumuler(modifs.restes, [reste_inconnu()])
        return modifs
    with zf:
        retenus, trouves = _retenir(zf, objets, base, niveau, budget)
        pris = set(zf.namelist())
    traduits: dict[str, tuple[str, bytes]] = {}
    for cible, trouve in trouves.items():
        if trouve is None:
            # Relevé à l'extraction, plus lisible maintenant : traductions perdues.
            if any(o.cible == cible and o.echec for o in retenus):
                cumuler(modifs.restes, [_reste(cible, "reinjection")])
            continue
        ex, pref = trouve
        if not any(k.startswith(pref) for k in traductions):
            continue        # aucune traduction pour cet objet : inutile de l'ouvrir
        dossier = tempfile.mkdtemp(prefix="incorpore_")
        echec = True    # sauf objet remis en place ou sans changement
        try:
            moderne = _moderne(ex)
            if moderne is None:
                continue
            type_, octets = moderne
            entree, chemin_json, data = _relire(type_, octets, dossier, niveau, budget)
            elements = list(_elements_de(data))
            ids = {pref + el["id"] for el in elements}
            if any(k.startswith(pref) and k not in ids for k in traductions):
                # Une partie de l'objet (un objet interne) ne se relit plus.
                cumuler(modifs.restes, [_reste(cible, "reinjection")])
            change = False
            for el in elements:
                el["translated_text"] = traductions.get(pref + el["id"]) or el["text"]
                change = change or el["translated_text"] != el["text"]
            if not change:
                echec = False
                continue
            with open(chemin_json, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            sortie = os.path.join(dossier, f"sortie.{type_}")
            from engines import new_engine
            moteur = new_engine(type_)
            try:
                resultat = moteur.inject_translation(
                    entree, chemin_json, sortie, niveau_objets=niveau + 1)
            finally:
                _nettoyer_moteur(moteur)
            ok = resultat[0] if isinstance(resultat, tuple) else resultat
            if ok is False or not os.path.isfile(sortie):
                continue
            with open(sortie, "rb") as f:
                nouveaux = f.read()
            if _type_ooxml(nouveaux) != type_:
                continue
            if ex.enveloppe == "ancien":
                _remplacer_ancien(modifs, ex, type_, nouveaux, retenus, pris)
            else:
                modifs.parties[cible] = reecrire(ex, nouveaux)
            modifs.cibles.append(cible)
            traduits[cible] = (type_, nouveaux)
            echec = False
            # Après la remise en place : un parent perdu est seul à signaler.
            nom = posixpath.basename(cible) or cible
            cumuler(modifs.restes, [{**r, "cible": f"{nom} › {r.get('cible') or '?'}"}
                                    for r in getattr(moteur, "objets_restes", [])])
            for o in retenus:
                r = ("graphique", o.graphique, nouveaux, ex.contenu)
                if o.cible == cible and o.graphique and r not in modifs.retouches:
                    modifs.retouches.append(r)
        except Exception as exc:  # noqa: BLE001 — au mieux : l'objet d'origine est gardé
            logger.warning("Objet %s non réinjecté : %s", cible, exc)
            continue
        finally:
            if echec:
                cumuler(modifs.restes, [_reste(cible, "reinjection")])
            shutil.rmtree(dossier, ignore_errors=True)
    _redessiner_apercus(modifs, traduits, retenus, tous, pris)
    return modifs


_TYPE_IMAGE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"


def _redessiner_apercus(modifs: Modifs, traduits: dict[str, tuple[str, bytes]],
                        retenus: list[ObjetIncorpore], tous: list[ObjetIncorpore],
                        pris: set[str]) -> None:
    """Refait l'image affichée des objets traduits (6.11.4) : un PNG neuf, vers
    lequel TOUTES les relations de l'aperçu (DrawingML et VML) sont réorientées.
    Une icône garde son image ; l'ancien aperçu reste, orphelin (il peut servir
    ailleurs dans le paquet). Un aperçu non redessiné reste celui d'origine et
    l'objet est signalé dans `modifs.restes`.
    Une image partagée avec un objet NON traduit (diapositive dupliquée hors
    de la plage, objet sauté) n'est pas redessinée : elle le montrerait traduit."""
    from engines import apercus
    demandes, objets = [], {}
    for o in retenus:
        if o.cible not in traduits or o.icone or o.lie or not o.apercu or o.apercu in objets:
            continue
        if any(a.apercu == o.apercu and a.cible not in traduits for a in tous):
            cumuler(modifs.restes, [_reste(o.cible, "apercu")])
            continue
        type_, nouveaux = traduits[o.cible]
        demandes.append(apercus.Demande(o.apercu, type_, nouveaux, o.ratio))
        objets[o.apercu] = o
    if not demandes:
        return
    try:
        rendus = apercus.redessiner(demandes)
    except Exception as exc:  # noqa: BLE001 — au mieux : les aperçus d'origine restent
        logger.warning("Aperçus non redessinés : %s", exc)
        cumuler(modifs.restes, [_reste(o.cible, "apercu") for o in objets.values()])
        return
    cumuler(modifs.restes, [_reste(o.cible, "apercu") for a, o in objets.items()
                            if a not in rendus])
    for apercu, png in rendus.items():
        o = objets[apercu]
        nom = _nom_libre(posixpath.join(posixpath.dirname(apercu), stem(apercu) + "_traduit"),
                         "png", pris | set(modifs.parties))
        modifs.parties[nom] = png
        for rels, rid in o.relations_apercu:
            source = posixpath.dirname(posixpath.dirname(rels))
            modifs.retouches.append(
                ("rel", rels, rid, posixpath.relpath(nom, source or "."), _TYPE_IMAGE))
    if rendus:
        defaut = ("defaut", "png", "image/png")
        if defaut not in modifs.retouches:
            modifs.retouches.append(defaut)


def _remplacer_ancien(modifs: Modifs, ex: Extrait, type_: str, nouveaux: bytes,
                      retenus: list[ObjetIncorpore], pris: set[str]) -> None:
    """Un 97-2003 traduit devient une partie OOXML : nouvelle partie, relation
    réorientée vers elle (type `package`), progId et type de contenu modernes."""
    cible = ex.objet.cible
    nom = _nom_libre(cible, type_, pris | set(modifs.parties))
    modifs.parties[nom] = nouveaux
    vus = set()
    for o in retenus:
        if o.cible != cible or not o.rid:
            continue
        relative = posixpath.relpath(nom, posixpath.dirname(o.partie))
        rel = ("rel", _Paquet.rels_de(o.partie), o.rid, relative, _TYPE_PACKAGE)
        nouveau = _PROGID_MODERNE.get(o.prog_id.lower())
        progid = ("progid", o.partie, o.rid, nouveau) if nouveau else None
        for r in (rel, progid):
            if r is not None and r not in vus:
                vus.add(r)
                modifs.retouches.append(r)
    defaut = ("defaut", type_, _CT_MODERNE[type_])
    if defaut not in modifs.retouches:
        modifs.retouches.append(defaut)


def _retoucher(retouches: list[tuple], lire) -> dict[str, bytes]:
    """Parties XML retouchées, lues avec `lire(nom) -> octets | None` (le
    contenu COURANT du paquet). Une retouche qui échoue est sans effet."""
    racines: dict[str, etree._Element | None] = {}
    modifiees: list[str] = []

    def racine(nom: str):
        if nom not in racines:
            octets = lire(nom)
            if octets is None or len(octets) > OCTETS_PARTIE_MAX:
                racines[nom] = None
            else:
                parser = etree.XMLParser(resolve_entities=False, no_network=True)
                racines[nom] = etree.fromstring(octets, parser)
        return racines[nom]

    def noter(nom: str) -> None:
        if nom not in modifiees:
            modifiees.append(nom)

    for r in retouches:
        try:
            if r[0] == "rel":
                _, partie_rels, rid, cible, type_rel = r
                for e in racine(partie_rels).iter("{%s}Relationship" % NS["rel"]):
                    if e.get("Id") == rid:
                        e.set("Target", cible)
                        e.set("Type", type_rel)
                        e.attrib.pop("TargetMode", None)
                        noter(partie_rels)
            elif r[0] == "progid":
                _, partie, rid, progid = r
                for e in racine(partie).iter():
                    if e.get(_R_ID) != rid:
                        continue
                    for attribut in ("progId", "ProgID"):
                        if e.get(attribut) is not None:
                            e.set(attribut, progid)
                            noter(partie)
            elif r[0] == "defaut":
                _, extension, type_contenu = r
                types = racine("[Content_Types].xml")
                defauts = [e for e in types if e.tag == "{%s}Default" % _NS_CT]
                if not any((e.get("Extension") or "").lower() == extension.lower()
                           for e in defauts):
                    neuf = etree.Element("{%s}Default" % _NS_CT, nsmap=types.nsmap)
                    neuf.set("Extension", extension)
                    neuf.set("ContentType", type_contenu)
                    types.insert(types.index(defauts[-1]) + 1 if defauts else 0, neuf)
                    noter("[Content_Types].xml")
            elif r[0] == "graphique":
                _, graphique, traduit, original = r
                if _aligner_graphique(racine(graphique), traduit, original):
                    noter(graphique)
        except Exception:  # noqa: BLE001 — retouche sans effet, le reste continue
            continue
    return {nom: etree.tostring(racines[nom], xml_declaration=True,
                                encoding="UTF-8", standalone=True)
            for nom in modifiees}


def _onglets(octets: bytes) -> list[tuple[str, str]]:
    """[(nom d'onglet, partie de la feuille)] d'un classeur, dans l'ordre."""
    with zipfile.ZipFile(io.BytesIO(octets)) as zf:
        paquet = _Paquet(zf)
        classeur = paquet.xml("xl/workbook.xml")
        if classeur is None:
            return []
        rels = paquet.relations("xl/workbook.xml")
        return [(s.get("name") or "", rels.get(s.get(_R_ID) or "", ("",))[0])
                for s in classeur.iterfind("x:sheets/x:sheet", NS)]


def _aligner_graphique(graphique, traduit: bytes, original: bytes) -> bool:
    """Réaligne le XML d'un graphique natif sur son classeur caché traduit
    (6.11.5) : chaque `c:f` suit les onglets renommés, chaque `c:strCache`
    d'un `c:strRef` reçoit le texte des cellules traduites. Le classeur fait
    foi, comme dans le moteur XLSX. Rend True si le graphique a changé."""
    # Import tardif : le moteur XLSX importe ce module.
    from engines.xlsx.engine import XLSXTranslatorEngine as XlsxEngine, reecrire_references
    avant, apres = _onglets(original), _onglets(traduit)
    renommage = {a[0]: b[0] for a, b in zip(avant, apres) if a[0] and b[0] and a[0] != b[0]}
    touche = False
    for f in graphique.iter("{%s}f" % NS["c"]):
        neuf = reecrire_references(f.text or "", renommage)
        if neuf != (f.text or ""):
            f.text = neuf
            touche = True
    feuilles = {nom: cible for nom, cible in apres}
    avant_cibles = {cible for _, cible in avant}
    with zipfile.ZipFile(io.BytesIO(traduit)) as zf, \
            zipfile.ZipFile(io.BytesIO(original)) as zo:
        paquet, paquet_o = _Paquet(zf), _Paquet(zo)

        def lire(p):
            sst = p.xml("xl/sharedStrings.xml")
            return [] if sst is None else [
                "".join(t.text or "" for t in si.iter("{%s}t" % NS["x"]))
                for si in sst.iterfind("x:si", NS)]

        def grille(p, cible):
            feuille = p.xml(cible)
            return {} if feuille is None else {
                c.get("r"): c for c in feuille.iter("{%s}c" % NS["x"]) if c.get("r")}

        magasin, magasin_o = lire(paquet), lire(paquet_o)
        cellules: dict[str, dict] = {}
        cellules_o: dict[str, dict] = {}
        for sref in graphique.iter("{%s}strRef" % NS["c"]):
            f, cache = sref.find("c:f", NS), sref.find("c:strCache", NS)
            m = XlsxEngine._REF_GRAPHIQUE.match((f.text or "").strip()) \
                if f is not None else None
            if m is None or cache is None:
                continue
            cible = feuilles.get(m.group(1).replace("''", "'") if m.group(1) else m.group(2))
            if not cible:
                continue
            if cible not in cellules:
                cellules[cible] = grille(paquet, cible)
                cellules_o[cible] = grille(paquet_o, cible) if cible in avant_cibles else {}
            c1, l1 = XlsxEngine._colonne_de_ref(m.group(3)), int(m.group(4))
            c2, l2 = ((XlsxEngine._colonne_de_ref(m.group(5)), int(m.group(6)))
                      if m.group(5) else (c1, l1))
            largeur = c2 - c1 + 1     # ligne par ligne, comme `_aligner_graphiques`
            if largeur < 1 or l2 < l1:
                continue
            for pt in cache.iterfind("c:pt", NS):
                v, idx = pt.find("c:v", NS), pt.get("idx") or ""
                if v is None or not idx.isdigit():
                    continue
                ligne, col = divmod(int(idx), largeur)
                if l1 + ligne > l2:
                    continue
                ref = f"{XlsxEngine._lettres(c1 + col)}{l1 + ligne}"
                cel, cel_o = cellules[cible].get(ref), cellules_o[cible].get(ref)
                texte = (None if cel is None
                         else XlsxEngine._texte_de_cellule(None, cel, magasin))
                texte_o = (None if cel_o is None
                           else XlsxEngine._texte_de_cellule(None, cel_o, magasin_o))
                # Seule une cellule que la traduction a changée fait foi : une
                # cellule laissée telle quelle (formule, texte écarté) ne
                # remet pas la langue source dans un cache déjà traduit.
                if texte is not None and texte != texte_o and texte != v.text:
                    v.text = texte
                    touche = True
    return touche


def _nom_sur(nom: str) -> bool:
    """Un nom de partie qui reste DANS le paquet (jamais de `..` ni de racine)."""
    return bool(nom) and not nom.startswith("/") and ".." not in nom.split("/")


def appliquer_dossier(dossier, modifs: Modifs) -> None:
    """Applique `modifs` à un paquet déjà extrait dans `dossier`."""
    racine = Path(dossier)
    for nom, octets in modifs.parties.items():
        if _nom_sur(nom):
            chemin = racine / nom
            chemin.parent.mkdir(parents=True, exist_ok=True)
            chemin.write_bytes(octets)

    def lire(nom: str) -> bytes | None:
        chemin = racine / nom
        return chemin.read_bytes() if _nom_sur(nom) and chemin.is_file() else None

    for nom, octets in _retoucher(modifs.retouches, lire).items():
        (racine / nom).write_bytes(octets)


def appliquer_fichier(chemin_zip, modifs: Modifs) -> None:
    """Applique `modifs` à un paquet zip sur disque (réécriture atomique).
    Rien à faire : le fichier n'est pas touché."""
    if not modifs.parties and not modifs.retouches:
        return
    chemin_zip = str(chemin_zip)
    with open(chemin_zip, "rb") as f:
        octets = f.read()
    with zipfile.ZipFile(io.BytesIO(octets)) as zf:
        noms = set(zf.namelist())
        table = {n: b for n, b in modifs.parties.items() if _nom_sur(n)}
        table.update(_retoucher(modifs.retouches,
                                lambda n: zf.read(n) if n in noms else None))
    neuf = remplacer_parties(octets, table, ajouter=True)
    if neuf is octets:
        return
    temporaire = chemin_zip + ".tmp"
    with open(temporaire, "wb") as f:
        f.write(neuf)
    os.replace(temporaire, chemin_zip)


# --------------------------------------------------------------------------- #
# Écriture d'un fichier composé OLE2 (MS-CFB, version 3)
# --------------------------------------------------------------------------- #
#
# `olefile` sait lire, mais ne réécrit un flux qu'à taille égale ; une
# traduction change la taille. On recopie donc l'arbre entier (flux, dossiers,
# CLSID, drapeaux, dates) dans un nouveau fichier : secteurs de 512 octets,
# petits flux (< 4 096 octets) dans le mini-flux, arbre binaire équilibré
# tout noir (forme admise par MS-CFB 2.6.4).

_SECTEUR, _MINI, _COUPURE = 512, 64, 4096
_LIBRE, _FIN, _SECT_FAT, _SECT_DIFAT, _AUCUN = (0xFFFFFFFF, 0xFFFFFFFE,
                                                0xFFFFFFFD, 0xFFFFFFFC, 0xFFFFFFFF)
_FLUX, _RACINE = 2, 5


@dataclass
class _Noeud:
    nom: str
    type: int
    clsid: bytes
    etat: int
    cree: int
    modifie: int
    donnees: bytes = b""
    enfants: list = field(default_factory=list)


def _clsid_octets(texte: str) -> bytes:
    return uuid.UUID(texte).bytes_le if texte else b"\0" * 16


def _lire_arbre(ole) -> _Noeud:
    def noeud(e, chemin):
        n = _Noeud(e.name, e.entry_type, _clsid_octets(e.clsid), e.dwUserFlags,
                   e.createTime, e.modifyTime)
        if e.entry_type == _FLUX:
            n.donnees = ole.openstream(chemin).read()
        else:
            n.enfants = [noeud(k, chemin + [k.name]) for k in e.kids]
        return n
    return noeud(ole.root, [])


def _ecrire_cfb(racine: _Noeud) -> bytes:
    entrees: list[_Noeud] = []

    def numeroter(n):
        entrees.append(n)
        for k in n.enfants:
            numeroter(k)
    numeroter(racine)
    sid = {id(n): i for i, n in enumerate(entrees)}

    gauche, droite, enfant = {}, {}, {}

    def arbre(freres):          # liste triée → racine d'un arbre équilibré
        if not freres:
            return _AUCUN
        m = len(freres) // 2
        i = sid[id(freres[m])]
        gauche[i], droite[i] = arbre(freres[:m]), arbre(freres[m + 1:])
        return i
    for n in entrees:
        if n.type != _FLUX:
            enfant[sid[id(n)]] = arbre(sorted(n.enfants, key=lambda k: (len(k.nom), k.nom.upper())))

    fat: list[int] = []
    corps = bytearray()

    def poser(octets: bytes, bourrage: bytes = b"\0") -> int:
        nb = -(-len(octets) // _SECTEUR)
        if nb == 0:
            return _FIN
        debut = len(fat)
        fat.extend(range(debut + 1, debut + nb))
        fat.append(_FIN)
        corps.extend(octets + bourrage * (nb * _SECTEUR - len(octets)))
        return debut

    debuts: dict[int, int] = {}
    mini = bytearray()
    minifat: list[int] = []
    for i, n in enumerate(entrees):
        if n.type != _FLUX:
            continue
        if len(n.donnees) >= _COUPURE:
            debuts[i] = poser(n.donnees)
            continue
        nb = -(-len(n.donnees) // _MINI)
        if nb == 0:
            debuts[i] = _FIN
            continue
        debuts[i] = len(minifat)
        minifat.extend(range(len(minifat) + 1, len(minifat) + nb))
        minifat.append(_FIN)
        mini.extend(n.donnees.ljust(nb * _MINI, b"\0"))
    debuts[0] = poser(bytes(mini))
    debut_minifat = poser(struct.pack("<%dI" % len(minifat), *minifat), b"\xff")
    nb_minifat = -(-len(minifat) * 4 // _SECTEUR)

    repertoire = bytearray()
    for i, n in enumerate(entrees):
        nom = n.nom.encode("utf-16-le")[:62]
        flux_ou_racine = n.type in (_FLUX, _RACINE)
        taille = len(mini) if n.type == _RACINE else len(n.donnees) if n.type == _FLUX else 0
        repertoire += struct.pack(
            "<64sHBB3I16sIQQIQ", nom, len(nom) + 2, n.type, 1,
            gauche.get(i, _AUCUN), droite.get(i, _AUCUN), enfant.get(i, _AUCUN),
            n.clsid, n.etat, n.cree, n.modifie,
            debuts.get(i, _FIN) if flux_ou_racine else 0, taille)
    vide = struct.pack("<64sHBB3I16sIQQIQ", b"", 0, 0, 0, _AUCUN, _AUCUN, _AUCUN,
                       b"\0" * 16, 0, 0, 0, 0, 0)
    while len(repertoire) % _SECTEUR:
        repertoire += vide
    debut_repertoire = poser(bytes(repertoire))

    nb_fat = nb_difat = 0
    while True:                 # la FAT se décrit elle-même : point fixe
        total = len(fat) + nb_fat + nb_difat
        f = -(-total // 128)
        d = 0 if f <= 109 else -(-(f - 109) // 127)
        if (f, d) == (nb_fat, nb_difat):
            break
        nb_fat, nb_difat = f, d
    secteurs_fat = list(range(len(fat), len(fat) + nb_fat))
    debut_difat = len(fat) + nb_fat if nb_difat else _FIN
    fat.extend([_SECT_FAT] * nb_fat + [_SECT_DIFAT] * nb_difat)
    fat.extend([_LIBRE] * (nb_fat * 128 - len(fat)))

    difat = bytearray()
    reste = secteurs_fat[109:]
    for k in range(nb_difat):
        lot = reste[k * 127:(k + 1) * 127]
        suivant = debut_difat + k + 1 if k + 1 < nb_difat else _FIN
        difat += struct.pack("<128I", *(lot + [_LIBRE] * (127 - len(lot)) + [suivant]))

    tete = secteurs_fat[:109]
    entete = struct.pack(
        "<8s16sHHHHH6s9I109I", olefile.MAGIC, b"\0" * 16, 0x3E, 3, 0xFFFE, 9, 6,
        b"\0" * 6, 0, nb_fat, debut_repertoire, 0, _COUPURE,
        debut_minifat, nb_minifat, debut_difat, nb_difat,
        *(tete + [_LIBRE] * (109 - len(tete))))
    return entete + bytes(corps) + struct.pack("<%dI" % len(fat), *fat) + bytes(difat)
