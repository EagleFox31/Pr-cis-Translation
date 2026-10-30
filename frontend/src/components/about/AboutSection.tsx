import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { motion, AnimatePresence } from 'motion/react';
import { Check, Mail, MessageCircle, Phone, X } from 'lucide-react';

import { useAuth } from '../../contexts/AuthContext';
import { openSupport } from '../support/supportBus';

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
  const { user } = useAuth();
  const [contactOpen, setContactOpen] = useState(false);

  // Connecté : la fenêtre d'assistance existante (le ticket porte son compte).
  // Visiteur : l'assistance exige un compte, on propose donc les canaux directs.
  const contact = () => (user ? openSupport({ category: 'other' }) : setContactOpen(true));

  return (
    <section className="about-section" id="about">
      <div className="section-inner about-inner">
        <header className="about-head">
          <span className="section-tag">{t('about.tag')}</span>
          <h2
            className="section-title"
            dangerouslySetInnerHTML={{ __html: t('about.title') }}
          />
        </header>
        <div className="story-grid about-grid">
          <div className="about-story">
            <p className="about-text">{t('about.desc')}</p>
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

          <div className="about-card-wrap">
            <img src="/Identite Precis.png" alt="" aria-hidden="true" className="about-mascot" />
            <aside className="about-card" aria-labelledby="about-card-title">
              <p className="about-card-label">{t('about.card_label')}</p>
              <h3 id="about-card-title" className="about-card-name">Trigenys Group</h3>
              <dl className="about-card-facts">
                <div><dt>{t('about.card_location_label')}</dt><dd>{t('about.card_location')}</dd></div>
                <div><dt>{t('about.card_founded_label')}</dt><dd>2026</dd></div>
                <div><dt>{t('about.card_products_label')}</dt><dd>{t('about.card_products')}</dd></div>
              </dl>
              <p className="about-card-links">
                <Mail size={16} aria-hidden="true" />
                <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
                <span aria-hidden="true">·</span>
                <a href={LINKEDIN_URL} target="_blank" rel="noopener noreferrer">LinkedIn</a>
                <span aria-hidden="true">·</span>
                <a href={FACEBOOK_URL} target="_blank" rel="noopener noreferrer">Facebook</a>
              </p>
              <button type="button" className="btn-primary about-card-cta" onClick={contact}>
                {t('about.contact_cta')}
              </button>
            </aside>
          </div>
        </div>
      </div>
      {/* Integrated Footer */}
      <FooterSection />
      <ContactModal open={contactOpen} onClose={() => setContactOpen(false)} />
    </section>
  );
}

function ContactModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useTranslation();

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  const channels = [
    { key: 'email', icon: Mail, label: t('about.contact_email'), value: CONTACT_EMAIL, href: `mailto:${CONTACT_EMAIL}` },
    ...(WHATSAPP ? [{ key: 'whatsapp', icon: MessageCircle, label: t('about.contact_whatsapp'), value: `+${WHATSAPP}`, href: `https://wa.me/${WHATSAPP}` }] : []),
    ...(PHONE ? [{ key: 'phone', icon: Phone, label: t('about.contact_phone'), value: `+${PHONE}`, href: `tel:+${PHONE}` }] : []),
  ];

  // Rendu dans <body> : la section crée son propre empilement et le menu passerait devant.
  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          className="contact-overlay"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            className="contact-modal"
            role="dialog" aria-modal="true" aria-labelledby="contact-modal-title"
            initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 16 }}
            onClick={(e) => e.stopPropagation()}
          >
            <button type="button" className="contact-close" onClick={onClose} aria-label={t('about.contact_close')} autoFocus>
              <X size={18} />
            </button>
            <img src="/Identite Precis.png" alt="" aria-hidden="true" className="contact-mascot" />
            <h3 id="contact-modal-title">{t('about.contact_title')}</h3>
            <p className="contact-intro">{t('about.contact_intro')}</p>
            <ul className="contact-channels">
              {channels.map(({ key, icon: Icon, label, value, href }) => (
                <li key={key}>
                  <a href={href} {...(key === 'whatsapp' ? { target: '_blank', rel: 'noopener noreferrer' } : {})}>
                    <span className="contact-channel-icon"><Icon size={18} aria-hidden="true" /></span>
                    <span><strong>{label}</strong><small>{value}</small></span>
                  </a>
                </li>
              ))}
            </ul>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
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
