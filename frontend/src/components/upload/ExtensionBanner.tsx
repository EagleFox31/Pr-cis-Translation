import { useState } from 'react';
import { Link } from 'react-router-dom';
import { X } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { useAuth } from '../../contexts/AuthContext';
import { useExtensionInstalled } from '../../hooks/useExtensionInstalled';
import { estMobile } from '../../lib/extension';
import '../../extension-page.css';

const CLE = 'precis.extension_banner_dismissed';

function dejaRefuse(): boolean {
  try {
    return localStorage.getItem(CLE) === '1';
  } catch {
    return false;
  }
}

/** Invitation unique et refermable à installer l'extension (ordinateur, connecté, non installée). */
export default function ExtensionBanner() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const { installe } = useExtensionInstalled();
  const [ferme, setFerme] = useState(dejaRefuse);

  if (!user || ferme || installe !== false || estMobile()) return null;

  const fermer = () => {
    setFerme(true);
    try {
      localStorage.setItem(CLE, '1');
    } catch {
      /* stockage interdit : la fermeture ne dure que pour cette visite */
    }
  };

  return (
    <aside className="ext-banner" aria-label={t('extension_page.banner.label')}>
      <span className="ext-banner__text">{t('extension_page.banner.text')}</span>
      <Link to="/extension" className="ext-banner__link">{t('extension_page.banner.link')}</Link>
      <button type="button" className="ext-banner__close" onClick={fermer} aria-label={t('extension_page.banner.close')}>
        <X size={16} aria-hidden="true" />
      </button>
    </aside>
  );
}
