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
 * L'en-tête est `AppBar`, partagée avec les pages d'intégration
 * (docs/etude-navigation-integrations.md) — la même barre, pas une imitation qui dériverait.
 */
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

import { useAuth } from '../../contexts/AuthContext';
import AppBar from '../navbar/AppBar';
import { AdminStats, type AdminStat } from './AdminParts';
import './admin.css';

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
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user } = useAuth();
  // Jamais montré à un non-admin : il trahirait les pages internes.
  const showTabs = tabs && user?.plan === 'admin';
  const tabLinks = TABS.map((tab) => ({ href: tab.to, label: t(`admin.tabs.${tab.key}`, tab.label) }));

  return (
    <div className="admin-page">
      <AppBar sub={showTabs ? { label: t('admin.menu', 'Administration'), links: tabLinks } : undefined} />

      {/* Contenu : décalé sous la barre fixe, cadré comme le reste du site */}
      <main className="admin-main">
        <div className="admin-frame">
          {/* Page publique : Retour et titre restent visibles au défilement. */}
          <div className={'admin-head' + (tabs ? '' : ' admin-head--sticky')}>
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
