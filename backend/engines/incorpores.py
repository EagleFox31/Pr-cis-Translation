"""Objets incorporés des documents Office : repérage (étape 6.11.1).

Un objet incorporé (classeur Excel dans une diapo, lettre Word dans un
classeur…) est un fichier rangé dans le paquet du document, affiché par une
IMAGE D'APERÇU que dessine Office. Traduire le document sans traduire l'objet
ni refaire son aperçu laisse un tableau en langue d'origine au milieu d'une
page traduite.

Ce module, commun aux trois moteurs (DOCX, XLSX, PPTX), ne fait pour l'instant
que REPÉRER : il lit le paquet et décrit chaque objet, sans rien modifier.
Les étapes suivantes (extraction, traduction, redessin) s'appuient sur cette
description. Voir `docs/etude-objets-incorpores.md`.

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

import io
import posixpath
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

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
}
_R_ID = "{%s}id" % NS["r"]
_R_EMBED = "{%s}embed" % NS["r"]
_O_RELID = "{%s}relid" % NS["o"]

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

    @property
    def raison_non_traite(self) -> str | None:
        """Pourquoi l'objet ne sera pas traduit, ou None s'il le sera."""
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
        except (KeyError, etree.XMLSyntaxError, zipfile.BadZipFile, ValueError,
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
    except (TypeError, ValueError):
        return None
    return w / h if w > 0 and h > 0 else None


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
        apercu=apercu, ratio=ratio)


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


def _ratio_ancre(feuille, ancre) -> float | None:
    """Ratio du cadre d'après `anchor/from` et `anchor/to` de la feuille."""
    def marque(nom):
        m = ancre.find("x:%s" % nom, NS)
        if m is None:
            return None
        try:
            return tuple(int(m.findtext("xdr:%s" % k, namespaces=NS))
                         for k in ("col", "colOff", "row", "rowOff"))
        except (TypeError, ValueError):
            return None
    de, a = marque("from"), marque("to")
    if not de or not a:
        return None
    fmt = feuille.find("x:sheetFormatPr", NS)
    def flt(v, defaut):
        try:
            return float(v)
        except (TypeError, ValueError):
            return defaut
    larg_def = flt(None if fmt is None else fmt.get("defaultColWidth"), 8.43)
    haut_def = flt(None if fmt is None else fmt.get("defaultRowHeight"), 15.0)
    larg = {}
    for c in feuille.iterfind("x:cols/x:col", NS):
        lo, hi = int(flt(c.get("min"), 0)), int(flt(c.get("max"), 0))
        for i in range(lo, min(hi, lo + 16384) + 1):
            larg[i - 1] = flt(c.get("width"), larg_def)
    haut = {}
    for row in feuille.iterfind("x:sheetData/x:row", NS):
        if row.get("ht"):
            haut[int(flt(row.get("r"), 0)) - 1] = flt(row.get("ht"), haut_def)
    def col_emu(i):
        return (larg.get(i, larg_def) * 7 + 5) * _PX_EMU
    def row_emu(i):
        return haut.get(i, haut_def) * EMU_PAR_PT
    w = sum(col_emu(i) for i in range(de[0], a[0])) - de[1] + a[1]
    h = sum(row_emu(i) for i in range(de[2], a[2])) - de[3] + a[3]
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
            liens = _relations_vers(paquet, {o.apercu for o in objets if o.apercu})
            for o in objets:
                if o.apercu:
                    o.relations_apercu = list(liens.get(o.apercu, []))
            return objets
    except (zipfile.BadZipFile, OSError, ValueError):
        return []


def rapport(objets: list[ObjetIncorpore]) -> dict:
    """Résumé pour le journal et le compte rendu client (D6).

    Un objet affiché à plusieurs endroits n'est signalé qu'une fois ; les
    marqueurs de compléments ne le sont jamais."""
    a_traiter = [o for o in objets if o.raison_non_traite is None]
    non_traites, vus = [], set()
    for o in objets:
        raison = o.raison_non_traite
        if raison is None or raison == "marqueur" or (o.cible, raison) in vus:
            continue
        vus.add((o.cible, raison))
        non_traites.append({"cible": posixpath.basename(o.cible) or o.cible,
                            "partie": o.partie, "nature": o.nature,
                            "raison": raison})
    natures: dict[str, int] = {}
    for o in objets:
        natures[o.nature] = natures.get(o.nature, 0) + 1
    return {"total": len(objets), "a_traiter": len(a_traiter),
            "a_redessiner": sum(1 for o in a_traiter if not o.icone and o.apercu),
            "natures": natures, "non_traites": non_traites}
