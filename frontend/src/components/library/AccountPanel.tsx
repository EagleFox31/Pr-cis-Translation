/**
 * En-tête de compte de la barre latérale : qui je suis, ce qu'il me reste,
 * comment je sors.
 *
 * Tout y était écrit en français EN DUR — « Déconnexion », « Illimité »,
 * « Utilisateur », « Traduction seule — sans stockage ». L'interface anglaise
 * affichait donc du français à cet endroit précis, et seulement là.
 *
 * LA DÉCONNEXION N'EST PLUS ICI
 * -----------------------------
 * Elle vivait au bas de ce bloc, en gris clair sur blanc, et se perdait : on
 * ne savait pas qu'elle existait. Elle est descendue en PIED DE PANNEAU, où
 * elle reste visible quelle que soit la position de la liste — le seul endroit
 * qui ne défile jamais. Voir `DocumentLibrary`.
 */
import { useTranslation } from 'react-i18next';
import { Crown, HardDrive } from 'lucide-react';

import type { AuthUser } from '../../contexts/AuthContext';
import { formatSize, percent } from '../../lib/format';
import Avatar from '../ui/Avatar';
import ProgressBar from '../ui/ProgressBar';

interface AccountPanelProps {
  user: AuthUser;
}

export default function AccountPanel({ user }: AccountPanelProps) {
  const { t } = useTranslation();

  const illimite = user.storage_limit <= 0 && user.plan === 'admin';
  const sansStockage = user.storage_limit <= 0 && user.plan !== 'admin';
  const occupation = percent(user.storage_used, user.storage_limit);
  // Au-delà de 90 %, la barre passe au rouge : l'information utile n'est pas
  // « voici votre quota », c'est « vous allez le heurter ».
  const ton = occupation >= 90 ? 'danger' : occupation >= 70 ? 'gold' : 'blue';

  return (
    <section className="compte">
      <div className="compte__identite">
        <Avatar name={user.name} email={user.email} size={46} />
        <div className="compte__noms">
          <p className="compte__nom">{user.name || t('account.default_name')}</p>
          <p className="compte__email" title={user.email}>{user.email}</p>
        </div>
        <span className={`compte__forfait compte__forfait--${user.plan === 'free' ? 'base' : 'paye'}`}>
          {t(`plans.${user.plan}`, user.plan)}
        </span>
      </div>

      <div className="compte__stockage">
        {illimite ? (
          <p className="compte__ligne">
            <Crown size={13} className="compte__couronne" aria-hidden />
            {formatSize(user.storage_used, t)} · {t('account.unlimited')}
          </p>
        ) : sansStockage ? (
          <p className="compte__ligne compte__ligne--discrete">
            <HardDrive size={13} aria-hidden />
            {t('account.no_storage')}
          </p>
        ) : (
          <>
            <div className="compte__quota">
              <span className="compte__ligne">
                <HardDrive size={13} aria-hidden />
                {t('account.storage')}
              </span>
              <span className="compte__chiffres">
                {formatSize(user.storage_used, t)} / {formatSize(user.storage_limit, t)}
              </span>
            </div>
            <ProgressBar value={occupation} tone={ton} height={5}
              label={t('account.storage')} />
          </>
        )}
      </div>
    </section>
  );
}
