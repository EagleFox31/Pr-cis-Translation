/**
 * Barre du haut partagée par les pages hors accueil (administration, intégrations).
 *
 * POURQUOI : chaque famille de pages avait sa copie de la barre, et les copies
 * dérivaient (sortie à des places différentes, avatar absent). Une seule barre :
 * logo, menu central, « Retour à l'accueil », FR/EN, avatar, menu mobile.
 * Voir docs/etude-navigation-integrations.md.
 *
 * Réutilise les classes `.navbar/.nav-inner/.nav-links/.lang-toggle` d'`index.css`.
 */
import type { ReactNode } from 'react';
import { lazy, Suspense, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

import { useAuth } from '../../contexts/AuthContext';
import MobileMenu from './MobileMenu';
import '../admin/admin.css';

// Tiroir « Mes documents » : chargé à la première ouverture seulement.
const BibliothequeHote = lazy(() => import('../library/BibliothequeHote'));

export interface AppBarLink {
  href: string;
  label: string;
  /** Pastille après le libellé (ex. « Bientôt »), barre large seulement. */
  badge?: ReactNode;
}

interface AppBarProps {
  /** Menu central ; vide → ni menu ni hamburger. */
  links?: AppBarLink[];
  linksLabel?: string;
  /** Bouton « Retour à l'accueil » dans la barre. */
  exit?: boolean;
  /** Accueil visé par le logo, la sortie et l'avatar (défaut : `/home` connecté, `/` sinon). */
  home?: string;
}

export default function AppBar({ links = [], linksLabel, exit = false, home }: AppBarProps) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { user } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  // `null` : jamais ouvert (rien de monté) ; ensuite reste monté pour l'animation de fermeture.
  const [biblio, setBiblio] = useState<boolean | null>(null);
  const fr = (i18n.language || 'fr').startsWith('fr');
  const accueil = home ?? (user ? '/home' : '/');
  const retour = t('admin.back_home', 'Retour à l’accueil');
  const menu = links.map((l) => ({ id: l.href, href: l.href, label: l.label }));
  const avatarLetter = user?.name ? user.name[0].toUpperCase() : (user?.email?.[0].toUpperCase() || '?');

  return (
    <>
      <nav className="navbar scrolled">
        <div className="nav-inner">
          <button
            onClick={() => navigate(accueil)}
            className="nav-logo"
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
            title={retour}
          >
            <img src="/Logo.png" alt="P" style={{ height: '46px', width: 'auto' }} />
            <span className="animated-logo-text">
              {'récis'.split('').map((c, i) => (
                <span key={i} style={{ animationDelay: `${i / 10}s` }}>{c}</span>
              ))}
            </span>
          </button>

          {links.length > 0 && (
            <ul className="nav-links" aria-label={linksLabel}>
              {links.map((l) => (
                <li key={l.href}>
                  <NavLink to={l.href} className={l.badge ? 'ext-nav-lien' : undefined}>
                    {l.label}
                    {l.badge}
                  </NavLink>
                </li>
              ))}
            </ul>
          )}

          {exit && (
            // Sortie explicite : le logo ramène aussi à l'accueil, mais ne se devine pas.
            <button onClick={() => navigate(accueil)} className="tb-btn ghost admin-btn admin-exit" title={retour}>
              <ArrowLeft size={15} strokeWidth={2.2} /> <span>{retour}</span>
            </button>
          )}

          <div className="lang-toggle">
            <button className={fr ? 'active' : ''} onClick={() => i18n.changeLanguage('fr')}>FR</button>
            <button className={fr ? '' : 'active'} onClick={() => i18n.changeLanguage('en')}>EN</button>
          </div>

          {user && (
            <button
              onClick={() => setBiblio(true)}
              title={t('admin.my_account', 'Mon compte')}
              aria-haspopup="dialog"
              style={{
                width: '34px', height: '34px', borderRadius: '999px',
                background: 'var(--blue)', color: 'white', border: 'none',
                fontWeight: 700, fontSize: '14px', cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: 'inherit', flexShrink: 0,
              }}
            >{avatarLetter}</button>
          )}

          {links.length > 0 && (
            <button className="hamburger" onClick={() => setMenuOpen((v) => !v)} aria-label="Toggle menu" aria-expanded={menuOpen}>
              <span style={{ transform: menuOpen ? 'rotate(45deg) translate(5px, 5px)' : 'none' }} />
              <span style={{ opacity: menuOpen ? 0 : 1 }} />
              <span style={{ transform: menuOpen ? 'rotate(-45deg) translate(5px, -5px)' : 'none' }} />
            </button>
          )}
        </div>
      </nav>

      {user && biblio !== null && (
        <Suspense fallback={null}>
          <BibliothequeHote isOpen={biblio} onClose={() => setBiblio(false)} />
        </Suspense>
      )}

      {links.length > 0 && (
        <MobileMenu
          isOpen={menuOpen} links={menu} activeSection={pathname}
          onNavClick={(to) => { setMenuOpen(false); navigate(to); }} onClose={() => setMenuOpen(false)}
        />
      )}
    </>
  );
}
