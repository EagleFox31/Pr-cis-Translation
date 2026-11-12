import { useTranslation } from 'react-i18next';
import AppBar from './navbar/AppBar';

// Barre du haut des pages d'intégration (extension, API…) : la barre des pages admin,
// avec une entrée par intégration (docs/etude-navigation-integrations.md).
export default function IntegrationsNav() {
  const { t } = useTranslation();
  return (
    <AppBar
      exit
      linksLabel={t('extension_page.nav_aria')}
      links={[
        { href: '/extension', label: t('extension_page.nav_label') },
        {
          href: '/integrations/api', label: t('extension_page.nav_api'),
          badge: <small className="ext-nav-badge">{t('extension_page.nav_soon')}</small>,
        },
      ]}
    />
  );
}
