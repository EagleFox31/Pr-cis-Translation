"""Débordement des zones de texte PPTX.

La traduction est jugée par rapport à SON original dans la même zone, jamais
par rapport au seul bord du cadre :
- l'original tenait : la traduction doit tenir ;
- l'original débordait déjà : la traduction ne doit pas déborder davantage
  (l'auteur avait accepté ce dépassement-là, pas un plus grand).

La mesure est approchée : largeur réelle de chaque lettre en Arial (police
très majoritaire des présentations, table fixe : aucune dépendance aux polices
du serveur), 1 em pour les caractères pleine chasse (CJK), interligne 1,2 em.
L'erreur résiduelle est la même des deux côtés, puisque source et traduction
sont mesurées dans la même zone, avec la même taille de police.

Dernier recours après la retraduction plus courte : la police est réduite en
écrivant la nouvelle taille dans le texte, comme le fait un maquettiste (même
rendu dans PowerPoint, LibreOffice, Keynote…), jamais sous 80 % de l'original.
Si la taille est héritée du masque (inconnue ici), repli sur
`normAutofit fontScale`, la valeur qu'écrit PowerPoint pour « Ajuster le texte ».
Les zones qui s'agrandissent seules (`spAutoFit`), sans retour à la ligne
(`wrap="none"`), en texte vertical ou en colonnes ne sont pas touchées.
"""
from __future__ import annotations

import copy
import unicodedata

from lxml import etree

_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
_EMU_PT = 12700
# Largeurs Arial en millièmes d'em (police à 1000 unités), par groupe.
_ARIAL = {
    191: "'", 222: "ijl’‘", 260: "|¦",
    278: " !,./:;I[\\]ft ÌÍÎÏìíîï",
    333: "()-`r¡¨­²³´·¸¹“”{}",
    350: "•", 355: '"', 389: "*", 400: "°", 469: "^",
    500: "Jcksvxyzçýÿ",
    584: "+<=>~¬×±÷",
    611: "FTZ¿ßø",
    667: "&ABEKPSVXYÀÁÂÃÄÅÈÉÊËÝÞ",
    722: "CDHNRUwÇÐÑÙÚÛÜ",
    737: "©®",
    778: "GOQÒÓÔÕÖØ",
    833: "Mm", 889: "%æ", 944: "Wœ", 1000: "Æ—…Œ",
    1015: "@",
}
_LARGEURS = {c: w / 1000 for w, cs in _ARIAL.items() for c in cs}
_DEFAUT_EM = 0.556          # chiffres, minuscules courantes, accents
_ESPACE_EM = 0.278
_INTERLIGNE = 1.2
# Marge de sécurité sur la largeur : le rendu (crénage, police de
# substitution métriquement proche) varie de quelques pour cent selon le
# logiciel ; un mot mesuré « tout juste » serait coupé ailleurs.
_MARGE = 0.97
_TAILLE_DEFAUT = 18.0
PLANCHER = 0.80
_PAS = 0.025
_AJUSTEMENTS = ("noAutofit", "normAutofit", "spAutoFit")


def _q(ns, nom):
    return f"{{{ns}}}{nom}"


def formes(root) -> list:
    """Toutes les formes de la diapositive, dans l'ordre du document : leur
    rang sert d'identité stable entre la mesure source et la réinjection."""
    return list(root.iter(_q(_P, "sp")))


def _taille(p, txbody) -> float:
    """Taille de police du paragraphe, en points : la plus grande des runs,
    sinon la marque de fin de paragraphe, sinon le style de la zone."""
    tailles = [int(r.get("sz")) for r in p.iter(_q(_A, "rPr"))
               if (r.get("sz") or "").isdigit()]
    if tailles:
        return max(tailles) / 100
    for chemin in (f"{{{_A}}}endParaRPr",
                   f"{{{_A}}}pPr/{{{_A}}}defRPr"):
        el = p.find(chemin)
        if el is not None and (el.get("sz") or "").isdigit():
            return int(el.get("sz")) / 100
    defaut = txbody.find(f"{{{_A}}}lstStyle/{{{_A}}}lvl1pPr/{{{_A}}}defRPr")
    if defaut is not None and (defaut.get("sz") or "").isdigit():
        return int(defaut.get("sz")) / 100
    return _TAILLE_DEFAUT


def _lignes_manuelles(p) -> list[str]:
    lignes = [""]
    for el in p:
        nom = etree.QName(el).localname
        if nom in ("r", "fld"):
            lignes[-1] += "".join(t.text or "" for t in el.iter(_q(_A, "t")))
        elif nom == "br":
            lignes.append("")
    return lignes


def _em(c: str) -> float:
    w = _LARGEURS.get(c)
    if w is not None:
        return w
    return 1.0 if unicodedata.east_asian_width(c) in ("W", "F") else _DEFAUT_EM


def _nb_lignes(texte: str, largeur: float, taille: float) -> int:
    """Lignes occupées par `texte` avec un retour à la ligne aux espaces ; un
    mot plus large qu'une ligne est coupé, comme le fait PowerPoint."""
    mots = texte.split()
    if not mots:
        return 1
    ligne = largeur * _MARGE / taille   # largeur d'une ligne, en em
    espace = _ESPACE_EM
    n, courant = 1, 0.0
    for mot in mots:
        lg = sum(_em(c) for c in mot)
        if courant and courant + espace + lg <= ligne + 1e-9:
            courant += espace + lg
            continue
        if courant:
            n += 1
        courant = 0.0
        for c in mot:                   # mot plus large que la ligne
            w = _em(c)
            if courant and courant + w > ligne + 1e-9:
                n += 1
                courant = 0.0
            courant += w
    return n


def hauteur(txbody, largeur: float, echelle: float = 1.0) -> float:
    """Hauteur estimée du texte, en points, à `echelle` de la police."""
    total = 0.0
    for p in txbody.findall(_q(_A, "p")):
        taille = _taille(p, txbody) * echelle
        n = sum(_nb_lignes(l, largeur, taille) for l in _lignes_manuelles(p))
        total += n * _INTERLIGNE * taille
    return total


def _emu(el, attr, defaut=0) -> int:
    v = el.get(attr) if el is not None else None
    try:
        return int(v)
    except (TypeError, ValueError):
        return defaut


def _geometrie(sp):
    """(largeur, hauteur) utiles en points, ou None si la zone n'est pas
    mesurable ou ne doit pas être ajustée."""
    txbody = sp.find(_q(_P, "txBody"))
    corps = txbody.find(_q(_A, "bodyPr")) if txbody is not None else None
    ext = sp.find(f"{{{_P}}}spPr/{{{_A}}}xfrm/{{{_A}}}ext")
    if corps is None or ext is None:
        return None          # espace réservé sans position propre : inconnu
    if (corps.get("wrap") == "none"
            or corps.get("vert") not in (None, "horz")
            or _emu(corps, "numCol", 1) > 1
            or corps.find(_q(_A, "spAutoFit")) is not None):
        return None
    cx, cy = _emu(ext, "cx"), _emu(ext, "cy")
    # Forme groupée : ses dimensions sont dans le repère du groupe.
    anc = sp.getparent()
    while anc is not None:
        if anc.tag == _q(_P, "grpSp"):
            x = anc.find(f"{{{_P}}}grpSpPr/{{{_A}}}xfrm")
            e = x.find(_q(_A, "ext")) if x is not None else None
            ce = x.find(_q(_A, "chExt")) if x is not None else None
            if _emu(ce, "cx") and _emu(ce, "cy"):
                cx = cx * _emu(e, "cx") / _emu(ce, "cx")
                cy = cy * _emu(e, "cy") / _emu(ce, "cy")
        anc = anc.getparent()
    largeur = (cx - _emu(corps, "lIns", 91440) - _emu(corps, "rIns", 91440)) / _EMU_PT
    haut = (cy - _emu(corps, "tIns", 45720) - _emu(corps, "bIns", 45720)) / _EMU_PT
    if largeur <= 0 or haut <= 0:
        return None
    return largeur, haut


_PORTEURS = ("rPr", "endParaRPr", "defRPr")


def _porteurs(txbody) -> list:
    """Éléments de la zone qui portent une taille de police explicite."""
    return [el for el in txbody.iter()
            if isinstance(el.tag, str)
            and etree.QName(el).localname in _PORTEURS
            and (el.get("sz") or "").isdigit()]


def _taille_connue(txbody) -> bool:
    """Toutes les tailles du texte sont écrites dans la zone (sinon elles
    viennent du masque et une taille écrite ici serait devinée)."""
    if txbody.find(f"{{{_A}}}lstStyle/{{{_A}}}lvl1pPr/{{{_A}}}defRPr[@sz]") is not None:
        return True
    for el in txbody.iter(_q(_A, "r"), _q(_A, "fld")):
        rpr = el.find(_q(_A, "rPr"))
        if rpr is None or not (rpr.get("sz") or "").isdigit():
            return False
    return True


def _restaurer(txbody, source, applique):
    """Remet les tailles d'origine d'une zone déjà réduite (`applique`)."""
    if not applique:
        return
    els = _porteurs(txbody)
    if len(els) == len(source[3]):
        for el, v in zip(els, source[3]):
            el.set("sz", str(v))
    else:
        for el in els:
            el.set("sz", str(round(int(el.get("sz")) / applique)))


def _ajustement(corps):
    for nom in _AJUSTEMENTS:
        el = corps.find(_q(_A, nom))
        if el is not None:
            return el
    return None


def _echelle(corps) -> float:
    el = corps.find(_q(_A, "normAutofit"))
    v = _emu(el, "fontScale", 100000) if el is not None else 100000
    return v / 100000


def etat_source(root) -> dict[int, tuple]:
    """Mesure de l'ORIGINAL, prise avant toute injection :
    {rang de la forme: (hauteur source, échelle source, ajustement d'origine,
    tailles écrites d'origine, tailles toutes connues)}. La clé "_reduites"
    garde les réductions déjà écrites, pour repartir de l'original."""
    etat = {}
    for i, sp in enumerate(formes(root)):
        geo = _geometrie(sp)
        if geo is None:
            continue
        txbody = sp.find(_q(_P, "txBody"))
        corps = txbody.find(_q(_A, "bodyPr"))
        f0 = _echelle(corps)
        aj = _ajustement(corps)
        etat[i] = (hauteur(txbody, geo[0], f0), f0,
                   copy.deepcopy(aj) if aj is not None else None,
                   [int(el.get("sz")) for el in _porteurs(txbody)],
                   _taille_connue(txbody))
    return etat


def _mesure(sp, source):
    """(limite, hauteur traduite, largeur) d'une forme mesurable."""
    geo = _geometrie(sp)
    if geo is None:
        return None
    hs, f0 = source[0], source[1]
    largeur, haut = geo
    txbody = sp.find(_q(_P, "txBody"))
    return max(haut, hs), hauteur(txbody, largeur, f0), largeur


def excedents(root, etat: dict) -> list[tuple[float, list]]:
    """Formes dont la traduction déborde plus que l'original :
    [(limite / hauteur traduite, paragraphes de la forme)]."""
    out = []
    reduites = etat.get("_reduites", {})
    for i, sp in enumerate(formes(root)):
        if i not in etat:
            continue
        _restaurer(sp.find(_q(_P, "txBody")), etat[i], reduites.get(i))
        m = _mesure(sp, etat[i])
        if m and m[1] > m[0]:
            out.append((m[0] / m[1],
                        sp.find(_q(_P, "txBody")).findall(_q(_A, "p"))))
    return out


def ajuster(root, etat: dict) -> int:
    """Réduit la police des formes qui débordent encore plus que l'original,
    au plus juste et jamais sous `PLANCHER`. Repart toujours de l'original :
    une réinjection ne cumule pas les réductions. Renvoie le nombre de formes
    réduites."""
    reduites = etat.setdefault("_reduites", {})
    n = 0
    for i, sp in enumerate(formes(root)):
        if i not in etat:
            continue
        hs, f0, aj0, _t0, connue = etat[i]
        txbody = sp.find(_q(_P, "txBody"))
        corps = txbody.find(_q(_A, "bodyPr"))
        _restaurer(txbody, etat[i], reduites.pop(i, None))
        actuel = _ajustement(corps)
        if actuel is not None:
            corps.remove(actuel)
        if aj0 is not None:
            _inserer(corps, copy.deepcopy(aj0))
        m = _mesure(sp, etat[i])
        if m is None or m[1] <= m[0]:
            continue
        limite, _ht, largeur = m
        s = 1.0
        while s - _PAS >= PLANCHER - 1e-9:
            s = round(s - _PAS, 3)
            if hauteur(txbody, largeur, f0 * s) <= limite:
                break
        if connue:
            for el in _porteurs(txbody):
                el.set("sz", str(max(100, round(int(el.get("sz")) * s))))
            reduites[i] = s
        else:
            el = corps.find(_q(_A, "normAutofit"))
            if el is None:
                ancien = _ajustement(corps)
                if ancien is not None:
                    corps.remove(ancien)
                el = etree.Element(_q(_A, "normAutofit"))
                _inserer(corps, el)
            el.set("fontScale", str(int(round(f0 * s * 100000))))
        n += 1
    return n


def _inserer(corps, el):
    """L'ajustement se place après `prstTxWarp` (ordre du schéma)."""
    pos = 1 if (len(corps) and corps[0].tag == _q(_A, "prstTxWarp")) else 0
    corps.insert(pos, el)
