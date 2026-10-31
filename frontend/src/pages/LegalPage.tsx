import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { LEGAL_FR, LEGAL_UPDATED as UPDATED_FR } from '../content/legal/fr';
import { LEGAL_EN, LEGAL_UPDATED as UPDATED_EN } from '../content/legal/en';
import type { LegalDoc } from '../content/legal/types';
import '../legal.css';

const CONTACT_EMAIL = 'contact@trigenys.com';

export default function LegalPage({ slug }: { slug: LegalDoc['slug'] }) {
  const { t, i18n } = useTranslation();
  const fr = (i18n.language || 'fr').startsWith('fr');
  const docs = fr ? LEGAL_FR : LEGAL_EN;
  const updated = fr ? UPDATED_FR : UPDATED_EN;
  const doc = docs.find((d) => d.slug === slug) ?? docs[0];

  useEffect(() => {
    document.title = `${doc.title} · Précis`;
    window.scrollTo(0, 0);
  }, [doc.title, slug]);

  return (
    <div className="legal-page">
      <header className="legal-topbar">
        <div className="legal-topbar__inner">
          <Link to="/" className="legal-back">{t('legal.back')}</Link>
          <span className="legal-topbar__title">Trigenys Group</span>
        </div>
      </header>

      <div className="legal-shell">
        <div className="legal-layout">
          <nav className="legal-nav" aria-label={t('legal.nav_label')}>
            {docs.map((d) => (
              <Link
                key={d.slug}
                to={`/${d.slug}`}
                aria-current={d.slug === doc.slug ? 'page' : undefined}
              >
                {d.title}
              </Link>
            ))}
          </nav>

          <div className="legal-main">
            <div className="legal-head">
              <div className="section-tag">{t('legal.tag')}</div>
              <h1>{doc.title}</h1>
              <p className="legal-updated">{t('legal.updated', { date: updated })}</p>
              <p className="legal-intro">{doc.intro}</p>
            </div>
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
      </div>
    </div>
  );
}
