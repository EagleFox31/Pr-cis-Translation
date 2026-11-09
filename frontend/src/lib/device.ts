// Identifiants d'appareil pour le contrôle anti-abus des pages offertes
// (docs/etude-anti-abus.md). Le serveur les hache en HMAC et ne s'en sert que
// pour relier des identifiants : jamais pour bloquer un compte seul.
// Tout échec (stockage interdit, script bloqué, délai) se dégrade en silence :
// le cookie signé `precis_device` reste le signal de base.

const COPY_KEY = 'precis_device_copy';
const PRINT_TIMEOUT_MS = 1500;

let printPromise: Promise<string | null> | null = null;

function deviceCopy(): string | null {
  try {
    let id = localStorage.getItem(COPY_KEY);
    if (!id || !/^[A-Za-z0-9_-]{8,128}$/.test(id)) {
      id = crypto.randomUUID().replace(/-/g, '');
      localStorage.setItem(COPY_KEY, id);
    }
    return id;
  } catch {
    return null;
  }
}

// FingerprintJS v5 (MIT) chargé à la demande : seules la traduction et la
// candidature bêta le paient, le reste du site ne le télécharge jamais.
function devicePrint(): Promise<string | null> {
  // Calcul unique par page ; seule l'ATTENTE est bornée, à chaque appel : un
  // premier appel trop lent laisse le calcul finir pour le suivant.
  printPromise ??= import('@fingerprintjs/fingerprintjs')
    .then((fp) => fp.load({ monitoring: false }))
    .then((agent) => agent.get())
    .then((result) => result.visitorId)
    .catch(() => null);
  const timeout = new Promise<null>((resolve) => setTimeout(() => resolve(null), PRINT_TIMEOUT_MS));
  return Promise.race([printPromise, timeout]);
}

export async function deviceHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {};
  const copy = deviceCopy();
  if (copy) headers['X-Device-Copy'] = copy;
  const print = await devicePrint();
  if (print) headers['X-Device-Print'] = print;
  return headers;
}
