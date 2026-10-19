# OCR des PDF scannés

Le service reconnaît automatiquement les pages sélectionnées sans texte
extractible, avant la consommation de pages et l'appel au traducteur. Tesseract
tourne localement, avec les modèles français, anglais et détection d'orientation.
Les pages numériques et les pages hors sélection sont conservées.

## Limites et contrôle utilisateur

- Texte imprimé français et anglais ; pas de prise en charge des manuscrits.
- Dix pages scannées maximum par demande ; 12 millions de pixels par page,
  un seul OCR simultané, 30 secondes par reconnaissance et budget global de
  90 secondes. La détection d'orientation a un délai distinct de 10 secondes.
- Les scans illisibles ou trop incertains sont refusés avant tout débit.
- Les polices et la composition sont approximatives. Le fond est conservé,
  les boîtes des mots reconnus sont masquées puis réécrites. Une signature ou
  un tampon superposé au texte peut être affecté : l'interface demande de
  vérifier le résultat. Ne pas présenter le résultat comme une copie certifiée.
- Un supplément OCR n'est pas activé : les tarifs et consommations existants
  restent applicables. Un montant et sa confirmation avant débit doivent être
  définis avant d'ajouter une tarification spécifique.

## Persistance et reprise

L'original déposé reste intact. La copie reconnue est enregistrée à côté du
JSON traduit sous `<traduction>.json.source.pdf`. Le suffixe `ocrv1` sépare les
caches OCR des caches des PDF numériques. La réouverture utilise cette source
et le JSON, sans nouvelle reconnaissance ni nouvel appel IA ; une source OCR
manquante produit une erreur explicite. Le magasin et ses sauvegardes incluent
cette copie. Sa purge suit celle du JSON ou de la racine du document.

## Vérification

`test_ocr.py` utilise Tesseract réellement : scan horizontal et tourné, fond
coloré, sceau hors texte, page numérique intacte, passage au rendu traduit,
original intact, réouverture et refus d'une page blanche. Le test d'endpoint
contrôle l'acceptation, le cache et la consommation d'une seule page sélectionnée.
`test_documents_scannes.py` garde le contrôle du solde après un échec OCR.
