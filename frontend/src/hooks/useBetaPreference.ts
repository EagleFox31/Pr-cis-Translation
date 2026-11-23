/**
 * Solde utilisé en premier : Bêta (vrai) ou forfait (faux).
 *
 * Une seule préférence pour le panneau de compte et la case de la zone de
 * traduction : changer l'une met l'autre à jour. Elle est propre à chaque
 * compte (deux personnes sur le même navigateur ne la partagent pas). Par
 * défaut la Bêta, qui expire avant le forfait. Le serveur l'applique via
 * `use_beta`.
 */
import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';

const PREFIXE = 'precis_beta_first';
const EVT = 'precis-beta-first';

function lire(cle: string): boolean {
  try { return localStorage.getItem(cle) !== '0'; } catch { return true; }
}

export function useBetaPreference(): [boolean, (v: boolean) => void] {
  const { user } = useAuth();
  const cle = user ? `${PREFIXE}:${user.id}` : PREFIXE;
  const [valeur, setValeur] = useState(() => lire(cle));
  useEffect(() => {
    const maj = () => setValeur(lire(cle));
    maj(); // changement de compte : relire sa propre préférence
    window.addEventListener(EVT, maj);
    window.addEventListener('storage', maj);
    return () => { window.removeEventListener(EVT, maj); window.removeEventListener('storage', maj); };
  }, [cle]);
  const changer = useCallback((v: boolean) => {
    try { localStorage.setItem(cle, v ? '1' : '0'); } catch { /* préférence de session seulement */ }
    setValeur(v);
    window.dispatchEvent(new Event(EVT));
  }, [cle]);
  return [valeur, changer];
}
