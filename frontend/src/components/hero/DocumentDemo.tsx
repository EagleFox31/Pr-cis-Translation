import { useEffect, useRef, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { motion, useMotionValue, useSpring, useTransform } from 'motion/react';
import { ArrowRight, Check, ScanLine, Sparkles, LayoutTemplate } from 'lucide-react';

/**
 * Démonstration animée du produit — c'est l'accroche du site.
 *
 * Le cycle rejoue, sans un mot, exactement ce que fait l'application :
 *   1. le document source apparaît (vraie page PDF, rendue par pdf.js) ;
 *   2. un balayage analyse sa mise en page ;
 *   3. la page de droite se remplit d'un SQUELETTE dont la géométrie est
 *      extraite du document source — c'est le point clé : le squelette a la
 *      forme exacte des blocs d'origine, ce qui montre d'un coup d'œil que la
 *      mise en page est conservée AVANT même que le texte n'arrive ;
 *   4. la traduction se révèle de haut en bas, le squelette s'effaçant au fur
 *      et à mesure — comme le streaming page par page du vrai moteur.
 *
 * Toutes les coordonnées sont exprimées en POURCENTAGE de la page PDF : la
 * démo reste alignée à n'importe quelle largeur, sans mesurer le DOM.
 */

/** Une page de journal plutôt qu'un CV : elle réunit d'un coup les cas que la
 *  traduction doit tenir — colonnes, manchette, chapeau, encadrés, légendes,
 *  filets, texte justifié. C'est là que la mise en page se casse d'ordinaire,
 *  donc c'est là que la démonstration a une valeur.
 *  (Le nom du fichier est sans accent : « après » aurait dû être encodé dans
 *  l'URL, et pdf.js ne le fait pas pour nous.) */
const SOURCE_PDF = '/demo_journal_avant.pdf';   // Global Tribune, en anglais
const TARGET_PDF = '/demo_journal_apres.pdf';   // Tribune Mondiale, en français

type Phase = 'scan' | 'hold1' | 'skeleton' | 'hold2' | 'reveal' | 'done';

/** Barre de squelette, en % de la page (donc indépendante de la taille écran). */
interface Bar { x: number; y: number; w: number; h: number }

/** Étapes du cycle : durée de chacune, en ms.
 *  hold1 = pause après le scan (blocs détectés visibles).
 *  hold2 = pause après le squelette (géométrie en place avant la traduction). */
const TIMINGS: Record<Phase, number> = {
  scan: 2400,
  hold1: 1000,
  skeleton: 1600,
  hold2: 1200,
  reveal: 3200,
  done: 4200,
};

/**
 * Regroupe les fragments de texte d'une page en barres de squelette.
 *
 * pdf.js donne un item par fragment stylé : plusieurs fragments d'une même
 * ligne doivent former UNE barre, sinon le squelette est haché. Mais il ne
 * suffit PAS de regrouper par bande verticale : sur une page en colonnes, deux
 * colonnes côte à côte partagent la même ligne de base et seraient fondues en
 * une seule barre traversant la gouttière — le squelette montrerait des lignes
 * pleine largeur là où le journal a des colonnes, soit exactement l'inverse de
 * ce qu'il doit prouver. (Mesuré sur la page de démonstration : 25 barres sur
 * 57 enjambaient la gouttière.)
 *
 * On coupe donc aussi sur l'ÉCART HORIZONTAL : au-delà de ~1.2 fois la hauteur
 * du texte, ce n'est plus une espace entre mots, c'est une gouttière.
 */
function barsFromTextContent(items: any[], pageW: number, pageH: number): Bar[] {
  type Frag = { x0: number; x1: number; top: number; h: number };
  const rows = new Map<number, Frag[]>();

  for (const it of items) {
    if (!(it.str ?? '').trim()) continue;
    const [, , , d, e, f] = it.transform as number[];
    const h = Math.abs(d) || 10;
    const w = it.width ?? 0;
    if (w <= 0) continue;
    // PDF : origine en bas à gauche → on repasse en coordonnées écran.
    const top = pageH - f - h;
    const key = Math.round(top / 4);          // tolérance de ligne de base
    const row = rows.get(key);
    const frag: Frag = { x0: e, x1: e + w, top, h };
    if (row) row.push(frag);
    else rows.set(key, [frag]);
  }

  const bars: Frag[] = [];
  for (const row of rows.values()) {
    row.sort((a, b) => a.x0 - b.x0);
    let cur = { ...row[0] };
    for (const frag of row.slice(1)) {
      const gap = frag.x0 - cur.x1;
      if (gap > 1.2 * Math.max(cur.h, frag.h)) {
        bars.push(cur);                       // gouttière : on ferme la barre
        cur = { ...frag };
      } else {
        cur.x1 = Math.max(cur.x1, frag.x1);
        cur.h = Math.max(cur.h, frag.h);
        cur.top = Math.min(cur.top, frag.top);
      }
    }
    bars.push(cur);
  }

  return bars
    .filter((b) => b.x1 - b.x0 > 4)
    .sort((a, b) => a.top - b.top)
    .map((b) => ({
      x: (b.x0 / pageW) * 100,
      y: (b.top / pageH) * 100,
      w: ((b.x1 - b.x0) / pageW) * 100,
      h: (b.h / pageH) * 100,
    }));
}

export default function DocumentDemo() {
  const { t } = useTranslation();
  const srcRef = useRef<HTMLCanvasElement>(null);
  const trgRef = useRef<HTMLCanvasElement>(null);

  const [bars, setBars] = useState<Bar[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [phase, setPhase] = useState<Phase>('scan');
  const [reveal, setReveal] = useState(0);          // 0 → 1, position du front
  const [cycle, setCycle] = useState(0);

  const reduced = useRef(false);

  // ── Rendu des deux pages + extraction de la géométrie du squelette ────────
  useEffect(() => {
    let active = true;
    const tasks: any[] = [];

    (async () => {
      const pdfjsLib = (window as any).pdfjsLib;
      if (!pdfjsLib) return;
      pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.js';

      const draw = async (url: string, canvas: HTMLCanvasElement | null) => {
        if (!canvas) return null;
        const doc = await pdfjsLib.getDocument(url).promise;
        if (!active) return null;
        const page = await doc.getPage(1);
        if (!active) return null;

        // Rendu à résolution fixe : le canvas est ensuite étiré en CSS
        // (width:100%), donc la démo reste nette sans re-rendu au resize.
        const viewport = page.getViewport({ scale: 2 });
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        const task = page.render({ canvasContext: canvas.getContext('2d'), viewport });
        tasks.push(task);
        await task.promise;
        return page;
      };

      try {
        const srcPage = await draw(SOURCE_PDF, srcRef.current);
        await draw(TARGET_PDF, trgRef.current);
        if (!active || !srcPage) return;

        const content = await srcPage.getTextContent();
        if (!active) return;
        const vp = srcPage.getViewport({ scale: 1 });
        setBars(barsFromTextContent(content.items, vp.width, vp.height));
        setLoaded(true);
      } catch {
        setLoaded(true);   // le PDF manque : la carte reste lisible, sans démo
      }
    })();

    return () => {
      active = false;
      tasks.forEach((tk) => { try { tk.cancel(); } catch { /* déjà fini */ } });
    };
  }, []);

  // ── Séquence : scan → pause → squelette → pause → révélation → pause → boucle
  useEffect(() => {
    if (!loaded) return;

    // Mouvement réduit : on montre l'état final, sans boucle.
    reduced.current = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduced.current) {
      setPhase('done');
      setReveal(1);
      return;
    }

    let raf = 0;
    const timers: number[] = [];
    setPhase('scan');
    setReveal(0);

    const t0 = TIMINGS.scan;
    const t1 = t0 + TIMINGS.hold1;
    const t2 = t1 + TIMINGS.skeleton;
    const t3 = t2 + TIMINGS.hold2;
    const t4 = t3 + TIMINGS.reveal;
    const tEnd = t4 + TIMINGS.done;

    timers.push(window.setTimeout(() => setPhase('hold1'), t0));
    timers.push(window.setTimeout(() => setPhase('skeleton'), t1));
    timers.push(window.setTimeout(() => setPhase('hold2'), t2));
    timers.push(window.setTimeout(() => {
      setPhase('reveal');
      const start = performance.now();
      const step = (now: number) => {
        const p = Math.min(1, (now - start) / TIMINGS.reveal);
        // Easing sinusoidal : départ progressif, décélération douce en fin.
        setReveal(Math.sin((p * Math.PI) / 2));
        if (p < 1) raf = requestAnimationFrame(step);
      };
      raf = requestAnimationFrame(step);
    }, t3));

    timers.push(window.setTimeout(() => setPhase('done'), t4));
    timers.push(window.setTimeout(() => setCycle((c) => c + 1), tEnd));

    return () => {
      timers.forEach(clearTimeout);
      cancelAnimationFrame(raf);
    };
  }, [loaded, cycle]);

  // ── Inclinaison 3D suivant le curseur (subtile : la carte « répond ») ─────
  const mx = useMotionValue(0);
  const my = useMotionValue(0);
  const rotX = useSpring(useTransform(my, [-0.5, 0.5], [6, -6]), { stiffness: 140, damping: 18 });
  const rotY = useSpring(useTransform(mx, [-0.5, 0.5], [-7, 7]), { stiffness: 140, damping: 18 });

  const onMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (reduced.current) return;
    const r = e.currentTarget.getBoundingClientRect();
    mx.set((e.clientX - r.left) / r.width - 0.5);
    my.set((e.clientY - r.top) / r.height - 0.5);
  }, [mx, my]);

  const onLeave = useCallback(() => { mx.set(0); my.set(0); }, [mx, my]);

  const status =
    phase === 'scan' || phase === 'hold1'
      ? { Icon: ScanLine, text: t('hero.demo_analyzing') }
    : phase === 'skeleton' || phase === 'hold2'
      ? { Icon: Sparkles, text: t('hero.demo_translating') }
    : phase === 'reveal'
      ? { Icon: Sparkles, text: t('hero.demo_rebuilding') }
    : { Icon: LayoutTemplate, text: t('hero.demo_done') };

  // Progression affichée : continue sur tout le cycle, pas seulement le reveal.
  const progress =
    phase === 'scan' ? 0.1
    : phase === 'hold1' ? 0.18
    : phase === 'skeleton' ? 0.28
    : phase === 'hold2' ? 0.35
    : phase === 'reveal' ? 0.35 + reveal * 0.65
    : 1;

  return (
    <div className="hd-wrap" style={{ perspective: '1400px' }}>
      <motion.div
        className="hd-card"
        onMouseMove={onMove}
        onMouseLeave={onLeave}
        style={{ rotateX: rotX, rotateY: rotY, transformStyle: 'preserve-3d' }}
        initial={{ opacity: 0, y: 28, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.8, delay: 0.25, ease: [0.16, 1, 0.3, 1] }}
      >
        {/* En-tête : nom de fichier + couple de langues */}
        <div className="hd-head">
          <span className="hd-dot red" />
          <span className="hd-dot yellow" />
          <span className="hd-dot green" />
          <span className="hd-filename">global_tribune.pdf</span>
          {/* Le journal de démonstration va de l'anglais au français. */}
          <span className="hd-langs">
            <span>EN</span>
            <ArrowRight size={11} strokeWidth={2.6} />
            <span className="hd-lang-to">FR</span>
          </span>
        </div>

        {/* Les deux pages */}
        <div className="hd-body">
          <div className="hd-panel">
            <div className="hd-panel-label">{t('hero.panel_source')}</div>
            <div className="hd-paper">
              <canvas ref={srcRef} className="hd-canvas" />

              {/* Balayage d'analyse : une ligne descend, un voile la suit */}
              {phase === 'scan' && (
                <motion.div
                  className="hd-scan"
                  initial={{ top: '0%' }}
                  animate={{ top: '100%' }}
                  transition={{ duration: TIMINGS.scan / 1000, ease: 'easeInOut' }}
                />
              )}

              {/* Contours des blocs détectés — « je comprends ta mise en page » */}
              {(phase === 'scan' || phase === 'hold1' || phase === 'skeleton') && bars.map((b, i) => (
                <motion.span
                  key={i}
                  className="hd-block"
                  style={{ left: `${b.x}%`, top: `${b.y}%`, width: `${b.w}%`, height: `${b.h}%` }}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: [0, 1, 0.35] }}
                  transition={{ duration: 0.5, delay: (b.y / 100) * (TIMINGS.scan / 1000) }}
                />
              ))}
            </div>
          </div>

          <div className="hd-arrow">
            <motion.span
              animate={{ x: [0, 4, 0], opacity: [0.55, 1, 0.55] }}
              transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
              style={{ display: 'inline-flex' }}
            >
              <ArrowRight size={18} strokeWidth={2.4} />
            </motion.span>
          </div>

          <div className="hd-panel">
            <div className="hd-panel-label right">{t('hero.panel_target')}</div>
            <div className="hd-paper">
              {/* La traduction se dévoile de haut en bas (clip animé). */}
              <div
                className="hd-reveal"
                style={{ clipPath: `inset(0 0 ${(1 - reveal) * 100}% 0)` }}
              >
                <canvas ref={trgRef} className="hd-canvas" />
              </div>

              {/* Squelette : la géométrie vient du document SOURCE — donc la
                  mise en page est déjà là avant le texte. Chaque barre
                  disparaît quand le front de révélation la dépasse. */}
              {phase !== 'scan' && phase !== 'hold1' && bars.map((b, i) => {
                const passed = b.y + b.h <= reveal * 100;
                return (
                  <motion.span
                    key={i}
                    className="hd-bar"
                    style={{ left: `${b.x}%`, top: `${b.y}%`, width: `${b.w}%`, height: `${b.h}%` }}
                    initial={{ opacity: 0, scaleX: 0.55 }}
                    animate={{
                      opacity: passed ? 0 : 1,
                      scaleX: 1,
                    }}
                    transition={{
                      opacity: { duration: passed ? 0.18 : 0.35, delay: passed ? 0 : (i % 12) * 0.03 },
                      scaleX: { duration: 0.4, delay: (i % 12) * 0.03, ease: [0.16, 1, 0.3, 1] },
                    }}
                  />
                );
              })}

              {/* Front lumineux, à la limite du texte reconstruit */}
              {phase === 'reveal' && (
                <span className="hd-front" style={{ top: `${reveal * 100}%` }} />
              )}
            </div>
          </div>
        </div>

        {/* Barre d'état */}
        <div className="hd-status">
          <span className="hd-status-text">
            <motion.span
              key={phase}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
            >
              {phase === 'done'
                ? <Check size={13} strokeWidth={3} className="hd-check" />
                : <status.Icon size={13} strokeWidth={2.4} />}
              {status.text}
            </motion.span>
          </span>
          <div className="hd-progress">
            <motion.div
              className="hd-progress-bar"
              animate={{ width: `${progress * 100}%` }}
              transition={{ duration: phase === 'reveal' ? 0 : 0.5, ease: 'easeOut' }}
            />
          </div>
        </div>
      </motion.div>

      {/* Étiquettes flottantes — elles n'apparaissent qu'au moment où la démo
          prouve ce qu'elles affirment. */}
      <motion.div
        className="hd-float hd-float--tl"
        initial={{ opacity: 0, y: 10, scale: 0.9 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, delay: 0.9, ease: [0.16, 1, 0.3, 1] }}
      >
        <span className="hd-float-icon blue"><Sparkles size={14} strokeWidth={2.2} /></span>
        <span className="hd-float-text">
          <strong>{t('hero.float_engine')}</strong>
          <span>{t('hero.float_engine_sub')}</span>
        </span>
      </motion.div>

      <motion.div
        className="hd-float hd-float--br"
        initial={{ opacity: 0, y: 10, scale: 0.9 }}
        animate={
          phase === 'done'
            ? { opacity: 1, y: 0, scale: 1 }
            : { opacity: 0.45, y: 0, scale: 0.97 }
        }
        transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
      >
        <span className="hd-float-icon green"><Check size={14} strokeWidth={3} /></span>
        <span className="hd-float-text">
          <strong>{t('hero.float_layout')}</strong>
          <span>{t('hero.float_layout_sub')}</span>
        </span>
      </motion.div>
    </div>
  );
}
