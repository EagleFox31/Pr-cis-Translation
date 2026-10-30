/**
 * Filtres des pages admin portés par l'adresse (`?q=…&status=…`), pour que le
 * bouton Retour, un lien copié ou un rechargement retrouvent la même vue.
 *
 * Les autres paramètres de l'adresse (notamment `user`, qui ouvre la fiche
 * utilisateur) ne sont jamais touchés. La frappe réécrit l'entrée d'historique
 * courante (`replace`) au lieu d'en empiler une par lettre.
 */
import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';

const SEP = '\u0001';

export function useAdminUrlParams<K extends string>(keys: readonly K[]) {
  const [params, setParams] = useSearchParams();

  // Signature des seules valeurs suivies : l'objet reste stable quand un autre
  // paramètre change, donc ouvrir la fiche ne relance aucune requête de liste.
  const signature = keys.map((k) => params.get(k) ?? '').join(SEP);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const values = useMemo(() => {
    const parts = signature.split(SEP);
    return Object.fromEntries(keys.map((k, i) => [k, parts[i]])) as Record<K, string>;
  }, [signature]);

  const setValues = useCallback((patch: Partial<Record<K, string | undefined>>) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      for (const [k, v] of Object.entries(patch) as [string, string | undefined][]) {
        if (v) next.set(k, v); else next.delete(k);
      }
      return next;
    }, { replace: true });
  }, [setParams]);

  const clear = useCallback(() => {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      keys.forEach((k) => next.delete(k));
      return next;
    }, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [setParams]);

  return { values, setValues, clear };
}
