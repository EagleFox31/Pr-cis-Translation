// Adresses injectées par `node build.mjs --prod` ; à défaut, poste de développement.
declare const __PRECIS_API__: string | undefined;
declare const __PRECIS_SITE__: string | undefined;

export const API_BASE: string = typeof __PRECIS_API__ === "string" ? __PRECIS_API__ : "http://localhost:8000";

// Site public : tarifs, page de l'extension, seule origine admise à interroger l'extension.
export const SITE: string = typeof __PRECIS_SITE__ === "string" ? __PRECIS_SITE__ : "http://localhost:3000";
export const SITE_TARIFS = SITE + "/home#pricing";
export const SITE_BIENVENUE = SITE + "/extension?bienvenue=1";
