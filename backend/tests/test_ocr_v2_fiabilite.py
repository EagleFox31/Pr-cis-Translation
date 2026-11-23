"""Fiabilité d'un scan (étude OCR v2 §7.6) : lignes douteuses écartées,
colonnes séparées, seconde lecture en complément. Sans Tesseract.

    backend/venv/Scripts/python.exe backend/tests/test_ocr_v2_fiabilite.py
"""
import racine  # noqa: F401
from app.services.ocr_v2.detect import Mot, completer, lignes_fiables


def mot(texte, x, conf=95, ligne=(1, 1, 1), y=100, h=20):
    return Mot(texte, (x, y, 10 * len(texte), h), conf, ligne)


def textes(mots):
    lignes = {}
    for m in mots:
        lignes.setdefault(m.ligne, []).append(m.texte)
    return [" ".join(t) for t in lignes.values()]


def cas_ligne_saine():
    garde, ecartees = lignes_fiables([mot("Le", 0), mot("permis", 30), mot("B", 100)])
    assert textes(garde) == ["Le permis B"] and ecartees == 0, (textes(garde), ecartees)
    print("  ligne saine gardée")


def cas_ligne_douteuse():
    # Un mot lu à 0 au milieu (« ecioge:de ») : les mots isolés autour restent en image.
    lu = [mot("cree", 0), mot("ecioge:de", 50, conf=0), mot("force", 150)]
    assert lignes_fiables(lu) == ([], 2)
    # Moyenne trop basse, aucun mot sous 50.
    assert lignes_fiables([mot("Ue", 0, conf=66), mot("AUTRE", 30, conf=67)]) == ([], 1)
    # Une seule lettre : rien à traduire.
    assert lignes_fiables([mot("a", 0)]) == ([], 1)
    print("  ligne douteuse, trop faible ou sans texte : écartée")


def cas_fragment():
    # Bruit en tête (« LE » à 32) : la phrase sûre qui suit est gardée.
    lu = [mot("=.", 0, conf=40), mot("a", 30, conf=72), mot("LE", 50, conf=32),
          mot("Vous", 80), mot("devez", 130), mot("ralentir", 200)]
    garde, ecartees = lignes_fiables(lu)
    assert textes(garde) == ["Vous devez ralentir"] and ecartees == 0, (textes(garde), ecartees)
    print("  ligne coupée au mot douteux, fragment sûr gardé")


def cas_rognage():
    # Bruit de photo aux deux bouts (« |_ », « ka LL » sous 60) : rogné, la phrase reste.
    lu = [mot("|_", 0, conf=90), mot("Vous", 30), mot("pouvez", 80), mot("ka", 150, conf=30), mot("LL", 180, conf=22)]
    garde, ecartees = lignes_fiables(lu)
    assert textes(garde) == ["Vous pouvez"] and ecartees == 0, textes(garde)
    print("  bruit en bout de ligne rogné")


def cas_colonnes():
    # Deux colonnes séparées par une photo (blanc de 300 px pour des mots de 20 px).
    lu = [mot("voir", 0), mot("la", 50), mot("liquide", 400), mot("frein", 480)]
    garde, _ = lignes_fiables(lu)
    assert textes(garde) == ["voir la", "liquide frein"], textes(garde)
    # Une colonne douteuse n'emporte pas l'autre.
    lu = [mot("voir", 0), mot("la", 50), mot("rw", 400, conf=6), mot("ers", 440, conf=40), mot("xx", 480, conf=55)]
    assert textes(lignes_fiables(lu)[0]) == ["voir la"]
    print("  ligne à cheval sur deux colonnes coupée")


def cas_completer():
    premiere = [mot("Le", 0), mot("permis", 30)]
    seconde = [mot("Le", 2, ligne=(1, 1, 1)), mot("ENTRETIEN", 0, y=10, ligne=(1, 1, 1))]
    tout = completer(premiere, seconde)
    assert [m.texte for m in tout] == ["Le", "permis", "ENTRETIEN"], tout
    # Clés de ligne distinctes : le titre ajouté ne rejoint pas une ligne de la première lecture.
    assert tout[2].ligne != tout[0].ligne
    assert textes(lignes_fiables(tout)[0]) == ["Le permis", "ENTRETIEN"]
    print("  seconde lecture : seuls les mots nouveaux sont ajoutés")


def main():
    cas_ligne_saine()
    cas_ligne_douteuse()
    cas_fragment()
    cas_rognage()
    cas_colonnes()
    cas_completer()
    print("PASS: fiabilité des lignes de scan")


if __name__ == "__main__":
    main()
