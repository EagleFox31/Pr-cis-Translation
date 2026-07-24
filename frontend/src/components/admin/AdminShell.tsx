/**
 * Coquille commune aux pages d'administration (`/admin/*`).
 *
 * POURQUOI : sans elle, ces pages s'ouvraient sur un fond nu, sans en-tête —
 * on avait l'impression de quitter Précis pour un autre logiciel. La coquille
 * REMET la barre de l'application (même logo, même verre dépoli, même bascule
 * FR/EN, même menu Administration) au-dessus d'un contenu cadré comme le reste
 * du site. Une seule barre pour toutes les pages admin : on ne la refait pas
 * page par page.
 *
 * L'en-tête réutilise les classes `.navbar/.nav-inner/.lang-toggle` d'`index.css`
 * — c'est littéralement la même barre, pas une imitation qui dériverait.
 */
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

import { useAuth } from '../../contexts/AuthContext';
import AdminMenu from '../navbar/AdminMenu';

const logo = '/Logo.png';

interface AdminShellProps {
  title: string;
  /** Sous-titre discret à droite du titre (ex. « 7 compte(s) »). */
  count?: string;
  /** Boutons d'action de la page (Rafraîchir, Exporter…). */
  actions?: ReactNode;
  children: ReactNode;
}

export default function AdminShell({ title, count, actions, children }: AdminShellProps) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { user } = useAuth();

  const avatarLetter = user?.name
    ? user.name[0].toUpperCase()
    : (user?.email?.[0].toUpperCase() || '?');

  return (
    <div style={{ minHeight: '100vh', background: 'var(--gray-50, #f9fafb)' }}>
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

          <div className="lang-toggle">
            <button className={i18n.language === 'fr' ? 'active' : ''} onClick={() => i18n.changeLanguage('fr')}>FR</button>
            <button className={i18n.language === 'en' ? 'active' : ''} onClick={() => i18n.changeLanguage('en')}>EN</button>
          </div>

          <AdminMenu />

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
        </div>
      </nav>

      {/* Contenu : décalé sous la barre fixe, cadré comme le reste du site */}
      <main style={{ paddingTop: 'calc(var(--nav-h) + 28px)', paddingBottom: '48px' }}>
        <div style={{ maxWidth: 'var(--frame-max, 1200px)', margin: '0 auto', padding: '0 var(--frame-pad, 24px)' }}>

          {/* Fil d'Ariane + titre + actions */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '20px', flexWrap: 'wrap' }}>
            <button onClick={() => navigate('/home')} className="tb-btn ghost"
              style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <ArrowLeft size={15} strokeWidth={2.2} /> {t('admin.back', 'Retour')}
            </button>
            <h1 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--navy, #0d1b3e)', margin: 0 }}>
              {title}
            </h1>
            {count && (
              <span style={{ fontSize: '12px', color: 'var(--gray-500, #6b7280)' }}>{count}</span>
            )}
            {actions && (
              <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>{actions}</div>
            )}
          </div>

          {children}
        </div>
      </main>
    </div>
  );
}
