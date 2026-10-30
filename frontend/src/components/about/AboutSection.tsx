import { useTranslation } from 'react-i18next';
import { motion } from 'motion/react';
import { Check, Mail, MessageCircle, Phone } from 'lucide-react';

const CONTACT_EMAIL = 'contact@trigenys.com';
const LINKEDIN_URL = 'https://www.linkedin.com/company/trigenys-group';
const FACEBOOK_URL = 'https://www.facebook.com/p/Trigenys-Group-61594499048324/';
// Numéros au format international, chiffres seuls (ex. 2376XXXXXXXX). Vides =
// lignes masquées : rien d'inventé ne s'affiche.
const PHONE = (import.meta.env.VITE_CONTACT_PHONE ?? '').replace(/\D/g, '');
const WHATSAPP = (import.meta.env.VITE_CONTACT_WHATSAPP ?? '').replace(/\D/g, '');

const PLEDGES = ['documents', 'billing', 'payment'] as const;

export default function AboutSection() {
  const { t } = useTranslation();

  return (
    <section className="about-section" id="about">
      <div className="section-inner about-inner">
        <div className="story-grid about-grid">
          <div>
            <span className="section-tag">{t('about.tag')}</span>
            <h2
              className="section-title"
              dangerouslySetInnerHTML={{ __html: t('about.title') }}
            />
            <p className="section-desc">{t('about.desc')}</p>
            <p className="about-method">{t('about.method')}</p>
            <ul className="about-pledges">
              {PLEDGES.map((key, i) => (
                <motion.li
                  key={key}
                  initial={{ opacity: 0, y: 10 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.1 * (i + 1) }}
                >
                  <Check size={18} aria-hidden="true" className="about-pledge-icon" />
                  <div>
                    <strong>{t(`about.pledge_${key}`)}</strong>
                    <span>{t(`about.pledge_${key}_desc`)}</span>
                  </div>
                </motion.li>
              ))}
            </ul>
          </div>

          <aside className="about-card" aria-labelledby="about-card-title">
            <p className="about-card-label">{t('about.card_label')}</p>
            <h3 id="about-card-title" className="about-card-name">Trigenys Group</h3>
            <dl className="about-card-facts">
              <div><dt>{t('about.card_location_label')}</dt><dd>{t('about.card_location')}</dd></div>
              <div><dt>{t('about.card_founded_label')}</dt><dd>2026</dd></div>
              <div><dt>{t('about.card_products_label')}</dt><dd>{t('about.card_products')}</dd></div>
            </dl>
            <ul className="about-card-contact">
              <li><Mail size={16} aria-hidden="true" /><a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a></li>
              {PHONE && (
                <li><Phone size={16} aria-hidden="true" /><a href={`tel:+${PHONE}`}>+{PHONE}</a></li>
              )}
              {WHATSAPP && (
                <li>
                  <MessageCircle size={16} aria-hidden="true" />
                  <a href={`https://wa.me/${WHATSAPP}`} target="_blank" rel="noopener noreferrer">WhatsApp</a>
                </li>
              )}
            </ul>
            <p className="about-card-social">
              <a href={LINKEDIN_URL} target="_blank" rel="noopener noreferrer">LinkedIn</a>
              <span aria-hidden="true">·</span>
              <a href={FACEBOOK_URL} target="_blank" rel="noopener noreferrer">Facebook</a>
            </p>
            <a className="btn-primary about-card-cta" href={`mailto:${CONTACT_EMAIL}`}>
              {t('about.contact_cta')}
            </a>
          </aside>
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
