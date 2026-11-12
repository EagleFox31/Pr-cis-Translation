/**
 * Repli progressif de la barre du haut, décidé par la place réellement prise.
 *
 * POURQUOI : un seuil fixe (l'ancien 1100 px) ne suffit pas. La largeur du menu
 * dépend de la langue, du rôle (un lien de plus pour l'admin) et du compte
 * (deux boutons pour un visiteur, un avatar sinon). On affiche tout, on mesure,
 * et tant que la ligne déborde on replie d'un cran. Les crans sont appliqués
 * avant l'affichage (useLayoutEffect) : aucune image où deux éléments se
 * chevauchent. Voir docs/etude-navigation-tarifs.md.
 */
import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from 'react';
import { flushSync } from 'react-dom';

/**
 * 0 tout visible · 1 espacements resserrés · 2 menu ☰ (liens et langue dans le
 * menu) · 3 logo sans texte · 4 « Se connecter » passe dans le menu.
 * Classes `r1`…`r4` sur `.navbar` (appbar.css).
 */
export const REPLI_MAX = 4;

/** Vrai si les éléments visibles de la ligne ne tiennent pas dans sa largeur. */
function deborde(ligne: HTMLElement): boolean {
  const cs = getComputedStyle(ligne);
  const dispo = ligne.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
  const enfants = Array.from(ligne.children).filter((e): e is HTMLElement => e instanceof HTMLElement && e.offsetWidth > 0);
  const ecart = parseFloat(cs.columnGap) || 0;
  const besoin = enfants.reduce((s, e) => s + e.offsetWidth, 0) + ecart * Math.max(0, enfants.length - 1);
  return besoin + 8 > dispo;   // 8 px de marge : jamais bord à bord
}

/**
 * @param ligne la rangée principale (`.nav-inner`)
 * @param cle   tout ce qui change la largeur du contenu (langue, rôle, compte)
 */
export function useRepli(ligne: RefObject<HTMLElement | null>, cle: string): number {
  const [niveau, setNiveau] = useState(0);
  const [largeur, setLargeur] = useState(0);
  const [polices, setPolices] = useState(0);
  const derniere = useRef('');

  // Largeur de la ligne ; polices chargées (elles changent la largeur des mots).
  useEffect(() => {
    const el = ligne.current;
    if (!el) return;
    // flushSync : le nouveau cran est calculé avant que l'image soit peinte,
    // même pendant qu'on rétrécit la fenêtre.
    const ro = new ResizeObserver(() => flushSync(() => setLargeur(el.clientWidth)));
    ro.observe(el);
    let vivant = true;
    document.fonts?.ready.then(() => { if (vivant) setPolices((n) => n + 1); });
    return () => { vivant = false; ro.disconnect(); };
  }, [ligne]);

  // Après chaque rendu : contexte changé → on repart de 0 ; sinon on replie
  // d'un cran tant que ça déborde. Chaque cran est rendu avant l'affichage.
  useLayoutEffect(() => {
    const el = ligne.current;
    if (!el) return;
    const k = `${cle}|${largeur}|${polices}`;
    if (k !== derniere.current) {
      derniere.current = k;
      if (niveau !== 0) { setNiveau(0); return; }
    }
    if (niveau < REPLI_MAX && deborde(el)) setNiveau(niveau + 1);
  });

  return niveau;
}
