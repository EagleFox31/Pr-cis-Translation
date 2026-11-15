import { useState } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import MobileMenu from './navbar/MobileMenu';

// Barre du haut des pages d'intégration (extension, API…) : une entrée par intégration.
export default function IntegrationsNav() {
  const { t, i18n } = useTranslation();
  const fr = (i18n.language || 'fr').startsWith('fr');
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);

  const links = [
    { id: '/extension', href: '/extension', label: t('extension_page.nav_label') },
    { id: '/integrations/api', href: '/integrations/api', label: t('extension_page.nav_api') },
  ];

  return (
    <>
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
              <li key={l.id}>
                <NavLink to={l.href} className="ext-nav-lien">
                  {l.label}
                  {l.id === '/integrations/api' && <small className="ext-nav-badge">{t('extension_page.nav_soon')}</small>}
                </NavLink>
              </li>
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
        isOpen={menuOpen} links={links} activeSection={pathname}
        onNavClick={(to) => { setMenuOpen(false); navigate(to); }} onClose={() => setMenuOpen(false)}
      />
    </>
  );
}
