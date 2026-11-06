/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Identifiants et adresses de boutique de l'extension navigateur (vides = pas encore publiée). */
  readonly VITE_EXTENSION_ID_CHROME?: string;
  readonly VITE_EXTENSION_ID_EDGE?: string;
  readonly VITE_EXTENSION_URL_CHROME?: string;
  readonly VITE_EXTENSION_URL_EDGE?: string;
  /** Adresse du ZIP d'installation manuelle (défaut : /extension/precis-extension.zip). */
  readonly VITE_EXTENSION_ZIP_URL?: string;
}

/** Version du ZIP d'installation manuelle, injectée au build (vite.config.ts). */
declare const __EXTENSION_VERSION__: string;
