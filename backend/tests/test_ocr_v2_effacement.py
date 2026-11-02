"""Effacement du texte d'une image (OCR v2, étude §6 et §8).

Chaque cas fabrique un fond connu, y écrit un mot, efface, puis compare au fond
d'origine. Le banc complet (textures, 108 zones, ~2 min) est à part :
`backend/tests/banc_effacement.py` ; on en reprend ici deux cas courts.

    backend/venv/Scripts/python.exe backend/tests/test_ocr_v2_effacement.py
"""
import time

import racine  # noqa: F401
import cv2
import numpy as np
from app.services.ocr_v2.erase import effacer
from banc_effacement import generer, psnr_zone, rect, traits_conserves

H, W = 120, 420
BOITE = (85, 30, 260, 72)


def degrade(h=H, w=W):
    x = np.linspace(0, 1, w)[None, :, None]
    return (np.array([200, 160, 120]) * (1 - x) + np.array([120, 200, 230]) * x).repeat(h, 0).astype(np.uint8)


def ecrire(fond):
    img = fond.copy()
    cv2.putText(img, "Bonjour", (90, 80), cv2.FONT_HERSHEY_SIMPLEX, 2, (30, 30, 30), 5, cv2.LINE_AA)
    return img


def psnr(a, b):
    mse = np.mean((a.astype(np.float32) - b.astype(np.float32)) ** 2)
    return 99.0 if mse == 0 else 10 * np.log10(255 ** 2 / mse)


def pixels_faux(a, b):
    return int((np.abs(a.astype(int) - b.astype(int)).max(2) > 30).sum())


def cas_degrade():
    fond = degrade()
    out, choix = effacer(ecrire(fond), [BOITE])
    db = psnr(out, fond)
    assert db >= 40, (choix, db)
    print(f"  dégradé : {choix[0]}, {db:.1f} dB")


def cas_trait_traversant():
    # Un trait rouge passe SOUS les lettres : il doit être reconstruit là où
    # elles le recouvraient. Les positions fantômes, décalées hors de la zone,
    # ne voient pas le trait ; la règle doit primer.
    fond = degrade()
    cv2.line(fond, (0, 60), (W - 1, 60), (0, 0, 220), 3)
    out, choix = effacer(ecrire(fond), [BOITE])
    assert choix[0].startswith("structurel"), choix
    faux = pixels_faux(out, fond)
    assert faux == 0, (choix, faux)
    print(f"  trait traversant : {choix[0]}, {faux} px faux")


def cas_texture():
    # Fond bruité, assez grand pour que le fantôme trouve où se poser : aucun
    # trait ne doit y être inventé, et l'effacement doit rester proche du fond.
    rng = np.random.default_rng(0)
    fond = np.clip(degrade(3 * H, 2 * W).astype(np.float32) + rng.normal(0, 12, (3 * H, 2 * W, 1)),
                   0, 255).astype(np.uint8)
    fond = cv2.GaussianBlur(fond, (3, 3), 0)
    img = ecrire(fond)
    out, choix = effacer(img, [BOITE])
    assert not choix[0].startswith("structurel") and "règle" not in choix[0], choix
    db = psnr(out, fond)
    assert db >= psnr(img, fond) + 15, (choix, db)
    print(f"  texture : {choix[0]}, {db:.1f} dB")


def cas_banc():
    # Flèche droite sous « Signal input » : 100 % du trait gardé ; fond uni ≥ 40 dB.
    cas = generer("schema_fleche")
    out, choix = effacer(cas["image"], cas["boites"][:1])
    garde = traits_conserves(out, cas["fond"], cas["traits"], rect(cas["boites"][0]))
    assert garde == 1.0, (choix, garde)
    cas = generer("uni")
    out, choix = effacer(cas["image"], cas["boites"])
    db = min(psnr_zone(out, cas["fond"], rect(b)) for b in cas["boites"])
    assert db >= 40, (choix, db)
    print(f"  banc : flèche 100 % gardée, uni {db:.1f} dB")


def main():
    debut = time.monotonic()
    for cas in (cas_degrade, cas_trait_traversant, cas_texture, cas_banc):
        cas()
    print(f"OK effacement ({time.monotonic() - debut:.1f} s)")


if __name__ == "__main__":
    main()
