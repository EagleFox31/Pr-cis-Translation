import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'motion/react';
import { ArrowRight, Facebook, Linkedin, Mail, MessageCircle, Phone, X } from 'lucide-react';

import { useAuth } from '../../contexts/AuthContext';
import { openSupport } from '../support/supportBus';

const CONTACT_EMAIL = 'support.precis@trigenys.com';
const LINKEDIN_URL = 'https://www.linkedin.com/company/trigenys-group';
const INSIGHT_URL = 'https://insight.trigenys.com/fr';
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
        <div className="about-layout">
          {/* Le hibou est bleu nuit : il repose sur un médaillon clair pour rester net sur le fond sombre. */}
          <motion.figure
            className="about-seal"
            initial={{ opacity: 0, y: 28 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
          >
            <img src="/Identite Precis.png" alt="" aria-hidden="true" className="about-mascot" />
            <figcaption>
              <span className="about-seal-label">{t('about.card_label')}</span>
              <strong>Trigenys Group</strong>
              <span className="about-seal-also">
                {t('about.card_products_label')} AgenStudio, <a href={INSIGHT_URL} target="_blank" rel="noopener noreferrer">Trigenys Insight</a>
              </span>
            </figcaption>
          </motion.figure>

          <div className="about-body">
            <h2 className="about-title" dangerouslySetInnerHTML={{ __html: t('about.title') }} />
            <p className="about-text">{t('about.desc')}</p>

            <ol className="about-pledges">
              {PLEDGES.map((key, i) => (
                <motion.li
                  key={key}
                  initial={{ opacity: 0, y: 12 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.15 + 0.1 * i, duration: 0.5 }}
                >
                  <span className="about-pledge-num" aria-hidden="true">{String(i + 1).padStart(2, '0')}</span>
                  <strong>{t(`about.pledge_${key}`)}</strong>
                  <span>{t(`about.pledge_${key}_desc`)}</span>
                </motion.li>
              ))}
            </ol>

            <div className="about-contact">
              <button type="button" className="about-cta" onClick={contact}>
                {t('about.contact_cta')}
                <ArrowRight size={18} aria-hidden="true" />
              </button>
              <a className="about-mail" href={`mailto:${CONTACT_EMAIL}`}>
                <Mail size={15} aria-hidden="true" />
                {CONTACT_EMAIL}
              </a>
              <span className="about-social">
                <a href={LINKEDIN_URL} target="_blank" rel="noopener noreferrer"><Linkedin size={15} aria-hidden="true" />LinkedIn</a>
                <a href={FACEBOOK_URL} target="_blank" rel="noopener noreferrer"><Facebook size={15} aria-hidden="true" />Facebook</a>
              </span>
            </div>
          </div>
        </div>
      </div>
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

  const links = [
    { to: '/mentions-legales', label: t('footer.legal') },
    { to: '/conditions', label: t('footer.terms') },
    { to: '/confidentialite', label: t('footer.privacy') },
    { to: '/fonctionnalites', label: t('nouveautes.footer_link') },
    { to: '/extension', label: t('extension_page.footer_link') },
    { to: '/cookies', label: t('footer.cookies') },
  ];

  return (
    // div et non <footer> : la règle globale `footer` (pied sombre des autres pages) s'appliquerait.
    <div className="about-footer">
      <div className="about-footer-row">
        <nav aria-label={t('footer.nav_label')}>
          <ul className="about-footer-links">
            {links.map(({ to, label }) => (
              <li key={to}><Link to={to}>{label}</Link></li>
            ))}
          </ul>
        </nav>
        <p className="about-footer-rights">{t('footer.rights')}</p>
      </div>
    </div>
  );
}
