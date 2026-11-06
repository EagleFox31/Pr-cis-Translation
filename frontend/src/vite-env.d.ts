/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Identifiants et adresses de boutique de l'extension navigateur (vides = pas encore publiée). */
  readonly VITE_EXTENSION_ID_CHROME?: string;
  readonly VITE_EXTENSION_ID_EDGE?: string;
  readonly VITE_EXTENSION_URL_CHROME?: string;
  readonly VITE_EXTENSION_URL_EDGE?: string;
}
