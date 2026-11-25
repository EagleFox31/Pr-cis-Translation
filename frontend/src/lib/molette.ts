/**
 * Molette de la visionneuse : UN GESTE = UNE ACTION.
 *
 * Un geste est une suite d'événements `wheel` sans pause (molette qu'on fait
 * tourner, ou pavé tactile et son inertie). Son action est fixée à son début :
 * - le cadre n'était pas au bord dans ce sens → le geste fait défiler la page
 *   et s'arrête au bord, sans jamais changer de page ;
 * - il était déjà au bord → le geste change de page, une seule fois.
 * Pour passer à la page suivante après avoir atteint le bas, il faut donc
 * s'arrêter puis relancer la molette.
 */
export type ActionMolette = 'defiler' | 'bloquer' | 'page';

/** Pause (ms) au-delà de laquelle un nouvel événement ouvre un nouveau geste. */
export const PAUSE_GESTE = 250;
/** Élan cumulé (px) qu'un geste parti du bord doit atteindre pour changer de page. */
export const SEUIL_PAGE = 60;

export function creerGesteMolette(pause = PAUSE_GESTE, seuil = SEUIL_PAGE) {
  let dernier = -Infinity;
  let sensGeste = 0;
  let mode: 'defiler' | 'page' | 'fini' = 'defiler';
  let cumul = 0;
  /** `auBord(sens)` : le cadre est-il déjà au bout dans ce sens (1 = bas, -1 = haut) ? */
  return (deltaY: number, t: number, auBord: (sens: number) => boolean): ActionMolette => {
    const sens = Math.sign(deltaY);
    if (t - dernier > pause || sens !== sensGeste) {
      sensGeste = sens;
      cumul = 0;
      mode = auBord(sens) ? 'page' : 'defiler';
    }
    dernier = t;
    if (mode === 'defiler') return auBord(sens) ? 'bloquer' : 'defiler';
    if (mode === 'fini') return 'bloquer';
    cumul += deltaY;
    if (Math.abs(cumul) < seuil) return 'bloquer';
    mode = 'fini';
    return 'page';
  };
}
