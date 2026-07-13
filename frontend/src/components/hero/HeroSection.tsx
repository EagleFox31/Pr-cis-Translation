import { useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { motion, useScroll, useTransform } from 'motion/react';
import { ArrowRight, LayoutTemplate, FileType2, Languages } from 'lucide-react';
import DocumentDemo from './DocumentDemo';

/** Faits vérifiables, tirés du produit — pas de chiffre invérifiable. */
const PROOFS = [
  { key: 'layout', Icon: LayoutTemplate },
  { key: 'formats', Icon: FileType2 },
  { key: 'langs', Icon: Languages },
];

export default function HeroSection() {
  const { t } = useTranslation();
  const heroRef = useRef<HTMLElement>(null);

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

          {/* Le mot-clé du titre est souligné par un trait qui SE TRACE : le
              regard est conduit vers la promesse (« sans perdre la mise en
              page »), qui est la seule chose qui nous distingue. */}
          <motion.h1
            className="hero-title"
            initial={{ opacity: 0, y: 26 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
          >
            {t('hero.title_before')}{' '}
            <span className="hero-underline">
              {t('hero.title_key')}
              <motion.span
                className="hero-underline-stroke"
                initial={{ scaleX: 0 }}
                animate={{ scaleX: 1 }}
                transition={{ duration: 0.8, delay: 0.75, ease: [0.16, 1, 0.3, 1] }}
              />
            </span>{' '}
            {t('hero.title_after')}
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
            {PROOFS.map(({ key, Icon }, i) => (
              <motion.li
                key={key}
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
