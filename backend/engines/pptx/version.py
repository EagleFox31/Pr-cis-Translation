"""Version du moteur PPTX (OOXML PresentationML).

QUAND L'INCREMENTER
  * patch (1.0.x) -- correctif de fidelite : balises de runs, apercus OLE,
    injection, extraction. Tout ce qui peut changer le document produit.
  * mineure (1.x.0) -- capacite nouvelle sans rupture (nouveau type de forme
    pris en charge, nouveau filtre d'extraction).
  * majeure (x.0.0) -- le contrat `extract_text` / `inject_translation` change.

Le suivi repart de 1.0.0 le 22/07/2026.

ETAT A LA 1.0.0
  Contrat de balises de runs avec invariants SANS SEUIL (cf. engines/runtags.py),
  glossaire de document, layouts et masques extraits une seule fois, apercus OLE
  Excel regeneres depuis le classeur traduit et rendus TRANSPARENTS, apercu
  progressif diapositive par diapositive.
"""

__version__ = "1.0.0"
