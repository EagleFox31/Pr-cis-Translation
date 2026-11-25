import { useTranslation } from 'react-i18next';
import { motion } from 'motion/react';
import { FileSignature, Globe2, Plane } from 'lucide-react';

// Deux blocs qui manquaient à la page d'accueil pour un visiteur venu d'un
// annuaire ou d'un forum : à qui s'adresse le produit, et les cinq questions
// qu'il se pose avant de créer un compte. Même grille de cartes que les
// fonctionnalités (`.feat-grid`, `.feat-card`) : aucun style nouveau pour
// les cartes, seulement pour la liste des questions (`.faq-list`).

const AUDIENCES = [
  { key: 'translators', Icon: FileSignature },
  { key: 'immigration', Icon: Plane },
  { key: 'offices', Icon: Globe2 },
] as const;

const QUESTIONS = ['certified', 'formats', 'scans', 'data', 'trial'] as const;

const reveal = {
  initial: { opacity: 0, y: 20 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, amount: 0.1 },
  transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] as const },
};

export default function AudienceSection() {
  const { t } = useTranslation();

  return (
    <>
      <section className="features-section" id="audience">
        <div className="section-inner">
          <motion.div className="features-header-block" {...reveal}>
            <div className="section-tag">{t('audience.tag')}</div>
            <h2 className="section-title" dangerouslySetInnerHTML={{ __html: t('audience.title') }} />
            <p className="section-desc">{t('audience.desc')}</p>
          </motion.div>

          <div className="feat-grid">
            {AUDIENCES.map((a, index) => (
              <motion.div
                key={a.key}
                className="feat-card"
                initial={{ opacity: 0, y: 25 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.1 }}
                transition={{ duration: 0.6, delay: 0.05 + index * 0.1, ease: [0.16, 1, 0.3, 1] }}
              >
                <div className="feat-icon">
                  <a.Icon size={22} strokeWidth={1.7} />
                </div>
                <div className="feat-title">{t(`audience.card_${a.key}_title`)}</div>
                <p className="feat-desc">{t(`audience.card_${a.key}_desc`)}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section className="features-section" id="faq">
        <div className="section-inner">
          <motion.div className="features-header-block" {...reveal}>
            <div className="section-tag">{t('faq.tag')}</div>
            <h2 className="section-title" dangerouslySetInnerHTML={{ __html: t('faq.title') }} />
          </motion.div>

          <div className="faq-list">
            {QUESTIONS.map((q) => (
              <details key={q} className="faq-item">
                <summary>{t(`faq.q_${q}`)}</summary>
                <p>{t(`faq.a_${q}`)}</p>
              </details>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
