import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowLeft, Check, Download, Monitor } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import MobileMenu from '../components/navbar/MobileMenu';
import { useExtensionInstalled } from '../hooks/useExtensionInstalled';
import {
  detecterNavigateurPrecis, estMobile, EXTENSION_URL, EXTENSION_ZIP, versionPlusAncienne,
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
type NavId = (typeof NAVIGATEURS)[number]['id'];
type Copie = 'idle' | 'ok' | 'erreur';

const FAQ = ['browsers', 'account', 'data', 'uninstall'] as const;
const PERMISSIONS = ['storage', 'tab', 'sites', 'send', 'sale'] as const;

// Rubriques du menu latéral : l'ancre de l'adresse ouvre directement la bonne.
const RUBRIQUES = [
  { id: 'install', cle: 'extension_page.tab_install' },
  { id: 'price', cle: 'extension_page.price.title' },
  { id: 'perms', cle: 'extension_page.permissions.title' },
  { id: 'faq', cle: 'extension_page.faq.title' },
] as const;
type Rubrique = (typeof RUBRIQUES)[number]['id'];

const rubriqueInitiale = (): Rubrique => {
  const h = window.location.hash.slice(1);
  return RUBRIQUES.some((r) => r.id === h) ? (h as Rubrique) : 'install';
};

export default function ExtensionPage() {
  const { t, i18n } = useTranslation();
  const fr = (i18n.language || 'fr').startsWith('fr');
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [copie, setCopie] = useState<Copie>('idle');

  const precis = detecterNavigateurPrecis();
  const [choix, setChoix] = useState<NavId>(precis === 'autre' ? 'chrome' : precis);
  const [rubrique, setRubrique] = useState<Rubrique>(rubriqueInitiale);

  const mobile = estMobile();
  const { installe, version } = useExtensionInstalled();
  const bienvenue = params.get('bienvenue') === '1';

  // Guide du navigateur choisi : sa boutique (Edge Add-ons ou Chrome Web Store).
  const nomChoix = NAVIGATEURS.find((n) => n.id === choix)!.nom;
  const boutique: Boutique = choix === 'edge' ? 'edge' : 'chrome';
  const urlBoutique = EXTENSION_URL[boutique];
  const miseAJour = !urlBoutique && installe && !!version && !!EXTENSION_ZIP.version
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

  const choisirRubrique = (r: Rubrique) => {
    setRubrique(r);
    window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}#${r}`);
    scrollRef.current?.scrollTo(0, 0);
  };

  const choisirNavigateur = (id: NavId) => {
    setChoix(id);
  };

  const copierLien = async () => {
    try {
      await navigator.clipboard.writeText(`${window.location.origin}/extension`);
      setCopie('ok');
    } catch {
      setCopie('erreur');
    }
  };

  const telecharger = (libelle: string) => (
    <a className="ext-btn ext-btn--primary" href={EXTENSION_ZIP.url} download="precis-extension.zip">
      <Download size={16} strokeWidth={2.2} aria-hidden="true" />
      {libelle}
    </a>
  );

  // État en tête de l'installation : mobile (copier le lien) ou extension déjà présente.
  const statut = () => {
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
            {version ? t('extension_page.installed', { version }) : t('extension_page.installed_nov')}
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
    return null;
  };

  const etape = (num: number, titre: string, texte: string) => (
    <li key={num}>
      <span className="ext-steps__num" aria-hidden="true">{num}</span>
      <div>
        <strong>{titre}</strong>
        <p>{texte}</p>
      </div>
    </li>
  );

  const etapes = (['add', 'pin', 'use'] as const).map((k, i) =>
    etape(i + 1, t(`extension_page.how.${k}_title`), t(`extension_page.how.${k}_text`)));


  // En-tête fixe, pleine largeur : accroche, statut et choix du navigateur.
  const entete = (
    <>
      <section className="ext-hero">
        <p className="ext-hero__lead">{t('extension_page.lead')}</p>
        {statut()}
      </section>

      {!mobile && (
          <div className="ext-browsers ext-pick">
            <p className="ext-browsers__title" id="ext-pick">{t('extension_page.cards_title')}</p>
            <div className="ext-browsers__grid" role="radiogroup" aria-labelledby="ext-pick">
              {NAVIGATEURS.map((n) => (
                <button
                  key={n.id} type="button" role="radio" aria-checked={choix === n.id}
                  className={`ext-browser${choix === n.id ? ' ext-browser--current' : ''}`}
                  onClick={() => choisirNavigateur(n.id)}
                >
                  {n.id === precis && <span className="ext-browser__badge">{t('extension_page.card_detected')}</span>}
                  <img className="ext-browser__logo" src={`/browsers/${n.id}.png`} alt="" width={48} height={48} />
                  <span className="ext-browser__name">{n.nom}</span>
                </button>
              ))}
            </div>
            <p className="ext-cta__hint">{t('extension_page.card_unsupported')}</p>
          </div>
      )}
    </>
  );

  const installation = mobile ? null : (
        <section className="ext-section ext-guide" aria-labelledby="ext-guide-title">
          <div className="ext-install">
            <div className="ext-install__steps">
              <h2 id="ext-guide-title">{t('extension_page.install_for', { browser: nomChoix })}</h2>
              <p>{t('extension_page.card_one_click')}</p>
              <ol className="ext-steps">{etapes}</ol>
            </div>

            <aside className="ext-install__card" aria-label={nomChoix}>
              <img src={`/browsers/${choix}.png`} alt="" width={64} height={64} />
              <strong>{nomChoix}</strong>
              <span className="ext-browser__sub">{t(`extension_page.card_via_${boutique}`)}</span>
              {urlBoutique ? (
                <a className="ext-btn ext-btn--primary" href={urlBoutique} target="_blank" rel="noopener">
                  <Download size={16} strokeWidth={2.2} aria-hidden="true" />
                  {t('extension_page.download_for', { browser: nomChoix })}
                </a>
              ) : (
                <button type="button" className="ext-btn ext-btn--ghost" disabled>{t('extension_page.soon')}</button>
              )}
            </aside>
          </div>
        </section>
  );

  const contenu = () => {
    switch (rubrique) {
      case 'price':
        return (
          <section className="ext-section" aria-labelledby="ext-price">
            <h2 id="ext-price">{t('extension_page.price.title')}</h2>
            <p>{t('extension_page.price.text')}</p>
            <p><Link className="ext-link" to="/home#pricing">{t('extension_page.price.link')}</Link></p>
          </section>
        );
      case 'perms':
        return (
          <section className="ext-section" aria-labelledby="ext-perms">
            <h2 id="ext-perms">{t('extension_page.permissions.title')}</h2>
            <ul className="ext-list">
              {PERMISSIONS.map((k) => <li key={k}>{t(`extension_page.permissions.${k}`)}</li>)}
            </ul>
            <p><Link className="ext-link" to="/confidentialite">{t('extension_page.permissions.privacy')}</Link></p>
          </section>
        );
      case 'faq':
        return (
          <section className="ext-section" aria-labelledby="ext-faq">
            <h2 id="ext-faq">{t('extension_page.faq.title')}</h2>
            {FAQ.map((k) => (
              <details key={k} className="ext-faq">
                <summary>{t(`extension_page.faq.${k}_q`)}</summary>
                <p>{t(`extension_page.faq.${k}_a`)}</p>
              </details>
            ))}
          </section>
        );
      default:
        return installation;
    }
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

            {entete}

            <div className="ext-layout">
              <nav className="ext-menu" aria-label={t('extension_page.menu_title')}>
                <p className="ext-menu__title">{t('extension_page.menu_title')}</p>
                <ul>
                  {RUBRIQUES.map((r) => (
                    <li key={r.id}>
                      <button
                        type="button" className={`ext-menu__item${rubrique === r.id ? ' is-active' : ''}`}
                        aria-current={rubrique === r.id ? 'page' : undefined}
                        onClick={() => choisirRubrique(r.id)}
                      >
                        {t(r.cle)}
                      </button>
                    </li>
                  ))}
                </ul>
              </nav>

              <div className="ext-content">{contenu()}</div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
