/**
 * Coquille commune aux pages d'administration (`/admin/*`).
 *
 * POURQUOI : sans elle, ces pages s'ouvraient sur un fond nu, sans en-tête —
 * on avait l'impression de quitter Précis pour un autre logiciel. La coquille
 * REMET la barre de l'application (même logo, même verre dépoli, même bascule
 * FR/EN) au-dessus d'un contenu cadré comme le reste du site. Le menu central
 * de la barre porte les pages admin (docs/etude-menu-admin.md) : une seule
 * navigation, à la place de l'ancien menu déroulant et des onglets sous le titre.
 *
 * L'en-tête réutilise les classes `.navbar/.nav-inner/.lang-toggle` d'`index.css`
 * — c'est littéralement la même barre, pas une imitation qui dériverait.
 */
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

import { useAuth } from '../../contexts/AuthContext';
import MobileMenu from '../navbar/MobileMenu';
import { AdminStats, type AdminStat } from './AdminParts';
import './admin.css';

const logo = '/Logo.png';

/** Pages admin, dans l'ordre des onglets (libellés : `admin.tabs.<clé>`). */
const TABS = [
  { key: 'users', to: '/admin/users', label: 'Comptes' },
  { key: 'documents', to: '/admin/documents', label: 'Documents' },
  { key: 'support', to: '/admin/support', label: 'Assistance' },
  { key: 'logs', to: '/admin/logs', label: 'Journal' },
  { key: 'beta', to: '/admin/beta', label: 'Bêta' },
] as const;

interface AdminShellProps {
  title: string;
  /** Sous-titre discret à droite du titre (ex. « 7 compte(s) »). */
  count?: string;
  /** Boutons d'action de la page (Rafraîchir, Exporter…). */
  actions?: ReactNode;
  /** Tuiles de chiffres clés, affichées sous l'en-tête. */
  stats?: AdminStat[];
  /** Onglets d'administration (faux pour une page publique comme `/beta`). */
  tabs?: boolean;
  children: ReactNode;
}

export default function AdminShell({ title, count, actions, stats, tabs = true, children }: AdminShellProps) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { user } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  // Jamais montré à un non-admin : il trahirait les pages internes.
  const showTabs = tabs && user?.plan === 'admin';
  const tabLinks = TABS.map((tab) => ({ id: tab.to, href: tab.to, label: t(`admin.tabs.${tab.key}`, tab.label) }));

  const avatarLetter = user?.name
    ? user.name[0].toUpperCase()
    : (user?.email?.[0].toUpperCase() || '?');

  return (
    <div className="admin-page">
      {/* En-tête de l'application — la vraie barre, réutilisée telle quelle */}
      <nav className="navbar scrolled">
        <div className="nav-inner">
          <button
            onClick={() => navigate('/home')}
            className="nav-logo"
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
            title={t('admin.back_home', 'Retour à l’accueil')}
          >
            <img src={logo} alt="P" style={{ height: '46px', width: 'auto' }} />
            <span className="animated-logo-text">
              <span style={{ animationDelay: '0.0s' }}>r</span>
              <span style={{ animationDelay: '0.1s' }}>é</span>
              <span style={{ animationDelay: '0.2s' }}>c</span>
              <span style={{ animationDelay: '0.3s' }}>i</span>
              <span style={{ animationDelay: '0.4s' }}>s</span>
            </span>
          </button>

          {showTabs && (
            <ul className="nav-links" aria-label={t('admin.tabs_label', 'Pages d’administration')}>
              {tabLinks.map((tab) => (
                <li key={tab.id}><NavLink to={tab.href}>{tab.label}</NavLink></li>
              ))}
            </ul>
          )}

          {showTabs && (
            // Sortie explicite : le logo ramène aussi à l'accueil, mais ne se devine pas.
            <button onClick={() => navigate('/home')} className="tb-btn ghost admin-btn admin-exit" title={t('admin.back_home', 'Retour à l’accueil')}>
              <ArrowLeft size={15} strokeWidth={2.2} /> <span>{t('admin.back_home', 'Retour à l’accueil')}</span>
            </button>
          )}

          <div className="lang-toggle">
            <button className={i18n.language === 'fr' ? 'active' : ''} onClick={() => i18n.changeLanguage('fr')}>FR</button>
            <button className={i18n.language === 'en' ? 'active' : ''} onClick={() => i18n.changeLanguage('en')}>EN</button>
          </div>

          <button
            onClick={() => navigate('/home')}
            title={t('admin.my_account', 'Mon compte')}
            style={{
              width: '34px', height: '34px', borderRadius: '999px',
              background: 'var(--blue)', color: 'white', border: 'none',
              fontWeight: 700, fontSize: '14px', cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: 'inherit', flexShrink: 0,
            }}
          >{avatarLetter}</button>

          {showTabs && (
            <button className="hamburger" onClick={() => setMenuOpen((v) => !v)} aria-label="Toggle menu" aria-expanded={menuOpen}>
              <span style={{ transform: menuOpen ? 'rotate(45deg) translate(5px, 5px)' : 'none' }} />
              <span style={{ opacity: menuOpen ? 0 : 1 }} />
              <span style={{ transform: menuOpen ? 'rotate(-45deg) translate(5px, -5px)' : 'none' }} />
            </button>
          )}
        </div>
      </nav>

      {showTabs && (
        <MobileMenu
          isOpen={menuOpen} links={tabLinks} activeSection={pathname}
          onNavClick={(to) => { setMenuOpen(false); navigate(to); }} onClose={() => setMenuOpen(false)}
        />
      )}

      {/* Contenu : décalé sous la barre fixe, cadré comme le reste du site */}
      <main className="admin-main">
        <div className="admin-frame">
          <div className="admin-head">
            {/* Sans menu (page publique /beta), seul chemin visible vers l'accueil. */}
            {!showTabs && (
              <button onClick={() => navigate('/home')} className="tb-btn ghost admin-btn">
                <ArrowLeft size={15} strokeWidth={2.2} /> {t('admin.back', 'Retour')}
              </button>
            )}
            <h1>{title}</h1>
            {count && <span className="admin-head__count">{count}</span>}
            {actions && <div className="admin-head__actions">{actions}</div>}
          </div>

          {stats && stats.length > 0 && <AdminStats items={stats} />}

          {children}
        </div>
      </main>
    </div>
  );
}
