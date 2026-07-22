"""Version du moteur XLSX.

Le suivi part de **0.1.0**, et pas de 1.0.0 comme les trois autres moteurs :
le squelette accepte un classeur, le traverse et le réassemble, mais ne couvre
pas encore tout ce qu'un fichier Excel peut porter (voir `CONTEXTE.md`, section
« Ce qui n'est pas encore fait »).

Une version majeure dit « le contrat est stable ». Ici il ne l'est pas encore,
et l'annoncer en 1.0.0 ferait croire l'inverse à quiconque lit `/health`.

Il passera en 1.0.0 quand les chaînes en ligne, les graphiques et les tableaux
croisés dynamiques seront traités — c'est-à-dire quand un classeur quelconque
en ressortira traduit sans surprise.
"""

__version__ = "0.1.0"
