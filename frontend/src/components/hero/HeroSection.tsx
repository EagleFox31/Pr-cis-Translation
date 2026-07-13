import { useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { motion, useScroll, useTransform } from 'motion/react';
import { ArrowRight, Check } from 'lucide-react';
import AnimatedCounter from '../ui/AnimatedCounter';

const mascot = "/Identite Precis.png";

export default function HeroSection() {
  const { t } = useTranslation();
  const heroRef = useRef<HTMLElement>(null);

  const { scrollYProgress: heroScrollProgress } = useScroll({
    target: heroRef,
    offset: ['start start', 'end start'],
  });
  const heroGridY = useTransform(heroScrollProgress, [0, 1], [0, 80]);

  return (
    <section className="hero" id="hero" ref={heroRef}>
      {/* Grid parallax background */}
      <motion.div className="hero-grid" style={{ y: heroGridY }} />
      <div className="hero-particles">
        <div className="particle" style={{ left: '10%', animationDelay: '0s', animationDuration: '8s' }} />
        <div className="particle" style={{ left: '30%', animationDelay: '2s', animationDuration: '12s' }} />
        <div className="particle" style={{ left: '50%', animationDelay: '1s', animationDuration: '10s' }} />
        <div className="particle" style={{ left: '70%', animationDelay: '4s', animationDuration: '14s' }} />
        <div className="particle" style={{ left: '90%', animationDelay: '3s', animationDuration: '9s' }} />
      </div>
      <div className="hero-glow" />

      <div className="hero-content">
        <div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="hero-badge">
              <div className="hero-badge-dot" />
              {t('hero.badge')}
            </div>
          </motion.div>

          <motion.h1
            className="hero-title"
            dangerouslySetInnerHTML={{ __html: t('hero.title') }}
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
          />

          <motion.p
            className="hero-subtitle"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.3, ease: [0.16, 1, 0.3, 1] }}
          >
            {t('hero.subtitle')}
          </motion.p>

          <motion.div
            className="hero-actions"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.45, ease: [0.16, 1, 0.3, 1] }}
          >
            <a href="#pricing" className="btn-primary">
              {t('hero.btn_discover')}
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3" />
              </svg>
            </a>
            <a href="#story" className="btn-outline">{t('hero.btn_start')}</a>
          </motion.div>

          <motion.div
            className="hero-stats"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.6, ease: [0.16, 1, 0.3, 1] }}
          >
            <div>
              <div className="hero-stat-num">
                <AnimatedCounter value="99%" />
              </div>
              <div className="hero-stat-label">{t('hero.stat_precision')}</div>
            </div>
            <div>
              <div className="hero-stat-num">
                <AnimatedCounter value="24/7" duration={1500} />
              </div>
              <div className="hero-stat-label">{t('hero.stat_availability')}</div>
            </div>
            <div>
              <div className="hero-stat-num">
                <AnimatedCounter value="50+" />
              </div>
              <div className="hero-stat-label">{t('hero.stat_languages')}</div>
            </div>
          </motion.div>
        </div>

        {/* Hero Visual - Carousel */}
        <div className="hero-visual">
          <div className="doc-mockup carousel-slide-1">
            <div className="doc-card">
              <div className="doc-header">
                <div className="doc-dot red" />
                <div className="doc-dot yellow" />
                <div className="doc-dot green" />
                <div className="doc-filename">document_original.docx</div>
              </div>
              <div className="doc-body">
                <div className="doc-panel">
                  <div className="doc-panel-label">Source</div>
                  <canvas id="pdf-canvas-hero-source" style={{ width: '100%', height: 'auto', display: 'block' }} />
                </div>
                <div className="doc-arrow"><ArrowRight size={18} strokeWidth={2.2} /></div>
                <div className="doc-panel">
                  <div className="doc-panel-label right">Traduction</div>
                  <canvas id="pdf-canvas-hero-translated" style={{ width: '100%', height: 'auto', display: 'block' }} />
                </div>
              </div>
              <div className="doc-progress">
                <div className="doc-progress-bar" />
              </div>
              <div className="doc-badge-formats">
                <span className="fmt-badge">DOCX</span>
                <span className="fmt-badge highlighted">PDF</span>
                <span className="fmt-badge">XLSX</span>
              </div>
            </div>
            <div className="floating-label tl">
              <div className="fl-icon blue">A</div>
              <div className="fl-text">
                <strong>{t('hero.ai_translation')}</strong>
                <span>{t('hero.optimized')}</span>
              </div>
            </div>
            <div className="floating-label br">
              <div className="fl-icon gold"><Check size={14} strokeWidth={3} /></div>
              <div className="fl-text">
                <strong>{t('hero.human_review')}</strong>
                <span>{t('hero.certified')}</span>
              </div>
            </div>
          </div>

          <div className="mascot-slide carousel-slide-2">
            <div
              style={{
                backgroundColor: 'white',
                padding: '40px',
                borderRadius: '20px',
                boxShadow: 'var(--shadow-2xl)',
                border: '1px solid var(--gray-100)',
                width: '100%',
                maxWidth: '560px',
                minHeight: '420px',
                textAlign: 'center',
                position: 'relative',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                alignItems: 'center',
              }}
            >
              <img src={mascot} alt="Mascotte Précis" style={{ width: '180px', height: 'auto', marginBottom: '20px' }} />
              <div style={{ fontSize: '12px', color: 'var(--blue)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.15em' }}>
                {t('hero.mascot_subtitle')}
              </div>
              <div style={{ fontSize: '20px', color: 'var(--navy)', fontWeight: 700, marginTop: '5px' }}>
                {t('hero.intelligence_service_meaning')}
              </div>
              <p style={{ fontSize: '14px', color: 'var(--gray-500)', marginTop: '10px', lineHeight: 1.6, maxWidth: '400px' }}>
                {t('hero.deep_contextual_understanding')}
              </p>
              <div className="floating-label tl">
                <div className="fl-icon blue" style={{ color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700 }}>
                  AI
                </div>
                <div className="fl-text">
                  <strong>{t('hero.ai_advanced')}</strong>
                  <span>{t('hero.high_precision')}</span>
                </div>
              </div>
              <div className="floating-label br">
                <div className="fl-icon gold" style={{ color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Check size={14} strokeWidth={3} />
                </div>
                <div className="fl-text">
                  <strong>{t('hero.security')}</strong>
                  <span>{t('hero.rgpd_guaranteed')}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
