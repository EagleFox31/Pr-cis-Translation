import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { LEGAL_FR, LEGAL_UPDATED as UPDATED_FR } from '../content/legal/fr';
import { LEGAL_EN, LEGAL_UPDATED as UPDATED_EN } from '../content/legal/en';
import type { LegalDoc } from '../content/legal/types';
import MobileMenu from '../components/navbar/MobileMenu';
import '../components/admin/admin.css';
import '../legal.css';

const CONTACT_EMAIL = 'contact@trigenys.com';

export default function LegalPage({ slug }: { slug: LegalDoc['slug'] }) {
  const { t, i18n } = useTranslation();
  const fr = (i18n.language || 'fr').startsWith('fr');
  const docs = fr ? LEGAL_FR : LEGAL_EN;
  const updated = fr ? UPDATED_FR : UPDATED_EN;
  const doc = docs.find((d) => d.slug === slug) ?? docs[0];

  const scrollRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const links = docs.map((d) => ({ id: `/${d.slug}`, href: `/${d.slug}`, label: d.title }));

  useEffect(() => {
    document.title = `${doc.title} · Précis`;
    scrollRef.current?.scrollTo(0, 0);
  }, [doc.title, slug]);

  return (
    <div className="legal-page">
      {/* Même barre que l'administration : logo, documents au centre, FR/EN. */}
      <nav className="navbar scrolled">
        <div className="nav-inner">
          <Link to="/" className="nav-logo" title={t('legal.back')}>
            <img src="/Logo.png" alt="P" style={{ height: '46px', width: 'auto' }} />
            <span className="animated-logo-text">
              {'récis'.split('').map((c, i) => (
                <span key={i} style={{ animationDelay: `${i / 10}s` }}>{c}</span>
              ))}
            </span>
          </Link>

          <ul className="nav-links" aria-label={t('legal.nav_label')}>
            {links.map((l) => (
              <li key={l.id}><NavLink to={l.href}>{l.label}</NavLink></li>
            ))}
          </ul>

          <div className="lang-toggle">
            <button className={fr ? 'active' : ''} onClick={() => i18n.changeLanguage('fr')}>FR</button>
            <button className={fr ? '' : 'active'} onClick={() => i18n.changeLanguage('en')}>EN</button>
          </div>

          <button className="hamburger" onClick={() => setMenuOpen((v) => !v)} aria-label="Toggle menu" aria-expanded={menuOpen}>
            <span style={{ transform: menuOpen ? 'rotate(45deg) translate(5px, 5px)' : 'none' }} />
            <span style={{ opacity: menuOpen ? 0 : 1 }} />
            <span style={{ transform: menuOpen ? 'rotate(-45deg) translate(5px, -5px)' : 'none' }} />
          </button>
        </div>
      </nav>

      <MobileMenu
        isOpen={menuOpen} links={links} activeSection={`/${doc.slug}`}
        onNavClick={(to) => { setMenuOpen(false); navigate(to); }} onClose={() => setMenuOpen(false)}
      />

      {/* La page tient dans l'écran : Retour et titre restent fixes, seul le texte défile. */}
      <main className="legal-main">
        <div className="legal-head">
          <div className="legal-head__inner">
            <Link to="/" className="tb-btn ghost admin-btn legal-back">
              <ArrowLeft size={15} strokeWidth={2.2} /> <span>{t('admin.back', 'Retour')}</span>
            </Link>
            <h1>{doc.title}</h1>
            <span className="legal-updated">{t('legal.updated', { date: updated })}</span>
          </div>
        </div>

        <div className="legal-scroll" ref={scrollRef}>
          <div className="legal-body">
            <p className="legal-intro">{doc.intro}</p>
            <article className="legal-article">
              {doc.sections.map((section, i) => (
                <section key={section.heading} className="legal-section">
                  <h2>
                    <span className="legal-section__num">{i + 1}.</span>
                    {section.heading}
                  </h2>
                  {section.paragraphs.map((p) => (
                    <p key={p}>{p}</p>
                  ))}
                  {section.list && (
                    <ul>
                      {section.list.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  )}
                </section>
              ))}

              <p className="legal-contact">
                {t('legal.question')} <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
              </p>
            </article>
          </div>
        </div>
      </main>
    </div>
  );
}
