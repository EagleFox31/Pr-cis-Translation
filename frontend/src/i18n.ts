import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

import translationFR from './locales/fr/translation.json';

/**
 * Seul le français (langue de repli) est dans le paquet de départ : l'anglais
 * n'est téléchargé que pour qui le lit (navigateur en anglais, ou clic sur
 * « EN »). Les deux dictionnaires pesaient ensemble ~116 Ko sur chaque visite.
 */
let anglais: Promise<void> | null = null;
function chargerAnglais(): Promise<void> {
  anglais ??= import('./locales/en/translation.json').then((m) => {
    // `bindI18nStore: 'added'` ci-dessous : l'ajout redessine les textes.
    i18n.addResourceBundle('en', 'translation', m.default, true, true);
  });
  return anglais;
}

const estAnglais = (lng?: string) => !!lng && lng.startsWith('en');

i18n.on('languageChanged', (lng) => {
  if (estAnglais(lng)) void chargerAnglais();
});

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: { fr: { translation: translationFR } },
    partialBundledLanguages: true,
    fallbackLng: 'fr',
    interpolation: {
      escapeValue: false // react already safes from xss
    },
    react: { bindI18nStore: 'added' },
  });

/** Résolu quand la langue de départ est prête (immédiat en français). */
export const languePrete: Promise<void> = estAnglais(i18n.language) ? chargerAnglais() : Promise.resolve();

export default i18n;
