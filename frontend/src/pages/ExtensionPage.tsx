import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowLeft, Check, Download, Monitor } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import MobileMenu from '../components/navbar/MobileMenu';
import { useExtensionInstalled } from '../hooks/useExtensionInstalled';
import { detecterNavigateur, estMobile, EXTENSION_URL, type Navigateur } from '../lib/extension';
import '../components/admin/admin.css';
import '../legal.css';
import '../extension-page.css';

type Boutique = 'edge' | 'chrome';
type Copie = 'idle' | 'ok' | 'erreur';

const FAQ = ['browsers', 'account', 'data', 'uninstall'] as const;
const PERMISSIONS = ['storage', 'tab', 'sites', 'send', 'sale'] as const;

export default function ExtensionPage() {
  const { t, i18n } = useTranslation();
  const fr = (i18n.language || 'fr').startsWith('fr');
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [copie, setCopie] = useState<Copie>('idle');

  const navigateur: Navigateur = detecterNavigateur();
  const mobile = estMobile();
  const { installe, version } = useExtensionInstalled();
  const bienvenue = params.get('bienvenue') === '1';

  const links = [
    { id: '/home', href: '/home', label: t('nav.home') },
    { id: '/extension', href: '/extension', label: t('extension_page.nav_label') },
    { id: '/confidentialite', href: '/confidentialite', label: t('footer.privacy') },
  ];

  useEffect(() => {
    document.title = t('extension_page.doc_title');
    scrollRef.current?.scrollTo(0, 0);
  }, [t, i18n.language]);

  const libelleBoutique = (b: Boutique) => t(b === 'edge' ? 'extension_page.add_edge' : 'extension_page.add_chrome');

  // Bouton d'une boutique : lien réel si l'adresse est renseignée, sinon bouton inactif.
  const boutique = (b: Boutique, principal: boolean) => {
    const url = EXTENSION_URL[b];
    const classe = `ext-btn ${principal ? 'ext-btn--primary' : 'ext-btn--ghost'}`;
    if (!url) {
      return (
        <button type="button" className={classe} disabled>
          {principal ? t('extension_page.soon') : `${libelleBoutique(b)} · ${t('extension_page.soon')}`}
        </button>
      );
    }
    return (
      <a className={classe} href={url} target="_blank" rel="noopener">
        {principal && <Download size={16} strokeWidth={2.2} aria-hidden="true" />}
        {libelleBoutique(b)}
      </a>
    );
  };

  const copierLien = async () => {
    try {
      await navigator.clipboard.writeText(`${window.location.origin}/extension`);
      setCopie('ok');
    } catch {
      setCopie('erreur');
    }
  };

  const autre: Boutique = navigateur === 'edge' ? 'chrome' : 'edge';

  const action = () => {
    if (mobile) {
      return (
        <div className="ext-cta">
          <p className="ext-cta__note"><Monitor size={16} aria-hidden="true" /> {t('extension_page.mobile_title')}</p>
          <p className="ext-cta__hint">{t('extension_page.mobile_hint')}</p>
          <button type="button" className="ext-btn ext-btn--primary" onClick={copierLien}>
            {t('extension_page.copy_link')}
          </button>
          <span className="ext-cta__status" role="status">
            {copie === 'ok' && t('extension_page.copied')}
            {copie === 'erreur' && t('extension_page.copy_error')}
          </span>
        </div>
      );
    }
    if (installe) {
      return (
        <div className="ext-cta">
          <p className="ext-installed" role="status">
            <Check size={18} strokeWidth={2.4} aria-hidden="true" />
            {version
              ? t('extension_page.installed', { version })
              : t('extension_page.installed_nov')}
          </p>
        </div>
      );
    }
    if (navigateur === 'autre') {
      return (
        <div className="ext-cta">
          <p className="ext-cta__note">{t('extension_page.other_browser')}</p>
          <div className="ext-cta__row">
            {boutique('chrome', false)}
            {boutique('edge', false)}
          </div>
        </div>
      );
    }
    return (
      <div className="ext-cta">
        <div className="ext-cta__row">{boutique(navigateur, true)}</div>
        {EXTENSION_URL[autre] && (
          <a className="ext-link" href={EXTENSION_URL[autre]} target="_blank" rel="noopener">
            {t(autre === 'edge' ? 'extension_page.also_edge' : 'extension_page.also_chrome')}
          </a>
        )}
      </div>
    );
  };

  return (
    <div className="legal-page ext-page">
      <nav className="navbar scrolled">
        <div className="nav-inner">
          <Link to="/" className="nav-logo" title={t('extension_page.back')}>
            <img src="/Logo.png" alt="P" style={{ height: '46px', width: 'auto' }} />
            <span className="animated-logo-text">
              {'récis'.split('').map((c, i) => (
                <span key={i} style={{ animationDelay: `${i / 10}s` }}>{c}</span>
              ))}
            </span>
          </Link>

          <ul className="nav-links" aria-label={t('extension_page.nav_aria')}>
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
        isOpen={menuOpen} links={links} activeSection="/extension"
        onNavClick={(to) => { setMenuOpen(false); navigate(to); }} onClose={() => setMenuOpen(false)}
      />

      <main className="legal-main">
        <div className="legal-head">
          <div className="legal-head__inner">
            <Link to="/" className="tb-btn ghost admin-btn legal-back">
              <ArrowLeft size={15} strokeWidth={2.2} /> <span>{t('extension_page.back')}</span>
            </Link>
            <h1>{t('extension_page.title')}</h1>
          </div>
        </div>

        <div className="legal-scroll" ref={scrollRef}>
          <div className="legal-body ext-body">
            {bienvenue && (
              <section className="ext-welcome" aria-labelledby="ext-welcome-title">
                <h2 id="ext-welcome-title">{t('extension_page.welcome.title')}</h2>
                <ol>
                  <li>{t('extension_page.welcome.pin')}</li>
                  <li>{t('extension_page.welcome.login')}</li>
                  <li>{t('extension_page.welcome.try')}</li>
                </ol>
              </section>
            )}

            <section className="ext-hero">
              <p className="ext-hero__lead">{t('extension_page.lead')}</p>
              {action()}
            </section>

            <section className="ext-section" aria-labelledby="ext-how">
              <h2 id="ext-how">{t('extension_page.how.title')}</h2>
              <ol className="ext-steps">
                {(['add', 'pin', 'use'] as const).map((k, i) => (
                  <li key={k}>
                    <span className="ext-steps__num" aria-hidden="true">{i + 1}</span>
                    <div>
                      <strong>{t(`extension_page.how.${k}_title`)}</strong>
                      <p>{t(`extension_page.how.${k}_text`)}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </section>

            <section className="ext-section" aria-labelledby="ext-price">
              <h2 id="ext-price">{t('extension_page.price.title')}</h2>
              <p>{t('extension_page.price.text')}</p>
              <p><Link className="ext-link" to="/home#pricing">{t('extension_page.price.link')}</Link></p>
            </section>

            <section className="ext-section" aria-labelledby="ext-perms">
              <h2 id="ext-perms">{t('extension_page.permissions.title')}</h2>
              <ul className="ext-list">
                {PERMISSIONS.map((k) => <li key={k}>{t(`extension_page.permissions.${k}`)}</li>)}
              </ul>
              <p><Link className="ext-link" to="/confidentialite">{t('extension_page.permissions.privacy')}</Link></p>
            </section>

            <section className="ext-section" aria-labelledby="ext-faq">
              <h2 id="ext-faq">{t('extension_page.faq.title')}</h2>
              {FAQ.map((k) => (
                <details key={k} className="ext-faq">
                  <summary>{t(`extension_page.faq.${k}_q`)}</summary>
                  <p>{t(`extension_page.faq.${k}_a`)}</p>
                </details>
              ))}
            </section>
          </div>
        </div>
      </main>
    </div>
  );
}
