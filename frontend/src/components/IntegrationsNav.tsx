import { useTranslation } from 'react-i18next';
import AppBar from './navbar/AppBar';

// Barre du haut des pages d'intégration : menu commun + 2ᵉ rangée « Extension et API »
// (docs/etude-navigation-tarifs.md).
export default function IntegrationsNav() {
  const { t } = useTranslation();
  return (
    <AppBar
      sub={{
        label: t('extension_page.nav_aria'),
        links: [
          { href: '/extension', label: t('extension_page.nav_label') },
          {
            href: '/integrations/api', label: t('extension_page.nav_api'),
            badge: <small className="ext-nav-badge">{t('extension_page.nav_soon')}</small>,
          },
        ],
      }}
    />
  );
}
