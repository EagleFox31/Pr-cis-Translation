import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { motion, AnimatePresence } from 'motion/react';
import {
  Sparkles, LayoutTemplate, ScanText, ShieldCheck, Users, Languages,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

import Badge from '../ui/Badge';
import ComparisonContent from '../comparison/ComparisonTable';

const features: { key: string; Icon: LucideIcon; badge?: boolean }[] = [
  { key: 'fidelity', Icon: Sparkles },
  { key: 'format', Icon: LayoutTemplate },
  { key: 'ocr', Icon: ScanText, badge: true },
  { key: 'security', Icon: ShieldCheck },
  { key: 'human', Icon: Users },
  { key: 'languages', Icon: Languages },
];

export default function FeaturesGrid() {
  const { t } = useTranslation();
  const [showComparison, setShowComparison] = useState(false);

  return (
    <section className="features-section" id="features">
      <div className="section-inner">
        <motion.div
          className="features-header-block"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.1 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="section-tag">{t('features.tag')}</div>
          <h2 className="section-title" dangerouslySetInnerHTML={{ __html: t('features.title') }} />
          <p className="section-desc">{t('features.desc')}</p>
        </motion.div>

        <div className="feat-grid">
          {features.map((feat, index) => (
            <motion.div
              key={feat.key}
              className="feat-card"
              initial={{ opacity: 0, y: 25 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.1 }}
              transition={{
                duration: 0.6,
                delay: 0.05 + index * 0.1,
                ease: [0.16, 1, 0.3, 1],
              }}
              whileHover={{ y: -4, boxShadow: '0 20px 40px rgba(13,27,62,0.12)' }}
            >
              <div className="feat-icon">
                <feat.Icon size={22} strokeWidth={1.7} color="var(--blue)" />
              </div>
              <div className="feat-title">
                {t(`features.card_${feat.key}_title`)}
                {feat.badge && (
                  <span style={{ marginLeft: '6px' }}>
                    <Badge variant="soon">{t('features.soon_badge')}</Badge>
                  </span>
                )}
              </div>
              <p className="feat-desc">{t(`features.card_${feat.key}_desc`)}</p>
            </motion.div>
          ))}
        </div>

        {/* Comparatif intégré — toggle */}
        <motion.div
          style={{ paddingBottom: '40px' }}
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.1 }}
          transition={{ duration: 0.7, ease: [0.4, 0, 0.2, 1] }}
        >
          <div style={{ display: 'flex', justifyContent: 'center', marginTop: '40px' }}>
            <button
              onClick={() => setShowComparison((v) => !v)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 22px',
                borderRadius: '999px',
                border: '1.5px solid var(--blue)',
                background: showComparison ? 'var(--blue)' : 'transparent',
                color: showComparison ? 'white' : 'var(--blue)',
                fontWeight: 600,
                fontSize: '14px',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                fontFamily: 'inherit',
              }}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 6h18M3 12h18M3 18h18" />
              </svg>
              {t('comparison.label')}
              <svg
                width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
                strokeLinecap="round" strokeLinejoin="round"
                style={{ transform: showComparison ? 'rotate(180deg)' : 'none', transition: 'transform 0.3s ease' }}
              >
                <path d="M6 9l6 6 6-6" />
              </svg>
            </button>
          </div>

          <AnimatePresence>
            {showComparison && (
              <motion.div
                key="comparison"
                initial={{ opacity: 0, height: 0, marginTop: 0 }}
                animate={{ opacity: 1, height: 'auto', marginTop: 0 }}
                exit={{ opacity: 0, height: 0, marginTop: 0 }}
                transition={{ duration: 0.45, ease: [0.4, 0, 0.2, 1] }}
                style={{ overflow: 'hidden' }}
              >
                <ComparisonContent />
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </div>
    </section>
  );
}
