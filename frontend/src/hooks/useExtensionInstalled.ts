import { useEffect, useState } from 'react';
import { extensionInstallee } from '../lib/extension';

/** `installe` vaut null le temps de la détection, puis true ou false. */
export function useExtensionInstalled(): { installe: boolean | null; version?: string } {
  const [etat, setEtat] = useState<{ installe: boolean | null; version?: string }>({ installe: null });

  useEffect(() => {
    let actif = true;
    extensionInstallee().then((r) => { if (actif) setEtat(r); });
    return () => { actif = false; };
  }, []);

  return etat;
}
