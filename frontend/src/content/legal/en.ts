import type { LegalDoc } from './types';

export const LEGAL_UPDATED = 'October 31, 2026';

export const LEGAL_EN: LegalDoc[] = [
  {
    slug: 'mentions-legales',
    title: 'Legal notice',
    intro:
      'The information below identifies the publisher and the host of the Précis website, in accordance with the rules that apply to online services.',
    sections: [
      {
        heading: 'Publisher',
        paragraphs: [
          'The Précis website and service are published by Trigenys Group, a collective of independent digital professionals based in Douala, Cameroon. Trigenys Group is not a registered company: the services are provided by the members of the collective, who act together under this name.',
          'Contact: contact@trigenys.com.',
        ],
      },
      {
        heading: 'Publication director',
        paragraphs: ['The person responsible for the publication is Trigenys Group.'],
      },
      {
        heading: 'Hosting',
        paragraphs: [
          'The service is hosted by Amazon Web Services, Inc., 410 Terry Avenue North, Seattle, WA 98109, United States. Précis servers run on Amazon EC2.',
        ],
      },
      {
        heading: 'Website',
        paragraphs: ['The service is available at https://precis-translator.trigenys.com.'],
      },
      {
        heading: 'Intellectual property',
        paragraphs: [
          'The Précis brand, the interface, the texts and the mascot of the site belong to Trigenys Group. Any reproduction, representation or reuse, in whole or in part, is prohibited without its prior written consent.',
          'The documents you translate remain yours, as set out in the terms of use.',
        ],
      },
      {
        heading: 'Reporting content or a problem',
        paragraphs: [
          'To report content, an error or a malfunction, write to contact@trigenys.com and describe the page concerned. We reply as soon as we can.',
        ],
      },
    ],
  },
  {
    slug: 'conditions',
    title: 'Terms of use',
    intro:
      'These terms govern the use of Précis, a document translation service. They apply as soon as you create your account.',
    sections: [
      {
        heading: 'Purpose and acceptance',
        paragraphs: [
          'These terms set out the rules for using the Précis service, published by Trigenys Group. By creating an account, you confirm that you have read them and you accept them.',
        ],
      },
      {
        heading: 'The service',
        paragraphs: [
          'Précis translates documents in txt, pdf, docx, pptx and xlsx formats, up to 100 MB per document, with care taken to faithfully render the meaning and the original layout. Some complex documents (nested tables, unusual layouts) may show minor differences in presentation.',
          'Translation relies on an automated process that we continuously improve. Like any translation, it may occasionally contain inaccuracies: if you notice one, report it to contact@trigenys.com so that we can correct it and improve the service. For official, legal, medical or contractual use, we recommend having the result reviewed before using it.',
        ],
      },
      {
        heading: 'Account',
        paragraphs: ['To use the service, you agree to the following.'],
        list: [
          'provide accurate information and keep it up to date;',
          'open only one account, for your own use;',
          'keep your password secret and tell us if it is compromised;',
          'verify your e-mail address: this verification is required to use the free pages.',
        ],
      },
      {
        heading: 'Plans and quotas',
        paragraphs: [
          'Précis offers a free plan of 5 pages per month, a Starter plan of 100 pages per month and a Pro plan of 500 pages per month. The beta program has its own quotas and a limited duration, stated when you join the program.',
          'Current prices are shown on the site before any payment. They are not listed in these terms because they may change.',
          'The free plan and the beta programme are partly funded by a promotional mention of Précis, included in translation previews. It is shown to free accounts and to beta testers; a paid account taking part in the beta programme only sees it on translations made with its beta credits. This mention involves no advertising network and uses none of your data.',
          'On the free plan, the translation can be viewed as a preview. Downloading the translated document is available with paid plans, pages bought one by one and to beta programme participants.',
        ],
      },
      {
        heading: 'Payment',
        paragraphs: [
          'Payment is made by Mobile Money through Campay or Fapshi, or by card through Paddle. For card payments, Paddle acts as reseller and merchant of record.',
          'Prices are set by Précis and displayed, fees included, before you confirm. The Starter and Pro plans are paid for a given period, with no automatic renewal: when it ends, your account returns to the free plan. If you change plan during a period, the remaining days are converted into the new plan.',
          'Pages bought one by one do not expire.',
        ],
      },
      {
        heading: 'Interrupted translation',
        paragraphs: [
          'If a translation is interrupted, the pages that were not translated are credited back to you. If an error occurs, all the pages of the document are credited back. You can resume the translation without being billed twice for the same pages.',
        ],
      },
      {
        heading: 'Refunds',
        paragraphs: [
          'Pages that have been used are not refundable. However, if you were charged twice, or if a payment was not applied to your account, it is refunded on request to contact@trigenys.com.',
          'The refund is made through the original payment method when the payment provider allows it.',
        ],
      },
      {
        heading: 'Acceptable use and abuse prevention',
        paragraphs: ['You may not use Précis for any of the following.'],
        list: [
          'translating illegal content;',
          'translating content you have no rights to;',
          'uploading malware;',
          'bypassing the quotas or limits of the service;',
          'opening several accounts to repeatedly obtain free pages;',
          'sending automated requests in bulk;',
          'using a disposable e-mail address.',
        ],
      },
      {
        heading: 'Measures against abuse',
        paragraphs: [
          'To protect the service, we apply request rate limits, a Cloudflare Turnstile anti-bot check, and the analysis of device and network signals, stored in hashed form, in order to detect free accounts opened repeatedly.',
          'When abuse is detected, free pages may be withheld. The pages you have paid for always remain usable. Trigenys Group may also refuse access to the free plan or to the beta program in case of abuse.',
        ],
      },
      {
        heading: 'Your documents',
        paragraphs: [
          'You keep all your rights over your documents and their translations. You grant us only the rights needed to translate them, store them and show them to you.',
          'Our team may open a document to answer a support request, or to identify possible translation inaccuracies so that we can correct them and improve the service. This access is restricted to the team, each access is logged, and the document is never published, sold or shared outside the service providers listed in the privacy policy. Deleting the document ends this access.',
          'Do not upload documents that you are not allowed to share.',
        ],
      },
      {
        heading: 'Availability',
        paragraphs: [
          'Précis is a beta service that we regularly enrich and improve. We do what is needed to keep it available at all times; it may however be briefly interrupted, in particular for maintenance or updates. If an incident occurs, we act as quickly as possible to restore the service.',
        ],
      },
      {
        heading: 'Liability',
        paragraphs: [
          'To the extent permitted by law, the liability of Trigenys Group is limited to the amounts you paid over the last 12 months. For the sensitive uses mentioned above, the recommended review remains your responsibility: Trigenys Group cannot be held liable for the use of a translation that has not been reviewed.',
        ],
      },
      {
        heading: 'Changes to the terms',
        paragraphs: [
          'The current terms are published on this page, with their update date. Important changes are announced by e-mail or on the site.',
        ],
      },
      {
        heading: 'Governing law',
        paragraphs: [
          'These terms are governed by Cameroonian law. In case of a dispute, we first look for an amicable solution by e-mail at contact@trigenys.com. Failing that, the dispute falls under the jurisdiction of the courts of Douala.',
        ],
      },
      {
        heading: 'Contact',
        paragraphs: ['For any question about these terms: contact@trigenys.com.'],
      },
    ],
  },
  {
    slug: 'confidentialite',
    title: 'Privacy policy',
    intro:
      'This policy explains what data Précis collects, why, how long it is kept and how to exercise your rights.',
    sections: [
      {
        heading: 'Data controller',
        paragraphs: [
          'The controller of your data is Trigenys Group, based in Douala (Cameroon). Contact: contact@trigenys.com.',
        ],
      },
      {
        heading: 'Data we collect',
        paragraphs: ['We only collect the data needed for the service to work.'],
        list: [
          'Account: e-mail address, name, password stored in hashed form; if you sign in with Google, your Google identifier and photo.',
          'Usage: plan, quotas, page credits, uploaded documents and translations.',
          'Payment: Mobile Money phone number and transaction references. Card data is handled by Paddle and is never stored by Précis.',
          'Security: device fingerprint and IP address, stored only in hashed form.',
          'Support: your messages and tickets.',
          'Technical error logs.',
        ],
      },
      {
        heading: 'Purposes',
        paragraphs: ['Your data is used for the following purposes.'],
        list: [
          'providing the translation service;',
          'billing and processing payments;',
          'keeping the service secure and preventing abuse;',
          'answering your support requests;',
          'improving translation quality, including the review of documents by our team as described in the terms of use (article "Your documents").',
        ],
      },
      {
        heading: 'Service providers',
        paragraphs: ['To run Précis, we rely on the following service providers.'],
        list: [
          'DeepSeek: receives the text of your documents in order to translate it;',
          'Amazon Web Services: hosting;',
          'Campay, Fapshi and Paddle: payments;',
          'Cloudflare Turnstile: anti-bot check;',
          'Google: sign-in with Google, if you choose it;',
          'an e-mail sending service.',
        ],
      },
      {
        heading: 'Data transfers',
        paragraphs: [
          'Some of these providers may process your data outside Cameroon.',
        ],
      },
      {
        heading: 'Retention',
        paragraphs: ['Retention periods are as follows.'],
        list: [
          'Documents: until you delete them.',
          'Temporary translation files: 7 days at most, so that a translation can be resumed.',
          'Beta program device and IP signals: 30 days.',
          'Account data: as long as the account is active.',
          'Payment records: as long as the law requires.',
        ],
      },
      {
        heading: 'Security',
        paragraphs: [
          'Exchanges with the site are encrypted with HTTPS. Passwords are hashed with bcrypt, device and IP identifiers are hashed, and every access by our team to a document is logged.',
        ],
      },
      {
        heading: 'Your rights',
        paragraphs: [
          'Under Law No. 2024/017 of 23 December 2024 on the protection of personal data in Cameroon, you may request access to your data, its correction or its deletion, and object to certain processing. Your account can be deleted on request by e-mail.',
          'Write to contact@trigenys.com: we reply within a reasonable time.',
        ],
      },
      {
        heading: 'No sale of data, no targeted advertising',
        paragraphs: [
          'We do not sell your data and we use no advertising network. Previews on the free plan and the beta programme carry a promotional mention of Précis, identical for everyone: it uses no personal data and no tracker.',
        ],
      },
      {
        heading: 'Changes',
        paragraphs: [
          'This policy may change, for example if we change a service provider. The current version is always published on this page, with its update date.',
        ],
      },
      {
        heading: 'Contact',
        paragraphs: ['For any question about your data: contact@trigenys.com.'],
      },
    ],
  },
  {
    slug: 'cookies',
    title: 'Cookies',
    intro:
      'This page describes the cookies and data that Précis stores in your browser, and the third-party services loaded by the site.',
    sections: [
      {
        heading: 'What we use',
        paragraphs: [
          'Précis only uses what is necessary for the service to work and to stay secure. We use no advertising cookies and no audience measurement (the promotional mention on free and beta previews is part of the image and sets no cookie), so no consent banner is displayed.',
        ],
      },
      {
        heading: 'Cookies and local storage',
        paragraphs: ['These are the items Précis places in your browser.'],
        list: [
          'precis_device: security and abuse-prevention cookie, kept for 12 months.',
          'precis_beta_device: abuse-prevention cookie for the beta program, kept for 30 days.',
          'precis_tokens: browser local storage that keeps you signed in, until you sign out.',
          'precis_device_copy: local storage used for abuse prevention.',
        ],
      },
      {
        heading: 'Third-party services',
        paragraphs: [
          'The site loads third-party services that may set their own cookies.',
        ],
        list: [
          'Cloudflare Turnstile: anti-bot check;',
          'Paddle: card payment;',
          'Google: sign-in with Google and web fonts;',
          'jsDelivr and cdnjs: technical resources.',
        ],
      },
      {
        heading: 'Device fingerprint',
        paragraphs: [
          'A device fingerprint (FingerprintJS) is computed only during a translation and when applying to the beta program, for abuse prevention. It is stored in hashed form.',
        ],
      },
      {
        heading: 'Managing your preferences',
        paragraphs: [
          'Your browser settings let you delete these items at any time. If you block them, signing in or translating may stop working.',
        ],
      },
      {
        heading: 'Contact',
        paragraphs: ['For any question: contact@trigenys.com.'],
      },
    ],
  },
];
