"""Version du BACKEND (API, services, socle).

Ce numero couvre l'application : routes, services, modeles, migrations. Il ne
couvre PAS les moteurs, qui portent chacun le leur -- corriger le rendu d'un
PPTX ne change rien a l'API, et l'inverse est vrai aussi.

QUAND L'INCREMENTER
  * patch (1.0.x) -- correctif sans effet visible sur le contrat HTTP.
  * mineure (1.x.0) -- route ajoutee, champ ajoute, comportement etendu de
    facon compatible.
  * majeure (x.0.0) -- rupture du contrat HTTP : route retiree ou renommee,
    champ supprime, semantique changee. Le frontend doit suivre.

Le suivi repart de 1.0.0 le 22/07/2026.
"""

# 1.1.0 -- CORS restreint aux origines declarees, plafonds de debit sur les
#          routes d'authentification, 503 parlant sur panne SMTP. Le contrat
#          HTTP s'etend (nouveaux 429 et 503) sans rien retirer.
__version__ = "1.1.0"
