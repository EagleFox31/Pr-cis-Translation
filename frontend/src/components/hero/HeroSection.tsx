import { useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { motion, useScroll, useTransform } from 'motion/react';
import AnimatedCounter from '../ui/AnimatedCounter';

const mascot = "/Identite Precis.png";

export default function HeroSection() {
  const { t } = useTranslation();
  const heroRef = useRef<HTMLElement>(null);

  const { scrollYProgress: heroScrollProgress } = useScroll({
    target: heroRef,
    offset: ['start start', 'end start'],
  });
  const heroBgY = useTransform(heroScrollProgress, [0, 1], [0, 120]);
  const heroGridY = useTransform(heroScrollProgress, [0, 1], [0, 80]);

  return (
    <section className="hero" id="hero" ref={heroRef}>
      {/* Parallax Background */}
      <motion.div className="hero-parallax-bg" style={{ y: heroBgY }}>
        <div className="hero-lang-lines">
          <div className="lang-line lang-line-left">
            {[1, 2, 3].map((i) => (
              <span key={i} style={{ display: 'inline-flex', gap: '30px' }}>
                <span>Translation</span><span>•</span>
                <span>Traduction</span><span>•</span>
                <span>Traducción</span><span>•</span>
                <span>Übersetzung</span><span>•</span>
                <span>Traduzione</span><span>•</span>
                <span>Overzetting</span><span>•</span>
                <span>翻訳</span><span>•</span>
                <span>번역</span><span>•</span>
                <span>翻译</span><span>•</span>
                <span>ترجمة</span><span>•</span>
                <span>Перевод</span><span>•</span>
              </span>
            ))}
          </div>
          <div className="lang-line lang-line-right">
            {[1, 2, 3].map((i) => (
              <span key={i} style={{ display: 'inline-flex', gap: '30px' }}>
                <span>Documents</span><span>•</span>
                <span>Actes</span><span>•</span>
                <span>Certificats</span><span>•</span>
                <span>Contrats</span><span>•</span>
                <span>Diplômes</span><span>•</span>
                <span>書類</span><span>•</span>
                <span>문서</span><span>•</span>
                <span>文档</span><span>•</span>
                <span>عقود</span><span>•</span>
                <span>Справки</span><span>•</span>
              </span>
            ))}
          </div>
          <div className="lang-line lang-line-left">
            {[1, 2, 3].map((i) => (
              <span key={i} style={{ display: 'inline-flex', gap: '30px' }}>
                <span>Precision</span><span>•</span>
                <span>Précision</span><span>•</span>
                <span>Precisión</span><span>•</span>
                <span>Präzision</span><span>•</span>
                <span>Precisione</span><span>•</span>
                <span>Precisie</span><span>•</span>
                <span>精度</span><span>•</span>
                <span>정밀도</span><span>•</span>
                <span>精确</span><span>•</span>
                <span>دقة</span><span>•</span>
                <span>Точность</span><span>•</span>
              </span>
            ))}
          </div>
          <div className="lang-line lang-line-right">
            {[1, 2, 3].map((i) => (
              <span key={i} style={{ display: 'inline-flex', gap: '30px' }}>
                <span>AI &amp; Human</span><span>•</span>
                <span>IA &amp; Humain</span><span>•</span>
                <span>IA y Humano</span><span>•</span>
                <span>KI &amp; Mensch</span><span>•</span>
                <span>IA &amp; Umano</span><span>•</span>
                <span>AI &amp; Mens</span><span>•</span>
                <span>AI &amp; 人間</span><span>•</span>
                <span>AI &amp; 인간</span><span>•</span>
                <span>AI &amp; 人类</span><span>•</span>
                <span>ذكاء بشري واصطناعي</span><span>•</span>
              </span>
            ))}
          </div>
        </div>
      </motion.div>
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
            {/* CTA principal → l'outil de traduction (section suivante, RF-1) */}
            <a href="#story" className="btn-primary">
              {t('hero.btn_start')}
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3" />
              </svg>
            </a>
            <a href="#pricing" className="btn-outline">{t('hero.btn_discover')}</a>
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
              <div className="hero-stat-label">Disponibilité</div>
            </div>
            <div>
              <div className="hero-stat-num">
                <AnimatedCounter value="50+" />
              </div>
              <div className="hero-stat-label">Langues</div>
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
                <div className="doc-arrow">→</div>
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
                <strong>Traduction IA</strong>
                <span>Optimisée</span>
              </div>
            </div>
            <div className="floating-label br">
              <div className="fl-icon gold">✓</div>
              <div className="fl-text">
                <strong>Relecture Humaine</strong>
                <span>Certifiée</span>
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
                Intelligence Artificielle
              </div>
              <div style={{ fontSize: '20px', color: 'var(--navy)', fontWeight: 700, marginTop: '5px' }}>
                L'intelligence au service du sens
              </div>
              <p style={{ fontSize: '14px', color: 'var(--gray-500)', marginTop: '10px', lineHeight: 1.6, maxWidth: '400px' }}>
                Une compréhension contextuelle profonde qui surpasse les traducteurs classiques.
              </p>
              <div className="floating-label tl">
                <div className="fl-icon blue" style={{ color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700 }}>
                  AI
                </div>
                <div className="fl-text">
                  <strong>IA Avancée</strong>
                  <span>Haute Précision</span>
                </div>
              </div>
              <div className="floating-label br">
                <div className="fl-icon gold" style={{ color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700 }}>
                  ✓
                </div>
                <div className="fl-text">
                  <strong>Sécurité</strong>
                  <span>RGPD Garanti</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* RF-2.2 : fond de transition douce vers la section claire suivante */}
      <div className="hero-bottom-fade" />
    </section>
  );
}
