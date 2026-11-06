import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowLeft, Check, Copy, Download, Monitor } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import MobileMenu from '../components/navbar/MobileMenu';
import { useExtensionInstalled } from '../hooks/useExtensionInstalled';
import {
  detecterNavigateur, detecterNavigateurPrecis, estMobile, EXTENSION_URL, EXTENSION_ZIP, versionPlusAncienne, type Navigateur,
} from '../lib/extension';
import '../components/admin/admin.css';
import '../legal.css';
import '../extension-page.css';

type Boutique = 'edge' | 'chrome';

// Navigateurs pris en charge (même extension) ; Edge passe par sa boutique, les autres par le Chrome Web Store.
const NAVIGATEURS = [
  { id: 'chrome', nom: 'Google Chrome' },
  { id: 'edge', nom: 'Microsoft Edge' },
  { id: 'brave', nom: 'Brave' },
  { id: 'opera', nom: 'Opera' },
  { id: 'vivaldi', nom: 'Vivaldi' },
] as const;
type Copie = 'idle' | 'ok' | 'erreur';

const FAQ = ['browsers', 'account', 'data', 'uninstall'] as const;
const PERMISSIONS = ['storage', 'tab', 'sites', 'send', 'sale'] as const;
const NOTES = ['note_folder', 'note_update', 'note_alert'] as const;

export default function ExtensionPage() {
  const { t, i18n } = useTranslation();
  const fr = (i18n.language || 'fr').startsWith('fr');
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [copie, setCopie] = useState<Copie>('idle');
  const [copieAdresse, setCopieAdresse] = useState<Copie>('idle');

  const navigateur: Navigateur = detecterNavigateur();
  const mobile = estMobile();
  const { installe, version } = useExtensionInstalled();
  const bienvenue = params.get('bienvenue') === '1';

  // Installation manuelle (ZIP) tant qu'aucune boutique n'est renseignée pour ce navigateur.
  const manuel = navigateur === 'autre' ? !EXTENSION_URL.chrome && !EXTENSION_URL.edge : !EXTENSION_URL[navigateur];
  const navManuel: Boutique = navigateur === 'edge' ? 'edge' : 'chrome';
  const pageExtensions = `${navManuel}://extensions`;
  const miseAJour = manuel && installe && !!version && !!EXTENSION_ZIP.version
    && versionPlusAncienne(version, EXTENSION_ZIP.version);

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

  // Carte d'un navigateur : logo officiel, nom, boutique d'origine et bouton (inactif tant que l'adresse manque).
  const precis = detecterNavigateurPrecis();
  const carte = (n: (typeof NAVIGATEURS)[number]) => {
    const b: Boutique = n.id === 'edge' ? 'edge' : 'chrome';
    const url = EXTENSION_URL[b];
    const courant = n.id === precis;
    return (
      <li key={n.id} className={`ext-browser${courant ? ' ext-browser--current' : ''}`}>
        {courant && <span className="ext-browser__badge">{t('extension_page.card_detected')}</span>}
        <img className="ext-browser__logo" src={`/browsers/${n.id}.png`} alt="" width={56} height={56} />
        <strong className="ext-browser__name">{n.nom}</strong>
        <span className="ext-browser__sub">{t(`extension_page.card_via_${b}`)}</span>
        {url ? (
          <a className="ext-btn ext-btn--primary" href={url} target="_blank" rel="noopener">
            <Download size={16} strokeWidth={2.2} aria-hidden="true" />
            {t('extension_page.card_add')}
          </a>
        ) : (
          <button type="button" className="ext-btn ext-btn--ghost" disabled>{t('extension_page.soon')}</button>
        )}
      </li>
    );
  };

  const ordre = [...NAVIGATEURS].sort((a, c) => Number(c.id === precis) - Number(a.id === precis));
  const cartes = (
    <div className="ext-browsers">
      <p className="ext-browsers__title">{t('extension_page.cards_title')}</p>
      <ul className="ext-browsers__grid">{ordre.map(carte)}</ul>
      <p className="ext-cta__hint">
        {!manuel && `${t('extension_page.card_one_click')} `}
        {t('extension_page.card_unsupported')}
      </p>
    </div>
  );

  const copierLien = async () => {
    try {
      await navigator.clipboard.writeText(`${window.location.origin}/extension`);
      setCopie('ok');
    } catch {
      setCopie('erreur');
    }
  };

  const copierAdresse = async () => {
    try {
      await navigator.clipboard.writeText(pageExtensions);
      setCopieAdresse('ok');
    } catch {
      setCopieAdresse('erreur');
    }
  };

  const telecharger = (libelle: string) => (
    <a className="ext-btn ext-btn--primary" href={EXTENSION_ZIP.url} download="precis-extension.zip">
      <Download size={16} strokeWidth={2.2} aria-hidden="true" />
      {libelle}
    </a>
  );

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
          {miseAJour && (
            <>
              <p className="ext-cta__hint">{t('extension_page.update_available', { version: EXTENSION_ZIP.version })}</p>
              <div className="ext-cta__row">{telecharger(t('extension_page.update_cta'))}</div>
            </>
          )}
        </div>
      );
    }
    return <div className="ext-cta">{cartes}</div>;
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

            {manuel ? (
            <details className="ext-section ext-manual" id="ext-manual">
              <summary>{t('extension_page.manual_toggle')}</summary>
              <h2>{t('extension_page.manual.title')}</h2>
              <p>{t('extension_page.manual.intro')}</p>
              <div className="ext-cta__row">{telecharger(t('extension_page.download'))}</div>
              {EXTENSION_ZIP.version && (
                <p className="ext-cta__hint">{t('extension_page.download_hint', { version: EXTENSION_ZIP.version })}</p>
              )}
              <ol className="ext-steps">
                <li>
                  <span className="ext-steps__num" aria-hidden="true">1</span>
                  <div>
                    <strong>{t('extension_page.manual.s1_title')}</strong>
                    <p>{t('extension_page.manual.s1_text')}</p>
                  </div>
                </li>
                <li>
                  <span className="ext-steps__num" aria-hidden="true">2</span>
                  <div>
                    <strong>{t('extension_page.manual.s2_title')}</strong>
                    <p>{t('extension_page.manual.s2_text', { browser: navManuel === 'edge' ? 'Microsoft Edge' : 'Google Chrome' })}</p>
                    <div className="ext-address">
                      <code>{pageExtensions}</code>
                      <button type="button" className="ext-btn ext-btn--ghost ext-btn--small" onClick={copierAdresse}>
                        <Copy size={15} strokeWidth={2.2} aria-hidden="true" />
                        {t('extension_page.manual.copy')}
                      </button>
                      <span className="ext-cta__status" role="status">
                        {copieAdresse === 'ok' && t('extension_page.manual.copied')}
                        {copieAdresse === 'erreur' && t('extension_page.copy_error')}
                      </span>
                    </div>
                  </div>
                </li>
                {(['s3', 's4'] as const).map((k, i) => (
                  <li key={k}>
                    <span className="ext-steps__num" aria-hidden="true">{i + 3}</span>
                    <div>
                      <strong>{t(`extension_page.manual.${k}_title`)}</strong>
                      <p>{t(`extension_page.manual.${k}_text_${navManuel}`)}</p>
                    </div>
                  </li>
                ))}
                <li>
                  <span className="ext-steps__num" aria-hidden="true">5</span>
                  <div>
                    <strong>{t('extension_page.manual.s5_title')}</strong>
                    <p>{t('extension_page.manual.s5_text')}</p>
                  </div>
                </li>
              </ol>
              <div className="ext-notes">
                <h3>{t('extension_page.manual.notes_title')}</h3>
                <ul className="ext-list">
                  {NOTES.map((k) => <li key={k}>{t(`extension_page.manual.${k}`)}</li>)}
                </ul>
              </div>
            </details>
            ) : (
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
            )}

            <section className="ext-section ext-section--half" aria-labelledby="ext-price">
              <h2 id="ext-price">{t('extension_page.price.title')}</h2>
              <p>{t('extension_page.price.text')}</p>
              <p><Link className="ext-link" to="/home#pricing">{t('extension_page.price.link')}</Link></p>
            </section>

            <section className="ext-section ext-section--half" aria-labelledby="ext-perms">
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
