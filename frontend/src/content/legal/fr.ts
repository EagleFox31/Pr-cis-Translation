import type { LegalDoc } from './types';

export const LEGAL_UPDATED = '31 octobre 2026';

export const LEGAL_FR: LegalDoc[] = [
  {
    slug: 'mentions-legales',
    title: 'Mentions légales',
    intro:
      'Les informations ci-dessous identifient l\'éditeur et l\'hébergeur du site Précis, conformément à la réglementation applicable aux services en ligne.',
    sections: [
      {
        heading: 'Éditeur',
        paragraphs: [
          'Le site et le service Précis sont édités par Trigenys Group, un collectif de professionnels indépendants du numérique basé à Douala, au Cameroun. Trigenys Group n\'est pas une société immatriculée : les services sont fournis par les membres du collectif, qui agissent ensemble sous ce nom.',
          'Contact : contact@trigenys.com.',
        ],
      },
      {
        heading: 'Responsable de la publication',
        paragraphs: ['Le responsable de la publication est Trigenys Group.'],
      },
      {
        heading: 'Hébergement',
        paragraphs: [
          'Le service est hébergé par Amazon Web Services, Inc., 410 Terry Avenue North, Seattle, WA 98109, États-Unis. Les serveurs de Précis fonctionnent sur Amazon EC2.',
        ],
      },
      {
        heading: 'Site',
        paragraphs: ['Le service est accessible à l\'adresse https://precis-translator.trigenys.com.'],
      },
      {
        heading: 'Propriété intellectuelle',
        paragraphs: [
          'La marque Précis, l\'interface, les textes et la mascotte du site appartiennent à Trigenys Group. Toute reproduction, représentation ou réutilisation, totale ou partielle, est interdite sans son accord écrit préalable.',
          'Les documents que vous traduisez restent votre propriété, comme précisé dans les conditions d\'utilisation.',
        ],
      },
      {
        heading: 'Signaler un contenu ou un problème',
        paragraphs: [
          'Pour signaler un contenu, une erreur ou un dysfonctionnement, écrivez à contact@trigenys.com en décrivant la page concernée. Nous répondons dans les meilleurs délais.',
        ],
      },
    ],
  },
  {
    slug: 'conditions',
    title: 'Conditions d\'utilisation',
    intro:
      'Ces conditions encadrent l\'utilisation de Précis, un service de traduction de documents. Elles s\'appliquent dès la création de votre compte.',
    sections: [
      {
        heading: 'Objet et acceptation',
        paragraphs: [
          'Les présentes conditions définissent les règles d\'utilisation du service Précis, édité par Trigenys Group. En créant un compte, vous déclarez les avoir lues et vous les acceptez.',
        ],
      },
      {
        heading: 'Le service',
        paragraphs: [
          'Précis traduit des documents aux formats txt, pdf, docx, pptx et xlsx, dans la limite de 100 Mo par document, en s\'attachant à restituer fidèlement le sens et la mise en page d\'origine. Certains documents complexes (tableaux imbriqués, mises en page atypiques) peuvent présenter de légers écarts de présentation.',
          'La traduction repose sur un traitement automatisé que nous améliorons en continu. Comme toute traduction, elle peut ponctuellement comporter des imprécisions : si vous en constatez une, signalez-la à contact@trigenys.com afin que nous puissions la corriger et améliorer le service. Pour un usage officiel, juridique, médical ou contractuel, nous vous recommandons de faire relire le résultat avant de l\'utiliser.',
        ],
      },
      {
        heading: 'Compte',
        paragraphs: ['Pour utiliser le service, vous vous engagez à respecter les points suivants.'],
        list: [
          'fournir des informations exactes et les tenir à jour ;',
          'n\'ouvrir qu\'un seul compte, pour votre usage personnel ;',
          'garder votre mot de passe secret et nous prévenir en cas de compromission ;',
          'vérifier votre adresse e-mail : cette vérification est requise pour utiliser les pages gratuites.',
        ],
      },
      {
        heading: 'Offres et quotas',
        paragraphs: [
          'Précis propose une offre gratuite de 5 pages par mois, une offre Starter de 100 pages par mois et une offre Pro de 500 pages par mois. Le programme bêta dispose de quotas propres et d\'une durée limitée, précisés lors de l\'inscription au programme.',
          'Les prix en vigueur sont affichés sur le site avant tout paiement. Ils ne figurent pas dans ces conditions, car ils peuvent évoluer.',
          'L\'offre gratuite et le programme bêta sont financés en partie par une mention promotionnelle de Précis, intégrée à l\'aperçu des traductions. Elle s\'affiche pour les comptes gratuits et pour les bêta-testeurs ; un compte payant qui participe au programme bêta la voit uniquement sur les traductions réalisées avec ses crédits bêta. Cette mention ne fait appel à aucune régie publicitaire et n\'utilise aucune de vos données.',
          'Avec l\'offre gratuite, la traduction se consulte en aperçu. Le téléchargement du document traduit est ouvert aux offres payantes, aux pages achetées à l\'unité et aux participants du programme bêta.',
        ],
      },
      {
        heading: 'Paiement',
        paragraphs: [
          'Le paiement s\'effectue par Mobile Money via Campay ou Fapshi, ou par carte bancaire via Paddle. Pour les paiements par carte, Paddle agit en qualité de revendeur et de commerçant officiel (merchant of record).',
          'Les prix sont fixés par Précis et affichés, frais compris, avant votre confirmation. Les offres Starter et Pro sont payées pour une période donnée, sans renouvellement automatique : à l\'expiration, votre compte revient à l\'offre gratuite. Si vous changez d\'offre en cours de période, les jours restants sont convertis dans la nouvelle offre.',
          'Les pages achetées à l\'unité n\'expirent pas.',
        ],
      },
      {
        heading: 'Traduction interrompue',
        paragraphs: [
          'Si une traduction est interrompue, les pages qui n\'ont pas été traduites vous sont recréditées. En cas d\'erreur, toutes les pages du document vous sont recréditées. Vous pouvez reprendre la traduction sans être facturé deux fois pour les mêmes pages.',
        ],
      },
      {
        heading: 'Remboursements',
        paragraphs: [
          'Les pages consommées ne sont pas remboursables. En revanche, si vous avez été débité deux fois, ou si un paiement n\'a pas été appliqué à votre compte, il est remboursé sur demande adressée à contact@trigenys.com.',
          'Le remboursement est effectué par le moyen de paiement d\'origine lorsque le prestataire de paiement le permet.',
        ],
      },
      {
        heading: 'Usage acceptable et lutte contre les abus',
        paragraphs: ['Il est interdit d\'utiliser Précis pour les usages suivants.'],
        list: [
          'traduire un contenu illégal ;',
          'traduire un contenu sur lequel vous n\'avez aucun droit ;',
          'transmettre un logiciel malveillant ;',
          'contourner les quotas ou les limites du service ;',
          'ouvrir plusieurs comptes pour obtenir de façon répétée des pages gratuites ;',
          'envoyer des requêtes automatisées en masse ;',
          'utiliser une adresse e-mail jetable.',
        ],
      },
      {
        heading: 'Mesures contre les abus',
        paragraphs: [
          'Pour protéger le service, nous appliquons des limites de requêtes, une vérification anti-robot Cloudflare Turnstile et l\'analyse de signaux d\'appareil et de réseau, conservés sous forme hachée, afin de repérer les comptes gratuits ouverts à répétition.',
          'Lorsqu\'un abus est constaté, les pages gratuites peuvent être retenues. Les pages que vous avez payées restent toujours utilisables. Trigenys Group peut aussi refuser l\'accès à l\'offre gratuite ou au programme bêta en cas d\'abus.',
        ],
      },
      {
        heading: 'Vos documents',
        paragraphs: [
          'Vous conservez tous vos droits sur vos documents et sur leurs traductions. Vous nous accordez uniquement les droits nécessaires pour les traduire, les conserver et vous les afficher.',
          'Notre équipe peut ouvrir un document pour répondre à une demande d\'assistance, ou pour repérer d\'éventuelles imprécisions de traduction afin de les corriger et d\'améliorer le service. Cet accès est réservé à l\'équipe, chaque accès est journalisé, et le document n\'est jamais publié, vendu ni transmis en dehors des prestataires listés dans la politique de confidentialité. La suppression du document met fin à cet accès.',
          'Ne transmettez pas de documents que vous n\'avez pas le droit de partager.',
        ],
      },
      {
        heading: 'Disponibilité',
        paragraphs: [
          'Précis est un service en bêta, que nous enrichissons et améliorons régulièrement. Nous faisons le nécessaire pour qu\'il reste accessible en permanence ; il peut toutefois être brièvement interrompu, notamment pour maintenance ou mise à jour. En cas d\'incident, nous intervenons dans les meilleurs délais pour rétablir le service.',
        ],
      },
      {
        heading: 'Responsabilité',
        paragraphs: [
          'Dans la mesure permise par la loi, la responsabilité de Trigenys Group est limitée aux sommes que vous avez versées au cours des 12 derniers mois. Pour les usages sensibles évoqués plus haut, la relecture recommandée reste de votre ressort : Trigenys Group ne peut être tenu responsable de l\'utilisation d\'une traduction qui n\'a pas été relue.',
        ],
      },
      {
        heading: 'Modification des conditions',
        paragraphs: [
          'Les conditions en vigueur sont publiées sur cette page, avec leur date de mise à jour. Les changements importants sont annoncés par e-mail ou sur le site.',
        ],
      },
      {
        heading: 'Droit applicable',
        paragraphs: [
          'Les présentes conditions sont soumises au droit camerounais. En cas de litige, nous recherchons d\'abord une solution amiable en échangeant par e-mail à contact@trigenys.com. À défaut, le litige relève des tribunaux de Douala.',
        ],
      },
      {
        heading: 'Contact',
        paragraphs: ['Pour toute question sur ces conditions : contact@trigenys.com.'],
      },
    ],
  },
  {
    slug: 'confidentialite',
    title: 'Politique de confidentialité',
    intro:
      'Cette politique explique quelles données Précis collecte, pourquoi, combien de temps elles sont conservées et comment exercer vos droits.',
    sections: [
      {
        heading: 'Responsable du traitement',
        paragraphs: [
          'Le responsable du traitement de vos données est Trigenys Group, basé à Douala (Cameroun). Contact : contact@trigenys.com.',
        ],
      },
      {
        heading: 'Données collectées',
        paragraphs: ['Nous collectons uniquement les données nécessaires au fonctionnement du service.'],
        list: [
          'Compte : adresse e-mail, nom, mot de passe stocké sous forme hachée ; si vous vous connectez avec Google, votre identifiant et votre photo Google.',
          'Usage : offre, quotas, crédits de pages, documents envoyés et traductions.',
          'Paiement : numéro de téléphone Mobile Money et références de transaction. Les données de carte bancaire sont traitées par Paddle et ne sont jamais stockées par Précis.',
          'Sécurité : empreinte d\'appareil et adresse IP, stockées uniquement sous forme hachée.',
          'Assistance : vos messages et tickets.',
          'Journaux d\'erreurs techniques.',
        ],
      },
      {
        heading: 'Finalités',
        paragraphs: ['Vos données sont utilisées pour les finalités suivantes.'],
        list: [
          'fournir le service de traduction ;',
          'facturer et traiter les paiements ;',
          'assurer la sécurité du service et lutter contre les abus ;',
          'répondre à vos demandes d\'assistance ;',
          'améliorer la qualité des traductions, y compris par l\'examen de documents par notre équipe dans les conditions décrites dans les conditions d\'utilisation (article « Vos documents »).',
        ],
      },
      {
        heading: 'Prestataires',
        paragraphs: [
          'Pour faire fonctionner Précis, nous faisons appel aux prestataires suivants.',
        ],
        list: [
          'DeepSeek : reçoit le texte de vos documents afin de le traduire ;',
          'Amazon Web Services : hébergement ;',
          'Campay, Fapshi et Paddle : paiements ;',
          'Cloudflare Turnstile : vérification anti-robot ;',
          'Google : connexion avec Google, si vous la choisissez ;',
          'un service d\'envoi d\'e-mails.',
        ],
      },
      {
        heading: 'Transferts de données',
        paragraphs: [
          'Certains de ces prestataires peuvent traiter vos données en dehors du Cameroun.',
        ],
      },
      {
        heading: 'Conservation',
        paragraphs: ['Les durées de conservation sont les suivantes.'],
        list: [
          'Documents : jusqu\'à ce que vous les supprimiez.',
          'Fichiers temporaires de traduction : 7 jours au plus, pour permettre la reprise d\'une traduction.',
          'Signaux d\'appareil et d\'adresse IP du programme bêta : 30 jours.',
          'Données de compte : tant que le compte est actif.',
          'Justificatifs de paiement : aussi longtemps que la loi l\'exige.',
        ],
      },
      {
        heading: 'Sécurité',
        paragraphs: [
          'Les échanges avec le site sont chiffrés par HTTPS. Les mots de passe sont hachés avec bcrypt, les identifiants d\'appareil et d\'adresse IP sont hachés, et chaque accès de notre équipe à un document est journalisé.',
        ],
      },
      {
        heading: 'Vos droits',
        paragraphs: [
          'Conformément à la loi n° 2024/017 du 23 décembre 2024 relative à la protection des données à caractère personnel au Cameroun, vous pouvez demander l\'accès à vos données, leur rectification, leur suppression et vous opposer à certains traitements. La suppression de votre compte s\'obtient sur demande par e-mail.',
          'Écrivez à contact@trigenys.com : nous vous répondons dans un délai raisonnable.',
        ],
      },
      {
        heading: 'Pas de vente de données, pas de publicité ciblée',
        paragraphs: [
          'Nous ne vendons pas vos données et ne faisons appel à aucune régie publicitaire. Les aperçus de l\'offre gratuite et du programme bêta portent une mention promotionnelle de Précis, identique pour tous : elle n\'utilise aucune donnée personnelle ni aucun traceur.',
        ],
      },
      {
        heading: 'Modifications',
        paragraphs: [
          'Cette politique peut évoluer, par exemple en cas de changement de prestataire. La version en vigueur est toujours publiée sur cette page, avec sa date de mise à jour.',
        ],
      },
      {
        heading: 'Contact',
        paragraphs: ['Pour toute question sur vos données : contact@trigenys.com.'],
      },
    ],
  },
  {
    slug: 'cookies',
    title: 'Cookies',
    intro:
      'Cette page décrit les cookies et les données stockées dans votre navigateur par Précis, ainsi que les services tiers chargés par le site.',
    sections: [
      {
        heading: 'Ce que nous utilisons',
        paragraphs: [
          'Précis n\'utilise que ce qui est nécessaire au fonctionnement et à la sécurité du service. Nous n\'utilisons ni cookie publicitaire ni mesure d\'audience (la mention promotionnelle des aperçus gratuits et bêta est intégrée à l\'image et ne dépose aucun cookie) : aucun bandeau de consentement n\'est donc affiché.',
        ],
      },
      {
        heading: 'Cookies et stockage local',
        paragraphs: ['Voici les éléments déposés par Précis dans votre navigateur.'],
        list: [
          'precis_device : cookie de sécurité et de lutte contre les abus, conservé 12 mois.',
          'precis_beta_device : cookie de lutte contre les abus du programme bêta, conservé 30 jours.',
          'precis_tokens : stockage local du navigateur, qui maintient votre connexion, jusqu\'à votre déconnexion.',
          'precis_device_copy : stockage local de lutte contre les abus.',
        ],
      },
      {
        heading: 'Services tiers',
        paragraphs: [
          'Le site charge des services tiers qui peuvent déposer leurs propres cookies.',
        ],
        list: [
          'Cloudflare Turnstile : vérification anti-robot ;',
          'Paddle : paiement par carte ;',
          'Google : connexion avec Google et polices d\'écriture ;',
          'jsDelivr et cdnjs : ressources techniques.',
        ],
      },
      {
        heading: 'Empreinte d\'appareil',
        paragraphs: [
          'Une empreinte d\'appareil (FingerprintJS) est calculée uniquement lors d\'une traduction et lors d\'une candidature au programme bêta, à des fins de lutte contre les abus. Elle est conservée sous forme hachée.',
        ],
      },
      {
        heading: 'Gérer vos préférences',
        paragraphs: [
          'Les réglages de votre navigateur vous permettent de supprimer ces éléments à tout moment. Si vous les bloquez, la connexion ou la traduction peuvent ne plus fonctionner.',
        ],
      },
      {
        heading: 'Contact',
        paragraphs: ['Pour toute question : contact@trigenys.com.'],
      },
    ],
  },
];
