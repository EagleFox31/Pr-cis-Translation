"""Version du moteur DOCX (OOXML WordprocessingML).

Meme regle d'incrementation que les autres moteurs (cf. engines/pptx/version.py).
Le suivi repart de 1.0.0 le 22/07/2026.

ETAT A LA 1.0.0
  Extraction et reinjection par lxml directement sur le XML interne ; les noeuds
  <w:t> sont modifies EN PLACE (aucune suppression ni recreation de run, donc
  toute la mise en forme est preservee). Zones de texte, en-tetes et pieds de
  page pris en charge. Branche mc:Fallback filtree pour ne pas dedoubler le
  texte.

LIMITE CONNUE
  Pas de notion de PAGE a l'extraction : un plan limite en pages ne peut pas
  selectionner, et le format est refuse en amont pour ces plans.
"""

__version__ = "1.0.0"
