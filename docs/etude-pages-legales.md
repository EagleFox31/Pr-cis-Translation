# Étude : pages légales

## 1. Besoin
Les liens « Mentions légales », « CGU » et « Confidentialité » du pied de page mènent à `#`. Il faut quatre pages réelles, en français et en anglais : Mentions légales, Conditions d'utilisation (anti-abus, paiement, usage des documents), Confidentialité, Cookies. Elles doivent renforcer la crédibilité, pas l'entamer.

Critères d'acceptation :
- Chaque règle écrite correspond à ce que fait le code (références ci-dessous) ; aucune promesse invérifiable.
- Aucun champ vide ou « à compléter » visible.
- Le statut réel est dit simplement : Trigenys Group est un collectif d'indépendants, pas une société immatriculée.
- Lecture confortable sur 1266 px et 390 px, jetons du site, fr/en.

## 2. Existant (faits relevés dans le code)
| Sujet | Constat |
|---|---|
| Anti-abus | Limites de requêtes (`rate_limit.py`, 3–30/min) ; Turnstile à l'inscription et à la connexion ; e-mail vérifié exigé pour les pages gratuites ; `anti_abus.py` : multi-comptes détectés (appareil, IP hachée, boîtes jetables), **retient seulement les pages gratuites, ne bloque jamais les pages payées** ; aucune suspension de compte dans le code. |
| Limites | 100 Mo, txt/pdf/docx/pptx/xlsx (`config.py:124`) ; quotas mensuels 5/100/500/illimité (`plans.py`) ; bêta : quotas par format, 30 jours, un seul accès par boîte (`beta_meter.py`, `beta.py`). |
| Paiement | Campay et Fapshi (Mobile Money), Paddle (carte). Plans Starter/Pro payés par période, **sans renouvellement automatique** ; pages à l'unité (`page_credits`, sans expiration). Prix fixés côté serveur (`pricing.py`), frais affichés (3 % Mobile Money ; carte 5 % + fixe). Pas de remboursement automatique : paiement non appliqué → `refund_due` traité à la main. |
| Traduction interrompue | Pages non traduites recréditées, erreur = tout recrédité, reprise sans double facturation (`jobs.py:384`, `usage.py:114`). |
| Documents | Disque du serveur (AWS EC2), pas de suppression automatique ; suppression par l'utilisateur (`documents.py:621`) ; **l'équipe peut ouvrir les documents, chaque accès est journalisé** (`admin_documents.py`) ; texte envoyé à DeepSeek pour la traduction ; OCR local. Pas de suppression de compte en libre-service. |
| Données | E-mail, nom, mot de passe haché (bcrypt), Google, plan, crédits, téléphone du paiement ; empreintes d'appareil et IP hachées ; journaux d'erreurs, tickets. Aucun outil d'analyse d'audience. |
| Cookies | `precis_device` (365 j) et `precis_beta_device` (30 j), anti-abus ; jetons de session en localStorage ; FingerprintJS à la traduction et à la candidature bêta ; tiers : Google Fonts, jsDelivr, cdnjs, Paddle.js, Turnstile, Google Sign-In. |
| Inscription | Aucune acceptation des conditions, aucun âge minimum. |
| Site | Domaine precis-translator.trigenys.com ; hébergement AWS EC2. |

## 3. Options
| Option | Pour | Contre |
|---|---|---|
| A. Textes dans les dictionnaires i18n | Mécanisme existant | Des centaines de lignes de droit dans `translation.json`, illisibles à relire |
| B. **Une page de lecture commune, textes dans `content/legal/{fr,en}.ts` (sections structurées)** | Un seul gabarit soigné, textes relisibles par un juriste, navigation entre les 4 documents | Un fichier de contenu par langue à tenir à jour |
| C. Générateur de CGU externe | Rapide | Textes génériques, faux sur les points propres à Précis (anti-abus, relecture) |

## 4. Recommandation : option B
Routes `/mentions-legales`, `/conditions`, `/confidentialite`, `/cookies`, un composant `LegalPage`. Sur ordinateur, sommaire des 4 documents à gauche, texte justifié à droite ; sur mobile, onglets défilants en haut. Pied de page : 4 liens. Inscription : une ligne « En créant un compte, vous acceptez les Conditions d'utilisation et la Politique de confidentialité » (liens), sans case à cocher.

## 5. Points décidés par défaut (modifiables)
1. **Éditeur** : « Trigenys Group, collectif de professionnels indépendants du numérique, Douala (Cameroun) », contact `contact@trigenys.com` ; responsable de la publication : Trigenys Group. Hébergeur : Amazon Web Services.
2. **Remboursement** : pages consommées non remboursables ; double débit ou paiement non appliqué remboursé sur demande ; crédits de pages sans date d'expiration ; plans sans renouvellement automatique.
3. **Relecture des documents** : l'équipe peut ouvrir un document pour l'assistance ou pour repérer les erreurs de traduction et améliorer le service ; accès réservé, journalisé, jamais publié ni revendu ; supprimer le document y met fin.
4. **Conservation** : documents gardés jusqu'à leur suppression par l'utilisateur ; compte supprimé sur demande par e-mail.
5. **Âge** : 18 ans, ou accord d'un parent.
6. **Cookies** : uniquement nécessaires (sécurité, anti-abus, session) ; pas de publicité ni de mesure d'audience, donc pas de bandeau de consentement.
7. **Droit** : droit camerounais (loi n° 2010/012 sur la cybersécurité, loi n° 2024/017 sur les données personnelles), règlement amiable puis tribunaux de Douala.

## 6. Impacts et risques
- Code : `App.tsx` (routes), `LegalPage.tsx`, `content/legal/*.ts`, `legal.css`, pied de page, `RegisterPage.tsx`, locales (`footer.*`, `legal.*`). Serveur : aucun.
- Risque juridique : textes rédigés sans juriste → **relecture par un juriste avant l'ouverture publique**.
- À tenir à jour à chaque changement de prestataire, de prix ou de règle anti-abus.
