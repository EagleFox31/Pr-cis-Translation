import { useEffect } from 'react';
import { Construction } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import IntegrationsNav from '../components/IntegrationsNav';
import '../components/admin/admin.css';
import '../legal.css';
import '../extension-page.css';

// Rubriques de la fiche : titre puis puces, toutes décrites dans api_page.
const BLOCS = [
  { titre: 'features_title', puces: ['f_text', 'f_docs', 'f_images', 'f_status'] },
  { titre: 'security_title', puces: ['s_keys', 's_https', 's_limits'] },
  { titre: 'docs_title', puces: ['d_ref', 'd_examples', 'd_errors'] },
] as const;
const FAITS = ['status', 'access', 'billing', 'format'] as const;

// Page de l'API : accessible, mais l'intégration n'est pas encore ouverte.
export default function ApiPage() {
  const { t, i18n } = useTranslation();

  useEffect(() => {
    document.title = t('api_page.doc_title');
  }, [t, i18n.language]);

  return (
    <div className="legal-page ext-page">
      <IntegrationsNav />

      <main className="legal-main">
        <div className="legal-head">
          <div className="legal-head__inner">
            <h1>
              {t('api_page.title')}
              <span className="api-statut">{t('api_page.status_badge')}</span>
            </h1>
          </div>
        </div>

        <div className="legal-scroll">
          <div className="legal-body ext-body">
            <div className="api-chantier" role="status">
              <Construction size={24} strokeWidth={2} aria-hidden="true" />
              <div>
                <strong>{t('api_page.status_title')}</strong>
                <p>{t('api_page.status_text')}</p>
              </div>
            </div>

            <section className="ext-hero api-hero">
              <p className="ext-hero__lead">{t('api_page.lead')}</p>
            </section>

            <section className="admin-panel ext-panel" aria-labelledby="api-panel-title">
              <header className="admin-panel__head">
                <div>
                  <span className="admin-panel__eyebrow">{t('api_page.eyebrow')}</span>
                  <h2 id="api-panel-title">{t('api_page.panel_title')}</h2>
                  <p className="admin-panel__muted ext-panel__sub">{t('api_page.panel_sub')}</p>
                </div>
              </header>
              <div className="admin-panel__body">
                <section className="admin-panel__block">
                  <dl className="admin-panel__facts">
                    {FAITS.map((f) => (
                      <div key={f}><dt>{t(`api_page.fact_${f}`)}</dt><dd>{t(`api_page.fact_${f}_v`)}</dd></div>
                    ))}
                  </dl>
                </section>
                <div className="api-grille">
                  {BLOCS.map(({ titre, puces }) => (
                    <section key={titre} className="api-bloc">
                      <h3>{t(`api_page.${titre}`)}</h3>
                      <ul className="ext-list">
                        {puces.map((p) => <li key={p}>{t(`api_page.${p}`)}</li>)}
                      </ul>
                    </section>
                  ))}
                </div>
                <p className="admin-panel__muted">{t('api_page.notice')}</p>
              </div>
            </section>
          </div>
        </div>
      </main>
    </div>
  );
}
