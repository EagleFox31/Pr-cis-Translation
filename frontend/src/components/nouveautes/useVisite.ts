import { useEffect, useLayoutEffect, useState, type RefObject } from 'react';
import { SEQ } from './visiteData';

const LARGEUR_SCENE = 540;
const HAUTEUR_SCENE = 460;

/**
 * Animation des scènes de la visite. Les textes et le curseur sont pilotés
 * directement dans le DOM (comme la maquette) ; React ne connaît que l'étape
 * courante, pour la légende. Tous les délais sont annulés au changement de
 * diapositive et au démontage.
 */
export function useVisite(stageRef: RefObject<HTMLElement | null>, diapo: number): number {
  // L'étape est rattachée à sa diapositive : pas de légende périmée au changement.
  const [etape, setEtape] = useState({ d: diapo, k: 0 });

  // Échelle de la scène : elle occupe l'emplacement sans jamais déborder.
  useLayoutEffect(() => {
    const ajuster = () => {
      const stage = stageRef.current;
      const slot = stage?.querySelector<HTMLElement>('.vst-slot');
      if (!stage || !slot) return;
      const r = slot.getBoundingClientRect();
      const petit = window.innerWidth <= 900;
      const k = Math.min(
        1.15,
        (r.width - (petit ? 16 : 40)) / LARGEUR_SCENE,
        (r.height - (petit ? 16 : 30)) / HAUTEUR_SCENE,
      );
      stage.style.setProperty('--k', k.toFixed(3));
    };
    ajuster();
    window.addEventListener('resize', ajuster);
    return () => window.removeEventListener('resize', ajuster);
  }, [stageRef]);

  useEffect(() => {
    const stage = stageRef.current;
    const sc = stage?.querySelectorAll<HTMLElement>('.vst-scene')[diapo];
    if (!sc) return;
    const S = SEQ[diapo];
    const reduit = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const timers: number[] = [];
    const later = (f: () => void, ms: number) => { timers.push(window.setTimeout(f, ms)); };

    // Change la langue des textes d'une famille, en fondu et en cascade.
    const langue = (sel: string, l: string, gap: number, wait: number) => {
      sc.querySelectorAll<HTMLElement>(sel).forEach((e, n) => {
        const v = e.dataset[l];
        if (v == null || v === e.textContent) return;
        if (!gap) { e.textContent = v; return; }
        later(() => {
          e.classList.add('vst-sw');
          later(() => { e.textContent = v; e.classList.remove('vst-sw'); }, 220);
        }, wait + n * gap);
      });
    };

    const jouerEtape = (k: number) => {
      const st = S[k];
      const vite = k === 0 || reduit;
      sc.dataset.step = String(k);
      setEtape({ d: diapo, k });
      if (st.l) langue('.vst-t', st.l, vite ? 0 : 130, st.w || 0);
      if (st.li) langue('.vst-ti', st.li, vite ? 0 : 1, st.w || 0);
      if (st.p) {
        const lp = sc.querySelector<HTMLElement>('.vst-lp');
        if (lp) lp.innerHTML = st.p;
      }
      const c = sc.querySelector<SVGElement>('.vst-cur');
      if (c && st.cur) {
        c.style.left = `${st.cur[0]}px`;
        c.style.top = `${st.cur[1]}px`;
        if (st.clk && !reduit) {
          later(() => { c.classList.remove('vst-clk'); void c.getBoundingClientRect(); c.classList.add('vst-clk'); }, 820);
        }
      }
    };

    // Sans animation : on déroule tout d'un coup et on s'arrête sur la dernière étape.
    if (reduit) {
      S.forEach((_, k) => jouerEtape(k));
      return () => timers.forEach(clearTimeout);
    }

    let raf1 = 0;
    let raf2 = 0;
    let k = 0;
    const run = () => {
      jouerEtape(k);
      later(() => { k = (k + 1) % S.length; run(); }, S[k].d);
    };
    sc.dataset.step = '-1';
    raf1 = requestAnimationFrame(() => { raf2 = requestAnimationFrame(run); });
    return () => {
      cancelAnimationFrame(raf1);
      cancelAnimationFrame(raf2);
      timers.forEach(clearTimeout);
    };
  }, [stageRef, diapo]);

  return etape.d === diapo ? etape.k : 0;
}
