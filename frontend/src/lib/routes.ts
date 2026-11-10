// Chargeurs des pages chargées à la demande. Un seul import par page : React
// (`lazy`), le démarrage (page d'arrivée) et le préchargement à l'intention
// partagent la même promesse, donc le même fichier téléchargé une fois.

type Chargeur = () => Promise<{ default: React.ComponentType<any> }>;

function memo(charger: Chargeur): Chargeur {
  let p: ReturnType<Chargeur> | undefined;
  return () => (p ??= charger().catch((e) => { p = undefined; throw e; }));
}

export const pages = {
  login: memo(() => import('../pages/LoginPage')),
  register: memo(() => import('../pages/RegisterPage')),
  verifyEmail: memo(() => import('../pages/VerifyEmailPage')),
  adminLogs: memo(() => import('../pages/AdminLogsPage')),
  adminUsers: memo(() => import('../pages/AdminUsersPage')),
  adminSupport: memo(() => import('../pages/AdminSupportPage')),
  adminDocuments: memo(() => import('../pages/AdminDocumentsPage')),
  adminBeta: memo(() => import('../pages/AdminBetaPage')),
  cardPayment: memo(() => import('../pages/CardPaymentPage')),
  beta: memo(() => import('../pages/BetaPage')),
  legal: memo(() => import('../pages/LegalPage')),
  extension: memo(() => import('../pages/ExtensionPage')),
  api: memo(() => import('../pages/ApiPage')),
  extensionAutoriser: memo(() => import('../pages/ExtensionAutoriserPage')),
  extensionConnecte: memo(() => import('../pages/ExtensionConnectePage')),
} satisfies Record<string, Chargeur>;

const PAR_CHEMIN: Record<string, Chargeur> = {
  '/login': pages.login,
  '/register': pages.register,
  '/verify-email': pages.verifyEmail,
  '/admin/logs': pages.adminLogs,
  '/admin/users': pages.adminUsers,
  '/admin/support': pages.adminSupport,
  '/admin/documents': pages.adminDocuments,
  '/admin/beta': pages.adminBeta,
  '/paiement/carte': pages.cardPayment,
  '/beta': pages.beta,
  '/extension': pages.extension,
  '/extension/autoriser': pages.extensionAutoriser,
  '/extension/connecte': pages.extensionConnecte,
  '/integrations/api': pages.api,
  '/mentions-legales': pages.legal,
  '/conditions': pages.legal,
  '/confidentialite': pages.legal,
  '/cookies': pages.legal,
};

/** Télécharge le code de la page servie à `chemin` (sans effet si l'accueil ou
 *  une adresse inconnue). Ne rejette jamais : un échec se rejouera au rendu. */
export function prechargerPage(chemin: string): Promise<void> {
  const charger = PAR_CHEMIN[chemin.replace(/\/+$/, '') || '/'];
  return charger ? charger().then(() => undefined, () => undefined) : Promise.resolve();
}

/** Préchargement à l'intention : survol, focus ou toucher d'un lien interne. */
export function installerPrechargement(): void {
  const viser = (e: Event) => {
    const lien = (e.target as Element | null)?.closest?.('a[href]') as HTMLAnchorElement | null;
    if (lien && lien.origin === location.origin) void prechargerPage(lien.pathname);
  };
  for (const type of ['pointerover', 'focusin', 'touchstart'] as const) {
    document.addEventListener(type, viser, { passive: true, capture: true });
  }
}
