/**
 * Message affiché après un changement de plan, commun à la page Comptes et à la
 * fiche utilisateur : même issue, mêmes toasts, quel que soit l'endroit du geste.
 */
import type { TFunction } from 'i18next';
import { showToast } from '../ui/Toast';

/** Événement émis par la fiche pour que la liste Comptes se rafraîchisse. */
export const USERS_CHANGED_EVENT = 'admin-users-changed';

export function toastPlanResult(t: TFunction, email: string, res: { ok: boolean; status: number }) {
  if (res.ok) {
    showToast('success', t('admin_users.changed', 'Plan modifié'), email);
  } else if (res.status === 400) {
    showToast('error', t('admin_users.change_refused_title', 'Changement refusé'),
      t('admin_users.change_refused', 'Un admin ne peut pas changer son propre plan.'));
  } else {
    showToast('error', t('admin_users.change_error', 'Échec'), String(res.status));
  }
}
