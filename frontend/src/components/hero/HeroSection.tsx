import { useRef, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { motion, useScroll, useTransform } from 'motion/react';
import { ArrowRight, LayoutTemplate, FileType2, Languages } from 'lucide-react';
import DocumentDemo from './DocumentDemo';

/** Légère marge : les trois lignes ne touchent pas tout à fait le bord, ce qui
 *  laisse aussi respirer les repères de coupe, qui débordent du mot. */
const SIDE_MARGIN = 10;

/**
 * Justifie le titre : les trois lignes tombent à la MÊME largeur, un même corps
 * pour toutes, le texte étant approché (letter-spacing) jusqu'à remplir la
 * mesure — c'est la justification au sens typographique.
 *
 * Deux points qu'on ne peut pas confier au CSS :
 *
 * • `text-align: justify` n'agit pas ici. Chaque ligne est un bloc, donc chaque
 *   ligne est une DERNIÈRE ligne — et une dernière ligne n'est jamais justifiée.
 *   `text-align-last: justify` le forcerait, mais en n'étirant QUE les blancs :
 *   avec deux ou trois mots, les mots se retrouveraient aux extrémités et le
 *   titre se lirait comme cassé. On répartit donc l'écart sur TOUTES les
 *   lettres, ce qui est l'approche (tracking) du typographe.
 *
 * • Le corps commun est calé sur la ligne la PLUS LONGUE : elle remplit la
 *   mesure sans approche, et les autres n'ont plus qu'à s'écarter. Aucune ligne
 *   n'a donc à se resserrer, ce qui abîmerait le dessin des lettres.
 */
function useJustifiedLines(ref: React.RefObject<HTMLHeadingElement | null>, deps: unknown[]) {
  const fit = useCallback(() => {
    const title = ref.current;
    if (!title) return;
    const target = title.clientWidth - SIDE_MARGIN;
    if (target <= 0) return;

    const lines = [...title.querySelectorAll<HTMLElement>('.hero-line')];
    const texts = lines.map((l) => l.querySelector<HTMLElement>('.hero-line-text'));
    if (texts.some((t) => !t)) return;

    // 1) Corps commun, calé sur la ligne la plus longue.
    title.style.fontSize = '';
    lines.forEach((l) => { l.style.letterSpacing = '0px'; l.style.setProperty('--ls', '0px'); });
    const base = parseFloat(getComputedStyle(title).fontSize);
    const widest = Math.max(...texts.map((t) => t!.getBoundingClientRect().width));
    if (!widest) return;
    title.style.fontSize = `${(base * target) / widest}px`;

    // 2) Approche par ligne. Le calcul théorique tombe à quelques pixels près
    //    (crénage, ligatures) : on corrige sur la mesure réelle, en deux ou
    //    trois passes, jusqu'à ce que le bord droit tombe juste.
    lines.forEach((line, i) => {
      const text = texts[i]!;
      const chars = (text.textContent ?? '').length;
      if (chars < 2) return;

      let ls = 0;
      for (let pass = 0; pass < 4; pass++) {
        // letter-spacing insère aussi un blanc APRÈS la dernière lettre : la
        // boîte est donc plus large que les glyphes d'exactement `ls`.
        const visible = text.getBoundingClientRect().width - ls;
        const delta = target - visible;
        if (Math.abs(delta) < 0.4) break;
        ls += delta / (chars - 1);
        line.style.letterSpacing = `${ls}px`;
      }
      // Ce blanc de fin décalerait vers la droite tout ce qui s'accroche au
      // bord du texte : le trait sous « sans perdre » et le repère de droite
      // de « mise en page ». On l'expose en variable, le CSS le reprend.
      line.style.setProperty('--ls', `${ls}px`);
    });
  }, [ref]);

  useEffect(() => {
    fit();
    const ro = new ResizeObserver(fit);
    if (ref.current) ro.observe(ref.current);
    // Les polices arrivent après le premier rendu : sans ce second passage, la
    // mesure serait faite sur la police de repli et les bords ne tomberaient
    // pas juste une fois Cormorant chargée.
    document.fonts?.ready.then(fit).catch(() => {});
    return () => ro.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fit, ...deps]);
}

/** Faits vérifiables, tirés du produit — pas de chiffre invérifiable.
 *  Les FORMATS sont des noms techniques : la chasse fixe les rend lisibles
 *  d'un coup d'œil et distingue la donnée du discours. */
const PROOFS = [
  { key: 'layout', Icon: LayoutTemplate, mono: false },
  { key: 'formats', Icon: FileType2, mono: true },
  { key: 'langs', Icon: Languages, mono: false },
];

export default function HeroSection() {
  const { t, i18n } = useTranslation();
  const heroRef = useRef<HTMLElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);

  // Re-mesuré à chaque changement de langue : « mise en page » et « layout »
  // n'ont ni la même longueur ni le même nombre de mots.
  useJustifiedLines(titleRef, [i18n.language]);

  const { scrollYProgress } = useScroll({
    target: heroRef,
    offset: ['start start', 'end start'],
  });
  // La grille de fond défile plus lentement que le contenu (profondeur), et le
  // hero s'estompe en sortant — la transition vers la section suivante est
  // continue au lieu d'être une coupure.
  const gridY = useTransform(scrollYProgress, [0, 1], [0, 90]);
  const contentY = useTransform(scrollYProgress, [0, 1], [0, -40]);
  const contentOpacity = useTransform(scrollYProgress, [0, 0.75], [1, 0]);

  return (
    <section className="hero" id="hero" ref={heroRef}>
      <motion.div className="hero-grid" style={{ y: gridY }} />
      <div className="hero-glow" />

      <motion.div className="hero-content" style={{ y: contentY, opacity: contentOpacity }}>
        <div>
          <motion.div
            className="hero-badge"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          >
            <span className="hero-badge-dot" />
            {t('hero.badge')}
          </motion.div>

          {/* Deux traitements, chacun porteur de sens :
              — « sans perdre » se souligne d'un trait qui se trace ;
              — « mise en page » est en italique doré, cerné de REPÈRES DE COUPE
                qui se posent un à un. Le mot est donc lui-même mis en page, et
                son cadre reste intact : la forme dit ce que la phrase promet. */}
          <motion.h1
            ref={titleRef}
            className="hero-title"
            initial={{ opacity: 0, y: 26 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
          >
            {/* Les trois lignes sont COUPÉES explicitement : `text-wrap: balance`
                laissait le navigateur décider et la coupe changeait avec la
                largeur, la langue et la police. Ici la structure du titre est
                voulue, donc elle est écrite. `.hero-line-text` isole le texte
                pour que useJustifiedLines le mesure sans les repères. */}
            <span className="hero-line">
              <span className="hero-line-text">{t('hero.title_before')}</span>
            </span>

            <span className="hero-line">
              <span className="hero-line-text">
                <span className="hero-underline">
                  {t('hero.title_key')}
                  <motion.span
                    className="hero-underline-stroke"
                    initial={{ scaleX: 0 }}
                    animate={{ scaleX: 1 }}
                    transition={{ duration: 0.8, delay: 0.7, ease: [0.16, 1, 0.3, 1] }}
                  />
                </span>{' '}
                {t('hero.title_mid')}
              </span>
            </span>

            <span className="hero-line hero-line--key">
              <span className="hero-line-text">
                <span className="hero-key">
                  {t('hero.title_layout')}
                  {(['tl', 'tr', 'bl', 'br'] as const).map((corner, i) => (
                    <motion.span
                      key={corner}
                      className={`hero-key-mark hero-key-mark--${corner}`}
                      initial={{ opacity: 0, scale: 0.4 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ duration: 0.35, delay: 1.25 + i * 0.08, ease: [0.16, 1, 0.3, 1] }}
                    />
                  ))}
                </span>
              </span>
            </span>
          </motion.h1>

          <motion.p
            className="hero-subtitle"
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.25, ease: [0.16, 1, 0.3, 1] }}
          >
            {t('hero.subtitle')}
          </motion.p>

          {/* Une action dominante : traduire. La secondaire reste un lien —
              plusieurs boutons de même poids diluent la conversion. */}
          <motion.div
            className="hero-actions"
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.4, ease: [0.16, 1, 0.3, 1] }}
          >
            <a href="#story" className="btn-primary">
              {t('hero.btn_start')}
              <ArrowRight size={18} strokeWidth={2.4} />
            </a>
            <a href="#features" className="btn-ghost">
              {t('hero.btn_how')}
            </a>
          </motion.div>

          <motion.ul
            className="hero-proofs"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.55, ease: [0.16, 1, 0.3, 1] }}
          >
            {PROOFS.map(({ key, Icon, mono }, i) => (
              <motion.li
                key={key}
                className={mono ? 'hero-proof--mono' : undefined}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.5, delay: 0.65 + i * 0.09 }}
              >
                <Icon size={15} strokeWidth={2} />
                {t(`hero.proof_${key}`)}
              </motion.li>
            ))}
          </motion.ul>
        </div>

        <div className="hero-visual">
          <DocumentDemo />
        </div>
      </motion.div>
    </section>
  );
}
