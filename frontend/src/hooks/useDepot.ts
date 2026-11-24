import { useEffect, useState } from 'react';

import { deposer } from '../services/depot';

/**
 * Dépose le fichier choisi dès sa sélection et suit l'envoi. `enCours` tient
 * le bouton Traduire grisé ; un dépôt qui échoue rend la main (`enCours`
 * false) : la traduction renverra alors le fichier elle-même, comme avant.
 */
export function useDepot(file: File | null, active: boolean) {
  const [etat, setEtat] = useState<{ file: File; pct: number; fini: boolean } | null>(null);

  useEffect(() => {
    if (!file || !active) return;
    const ctrl = new AbortController();
    setEtat({ file, pct: 0, fini: false });
    deposer(file, (pct) => {
      if (!ctrl.signal.aborted) setEtat({ file, pct, fini: false });
    }, ctrl.signal)
      .catch(() => null)
      .then(() => {
        if (!ctrl.signal.aborted) setEtat((e) => ({ file, pct: e?.pct ?? 0, fini: true }));
      });
    return () => ctrl.abort();
  }, [file, active]);

  const aJour = !!file && active && etat?.file === file;
  return {
    enCours: !!file && active && !(aJour && etat.fini),
    pct: aJour ? etat.pct : 0,
  };
}
