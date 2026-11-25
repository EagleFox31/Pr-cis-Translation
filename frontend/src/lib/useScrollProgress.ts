import { useEffect, type RefObject } from 'react';
import { useMotionValue, type MotionValue } from 'motion/react';

// Progression 0 → 1 d'un élément dans la fenêtre, calculée sur l'événement
// scroll (passif, une mesure par image). Remplace `useScroll({ target })` de
// motion, qui crée des ScrollTimeline/ViewTimeline natifs : leur création
// force une mise en page complète au montage (~2 s sur mobile bridé).
//   'hero'  : 0 quand le haut de l'élément touche le haut de la fenêtre,
//             1 quand son bas l'atteint (['start start', 'end start']).
//   'cross' : 0 quand le haut de l'élément entre par le bas de la fenêtre,
//             1 quand son bas sort par le haut (['start end', 'end start']).
export function useScrollProgress(
  ref: RefObject<HTMLElement | null>,
  mode: 'hero' | 'cross',
): MotionValue<number> {
  const progress = useMotionValue(0);
  useEffect(() => {
    let frame = 0;
    const mesurer = () => {
      frame = 0;
      const el = ref.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      const vh = window.innerHeight;
      const p = mode === 'hero' ? -r.top / (r.height || 1) : (vh - r.top) / (vh + r.height || 1);
      progress.set(Math.min(1, Math.max(0, p)));
    };
    const planifier = () => {
      if (!frame) frame = requestAnimationFrame(mesurer);
    };
    planifier();
    window.addEventListener('scroll', planifier, { passive: true });
    window.addEventListener('resize', planifier);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('scroll', planifier);
      window.removeEventListener('resize', planifier);
    };
  }, [ref, mode, progress]);
  return progress;
}
