import { useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { motion, useScroll, useTransform } from 'motion/react';

const mascot = "/Identite Precis.png";

export default function AboutSection() {
  const { t } = useTranslation();
  const aboutRef = useRef<HTMLElement>(null);

  const { scrollYProgress: aboutScrollProgress } = useScroll({
    target: aboutRef,
    offset: ['start end', 'end start'],
  });
  const aboutVisualY = useTransform(aboutScrollProgress, [0, 1], [40, -40]);

  return (
    <section className="about-section" id="about" ref={aboutRef}>
      <div
        className="section-inner"
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          width: '100%',
        }}
      >
        <div className="story-grid" style={{ width: '100%' }}>
          <div>
            <span className="section-tag">{t('about.tag')}</span>
            <h2
              className="section-title"
              dangerouslySetInnerHTML={{ __html: t('about.title') }}
            />
            <p className="section-desc">{t('about.desc')}</p>
            <p
              className="text-gray-500 mt-4 text-sm max-w-lg"
              style={{ lineHeight: 1.7, marginTop: '16px' }}
            >
              {t('about.mission')}
            </p>
            <div
              className="about-values flex gap-6"
              style={{
                marginTop: '24px',
                display: 'flex',
                gap: '24px',
                flexWrap: 'wrap',
              }}
            >
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.1 }}
              >
                <div
                  className="font-bold text-navy"
                  style={{ color: 'var(--navy)', fontWeight: 700 }}
                >
                  {t('about.val_innovation')}
                </div>
                <div className="text-xs text-gray-500">
                  {t('about.val_innovation_desc')}
                </div>
              </motion.div>
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.2 }}
              >
                <div
                  className="font-bold text-navy"
                  style={{ color: 'var(--navy)', fontWeight: 700 }}
                >
                  {t('about.val_quality')}
                </div>
                <div className="text-xs text-gray-500">
                  {t('about.val_quality_desc')}
                </div>
              </motion.div>
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.3 }}
              >
                <div
                  className="font-bold text-navy"
                  style={{ color: 'var(--navy)', fontWeight: 700 }}
                >
                  {t('about.val_security')}
                </div>
                <div className="text-xs text-gray-500">
                  {t('about.val_security_desc')}
                </div>
              </motion.div>
            </div>
          </div>

          <motion.div
            className="story-visual"
            style={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              y: aboutVisualY,
            }}
          >
            <div
              style={{
                backgroundColor: 'white',
                padding: '20px',
                borderRadius: '20px',
                boxShadow: 'var(--shadow-lg)',
                border: '1px solid var(--gray-100)',
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                maxWidth: '360px',
              }}
            >
              <img
                src={mascot}
                alt="Mascotte Précis"
                style={{ width: '100%', height: 'auto', borderRadius: '12px' }}
              />
            </div>
          </motion.div>
        </div>
      </div>

      {/* Integrated Footer */}
      <FooterSection />
    </section>
  );
}

function FooterSection() {
  const { t } = useTranslation();

  return (
    <div
      className="about-footer"
      style={{
        borderTop: '1px solid var(--gray-200)',
        paddingTop: '20px',
        width: '100%',
        maxWidth: '1240px',
        margin: '0 auto',
        padding: '20px 24px',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '0.75rem',
          color: 'var(--gray-500)',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <p>{t('footer.rights')}</p>
        <div style={{ display: 'flex', gap: '16px' }}>
          <a href="#" style={{ color: 'inherit' }}>
            {t('footer.legal')}
          </a>
          <a href="#" style={{ color: 'inherit' }}>
            {t('footer.terms')}
          </a>
          <a href="#" style={{ color: 'inherit' }}>
            {t('footer.privacy')}
          </a>
        </div>
      </div>
    </div>
  );
}
