"""Extraction et réécriture des objets incorporés (6.11.2) — `engines/incorpores.py`.

Ce que ce fichier verrouille :
  - aller-retour : extraire puis réécrire sans changement rend la cible
    identique octet pour octet, pour chaque enveloppe (OOXML, OLE2 `Package`,
    OLE2 `\\x01Ole10Native`) ;
  - réécrire un contenu traduit (plus long) le remet dans la MÊME enveloppe :
    autres flux, CLSID, nom et chemin du paquet conservés ;
  - le fichier OLE2 réécrit est relu par `olefile` au niveau d'exigence le
    plus strict, petits flux (mini-flux) comme gros flux (DIFAT) ;
  - un binaire 97-2003 est reconnu mais jamais réécrit sur place (D4) ;
  - garde-fous : .bin mal formé, bombe zip, profondeur 3, budget cumulé,
    objet lié, absent ou non traduisible → None, sans exception.

Tout est SYNTHÉTIQUE.

Exécution :  PYTHONUTF8=1 <venv>/python.exe tests/test_incorpores_extraction.py
"""
from __future__ import annotations

import io
import struct
import unittest
import zipfile

import racine  # noqa: F401  -- met backend/ sur le chemin

import olefile  # noqa: E402

from engines import incorpores as I  # noqa: E402

CLSID_PAQUET = "0003000C-0000-0000-C000-000000000046"
CLSID_EXCEL = "00020830-0000-0000-C000-000000000046"


def ooxml(principal: str, texte: str = "Bonjour", bourrage: int = 0) -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr(principal, "<x>%s</x>" % texte)
        if bourrage:
            zf.writestr("docProps/remplissage.bin", b"\0" * bourrage)
    return tampon.getvalue()


def ole2(flux: dict[str, bytes], clsid: str = "") -> bytes:
    noeuds = [I._Noeud(nom, I._FLUX, b"\0" * 16, 0, 0, 0, donnees)
              for nom, donnees in flux.items()]
    racine_ = I._Noeud("Root Entry", I._RACINE, I._clsid_octets(clsid), 0, 0, 0,
                       enfants=noeuds)
    return I._ecrire_cfb(racine_)


def ole10_packager(nom: str, donnees: bytes) -> bytes:
    chemin = ("C:\\Temp\\" + nom).encode("latin-1") + b"\0"
    temp = ("C:\\Users\\x\\AppData\\" + nom).encode("latin-1") + b"\0"
    corps = (struct.pack("<H", 2) + nom.encode("latin-1") + b"\0" + chemin
             + struct.pack("<HH", 0, 3) + struct.pack("<I", len(temp)) + temp
             + struct.pack("<I", len(donnees)) + donnees)
    unicode_ = b"".join(struct.pack("<I", len(s)) + s.encode("utf-16-le")
                        for s in (temp.decode("latin-1")[:-1], nom, chemin.decode("latin-1")[:-1]))
    corps += unicode_
    return struct.pack("<I", len(corps)) + corps


def paquet(parties: dict[str, bytes]) -> zipfile.ZipFile:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as zf:
        for nom, octets in parties.items():
            zf.writestr(nom, octets)
    return zipfile.ZipFile(io.BytesIO(tampon.getvalue()))


def objet(cible, prog_id="Excel.Sheet.12", lie=False, present=True):
    return I.ObjetIncorpore("pptx", "ppt/slides/slide1.xml", cible, prog_id,
                            I._nature(prog_id, cible), I._format(cible), False,
                            lie, present)


def relire(octets: bytes) -> dict[str, bytes]:
    with olefile.OleFileIO(io.BytesIO(octets), raise_defects=olefile.DEFECT_POTENTIAL) as ole:
        return {"/".join(p): ole.openstream(p).read() for p in ole.listdir()}


class OOXML(unittest.TestCase):
    def test_aller_retour_et_reecriture(self):
        xlsx = ooxml("xl/workbook.xml")
        cible = "ppt/embeddings/Microsoft_Excel_Worksheet.xlsx"
        ex = I.extraire(paquet({cible: xlsx}), objet(cible))
        self.assertEqual((ex.type, ex.enveloppe, ex.niveau), ("xlsx", "ooxml", 1))
        self.assertEqual(ex.contenu, xlsx)
        self.assertIs(I.reecrire(ex, xlsx), ex.origine)
        traduit = ooxml("xl/workbook.xml", "Hello")
        self.assertEqual(I.reecrire(ex, traduit), traduit)

    def test_paquet_docx_glisse_en_ooxml(self):
        cible = "word/embeddings/lettre.docx"
        ex = I.extraire(paquet({cible: ooxml("word/document.xml")}),
                        objet(cible, "Package"))
        self.assertEqual(ex.type, "docx")


class Package(unittest.TestCase):
    def setUp(self):
        self.xlsx = ooxml("xl/workbook.xml")
        self.bin = ole2({"\x01CompObj": b"compobj", "\x01Ole": b"\x01\0\0\x02" + b"\0" * 16,
                         "Package": self.xlsx}, CLSID_EXCEL)
        self.cible = "ppt/embeddings/oleObject1.bin"
        self.ex = I.extraire(paquet({self.cible: self.bin}), objet(self.cible))

    def test_extraction(self):
        self.assertEqual((self.ex.type, self.ex.enveloppe), ("xlsx", "package"))
        self.assertEqual(self.ex.contenu, self.xlsx)

    def test_aller_retour_identique(self):
        self.assertEqual(I.reecrire(self.ex, self.ex.contenu), self.bin)

    def test_reecriture_plus_longue_meme_enveloppe(self):
        for bourrage in (0, 6000, 70_000):     # mini-flux, puis secteurs normaux
            traduit = ooxml("xl/workbook.xml", "Hello world " * 50, bourrage)
            neuf = I.reecrire(self.ex, traduit)
            flux = relire(neuf)
            self.assertEqual(flux["Package"], traduit)
            self.assertEqual(flux["\x01CompObj"], b"compobj")
            with olefile.OleFileIO(io.BytesIO(neuf)) as ole:
                self.assertEqual(ole.root.clsid, CLSID_EXCEL)
            z = paquet({self.cible: neuf})
            self.assertEqual(I.extraire(z, objet(self.cible)).contenu, traduit)


class Ole10Native(unittest.TestCase):
    def setUp(self):
        self.docx = ooxml("word/document.xml")
        self.flux = ole10_packager("budget.docx", self.docx)
        self.bin = ole2({"\x01Ole10Native": self.flux, "\x03ObjInfo": b"\0\0\0\0\0\0"},
                        CLSID_PAQUET)
        self.cible = "word/embeddings/oleObject2.bin"
        self.ex = I.extraire(paquet({self.cible: self.bin}), objet(self.cible, "Package"))

    def test_extraction(self):
        self.assertEqual((self.ex.type, self.ex.enveloppe, self.ex.nom),
                         ("docx", "ole10native", "budget.docx"))
        self.assertEqual(self.ex.contenu, self.docx)

    def test_aller_retour_identique(self):
        self.assertEqual(I.reecrire(self.ex, self.ex.contenu), self.bin)

    def test_reecriture_garde_en_tete_et_suite(self):
        traduit = ooxml("word/document.xml", "Hello " * 300)
        flux = relire(I.reecrire(self.ex, traduit))["\x01Ole10Native"]
        self.assertEqual(flux, ole10_packager("budget.docx", traduit))
        self.assertEqual(struct.unpack_from("<I", flux)[0], len(flux) - 4)

    def test_natif_brut_sans_packager(self):
        brut = struct.pack("<I", len(self.docx)) + self.docx
        b = ole2({"\x01Ole10Native": brut})
        ex = I.extraire(paquet({self.cible: b}), objet(self.cible, "Package"))
        self.assertEqual((ex.contenu, ex.nom), (self.docx, None))
        traduit = ooxml("word/document.xml", "Hello")
        flux = relire(I.reecrire(ex, traduit))["\x01Ole10Native"]
        self.assertEqual(flux, struct.pack("<I", len(traduit)) + traduit)

    def test_fichier_glisse_non_office_ignore(self):
        b = ole2({"\x01Ole10Native": ole10_packager("notes.txt", b"du texte")})
        self.assertIsNone(I.extraire(paquet({self.cible: b}), objet(self.cible, "Package")))


class Ancien(unittest.TestCase):
    def test_binaire_97_2003_reconnu_jamais_reecrit(self):
        b = ole2({"Workbook": b"\x09\x08" + b"\0" * 5000, "\x01CompObj": b"c"})
        cible = "ppt/embeddings/oleObject3.bin"
        ex = I.extraire(paquet({cible: b}), objet(cible, "Excel.Sheet.8"))
        self.assertEqual((ex.type, ex.enveloppe, ex.contenu), ("xls", "ancien", b))
        self.assertEqual(I.reecrire(ex, b), b)
        with self.assertRaises(ValueError):
            I.reecrire(ex, b"autre")


class GardeFous(unittest.TestCase):
    cible = "ppt/embeddings/oleObject1.bin"

    def test_bin_mal_forme_ignore(self):
        for octets in (olefile.MAGIC + b"\xff" * 600, olefile.MAGIC, b"pas un zip"):
            self.assertIsNone(I.extraire(paquet({self.cible: octets}), objet(self.cible)))

    def test_ole10_tronque_ignore(self):
        b = ole2({"\x01Ole10Native": b"\x05"})
        self.assertIsNone(I.extraire(paquet({self.cible: b}), objet(self.cible, "Package")))

    def test_bombe_zip_refusee(self):
        bombe = ooxml("xl/workbook.xml", bourrage=20 * 1024 * 1024)
        self.assertIsNone(I.taille_zip_sure(bombe))
        cible = "ppt/embeddings/bombe.xlsx"
        self.assertIsNone(I.extraire(paquet({cible: bombe}), objet(cible)))
        self.assertIsNone(I.extraire(paquet({self.cible: ole2({"Package": bombe})}),
                                     objet(self.cible)))

    def test_profondeur(self):
        cible = "xl/embeddings/doc.docx"
        z = paquet({cible: ooxml("word/document.xml")})
        self.assertIsNotNone(I.extraire(z, objet(cible, "Word.Document.12"), niveau=2))
        self.assertIsNone(I.extraire(z, objet(cible, "Word.Document.12"), niveau=3))

    def test_budget_cumule(self):
        cible = "ppt/embeddings/a.xlsx"
        z = paquet({cible: ooxml("xl/workbook.xml", bourrage=1000)})
        taille = I.taille_zip_sure(z.read(cible))
        budget = I.Budget(int(taille * 1.5))
        self.assertIsNotNone(I.extraire(z, objet(cible), budget=budget))
        self.assertIsNone(I.extraire(z, objet(cible), budget=budget))

    def test_lie_absent_et_non_traduisible(self):
        cible = "ppt/embeddings/a.xlsx"
        z = paquet({cible: ooxml("xl/workbook.xml")})
        self.assertIsNone(I.extraire(z, objet(cible, lie=True)))
        self.assertIsNone(I.extraire(z, objet("ppt/embeddings/b.xlsx", present=True)))
        self.assertIsNone(I.extraire(z, objet(cible, present=False)))
        visio = "ppt/embeddings/schema.vsdx"
        self.assertIsNone(I.extraire(paquet({visio: ooxml("visio/document.xml")}),
                                     objet(visio, "Visio.Drawing.15")))


class EcritureCFB(unittest.TestCase):
    def test_gros_flux_avec_difat_et_dossier(self):
        gros = bytes(range(256)) * (9 * 1024 * 1024 // 256)    # > 109 secteurs FAT
        sous = I._Noeud("ObjectPool", 1, b"\0" * 16, 0, 0, 0, enfants=[
            I._Noeud("petit", I._FLUX, b"\0" * 16, 0, 0, 0, b"abc")])
        racine_ = I._Noeud("Root Entry", I._RACINE, b"\0" * 16, 0, 0, 0, enfants=[
            I._Noeud("Gros", I._FLUX, b"\0" * 16, 0, 0, 0, gros), sous,
            I._Noeud("vide", I._FLUX, b"\0" * 16, 0, 0, 0, b"")])
        flux = relire(I._ecrire_cfb(racine_))
        self.assertEqual(flux, {"Gros": gros, "ObjectPool/petit": b"abc", "vide": b""})

    def test_nombreux_freres_arbre_equilibre(self):
        noms = {"f%03d" % i: bytes([i]) * (i * 50) for i in range(60)}
        self.assertEqual(relire(ole2(noms)), noms)


class RemplacerParties(unittest.TestCase):
    def test_rien_a_remplacer_puis_une_partie(self):
        z = paquet({"a.xml": b"<a/>", "ppt/embeddings/x.bin": b"vieux", "z.xml": b"<z/>"})
        octets = z.fp.getvalue()
        self.assertIs(I.remplacer_parties(octets, {}), octets)
        self.assertIs(I.remplacer_parties(octets, {"absent": b"x"}), octets)
        neuf = zipfile.ZipFile(io.BytesIO(
            I.remplacer_parties(octets, {"ppt/embeddings/x.bin": b"neuf"})))
        self.assertEqual(neuf.namelist(), ["a.xml", "ppt/embeddings/x.bin", "z.xml"])
        self.assertEqual(neuf.read("ppt/embeddings/x.bin"), b"neuf")
        self.assertEqual(neuf.read("z.xml"), b"<z/>")


if __name__ == "__main__":
    unittest.main(verbosity=1)
