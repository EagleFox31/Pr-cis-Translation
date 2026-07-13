import { useRef, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { motion, useScroll, useTransform } from 'motion/react';
import { ArrowRight, LayoutTemplate, FileType2, Languages } from 'lucide-react';
import DocumentDemo from './DocumentDemo';

/** Légère marge : les lignes ne touchent pas tout à fait le bord, ce qui laisse
 *  aussi respirer les repères de coupe, qui débordent du mot. */
const SIDE_MARGIN = 10;

/** Blanc AJOUTÉ entre les mots, en em. Le blanc naturel de la police vaut
 *  ~0.25em : on aboutit donc à ~0.5em, soit deux fois le naturel — assez pour
 *  aérer, trop peu pour qu'on le remarque. Cf. le commentaire ci-dessous. */
const WORD_EXTRA_EM = 0.25;

/** Garde-fous du corps. */
const MIN_SIZE = 20;
const MAX_SIZE = 120;

/**
 * Justifie le titre : les trois lignes tombent à la MÊME largeur.
 *
 * L'écart de longueur entre « Traduisez vos documents » (23 signes) et « mise
 * en page » (12) doit être absorbé par quelque chose. Deux leviers existent, et
 * ils sont TRÈS inégaux — mesuré sur la police du titre :
 *
 *     blanc visé   corps des 3 lignes   écart de corps
 *       0.25em      50 / 81 / 98 px         ×1.95      (blanc naturel)
 *       0.50em      48 / 75 / 89 px         ×1.86
 *       1.00em      44 / 65 / 76 px         ×1.74      (blanc ×4 : déjà voyant)
 *       2.72em      34 / 45 / 50 px         ×1.49      (mots éparpillés)
 *
 * Autrement dit : QUADRUPLER les blancs ne réduit l'écart de corps que de 1.95
 * à 1.74. Les blancs sont un levier presque nul ; le corps est le seul vrai
 * levier. Tout miser sur eux — ce que faisait la version précédente — éparpille
 * les mots sans même égaliser les corps.
 *
 * On se place donc au point d'équilibre : un blanc de ~0.5em (deux fois le
 * naturel, invisible), et c'est le CORPS de chaque ligne qui comble le reste.
 * Les mots gardent leur dessin exact — aucune lettre n'est écartée — et la
 * ligne la plus courte devient la plus grande : « mise en page », la promesse,
 * est aussi ce que l'œil voit en premier.
 */
function useJustifiedLines(ref: React.RefObject<HTMLHeadingElement | null>, deps: unknown[]) {
  const fit = useCallback(() => {
    const title = ref.current;
    if (!title) return;
    const target = title.clientWidth - SIDE_MARGIN;
    if (target <= 0) return;

    const lines = [...title.querySelectorAll<HTMLElement>('.hero-line')];

    lines.forEach((line) => {
      const text = line.querySelector<HTMLElement>('.hero-line-text');
      if (!text) return;

      line.style.fontSize = '';
      let size = parseFloat(getComputedStyle(line).fontSize);

      // La largeur est LINÉAIRE en `size` — le blanc ajouté est lui aussi
      // exprimé en em, donc il grandit avec le corps. Une règle de trois suffit
      // ; la seconde passe ne rattrape que les arrondis (crénage, sous-pixel).
      for (let pass = 0; pass < 3; pass++) {
        line.style.fontSize = `${size}px`;
        line.style.wordSpacing = `${WORD_EXTRA_EM * size}px`;
        const w = text.getBoundingClientRect().width;
        if (!w) return;
        if (Math.abs(target - w) < 0.4) break;
        size = Math.min(MAX_SIZE, Math.max(MIN_SIZE, (size * target) / w));
      }
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

            {/* Plus de soulignement sous « sans perdre » : le corps croissant
                conduit déjà l'œil vers la dernière ligne, et le trait venait
                buter contre les repères de coupe qui la surmontent. */}
            <span className="hero-line">
              <span className="hero-line-text">
                {t('hero.title_key')} {t('hero.title_mid')}
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
