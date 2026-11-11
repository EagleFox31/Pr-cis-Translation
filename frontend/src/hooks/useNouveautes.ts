import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import api from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { showToast } from '../components/ui/Toast';

export type TypeNouveaute = 'nouveaute' | 'amelioration' | 'correctif';
export type DomaineNouveaute = 'documents' | 'visionneuse' | 'extension' | 'compte';

export interface ElementNouveaute {
  id: string;
  date: string;
  type: TypeNouveaute;
  domaine: DomaineNouveaute;
  titre: string;
  resume: string;
  detail: string;
}

/** Réponse de `GET /api/nouveautes/a-voir`. */
export interface AVoir {
  mode: 'accueil' | 'depuis' | null;
  depuis: string | null;
  elements: ElementNouveaute[];
}

/**
 * Données et actions des fenêtres « Nouveautés » : ce qu'il reste à voir,
 * « vu » et l'abonnement aux e-mails. Chaque appel est sûr à relancer.
 */
export function useNouveautes() {
  const { t, i18n } = useTranslation();
  const { refreshUser } = useAuth();

  /** Éléments à voir ; `null` en cas d'erreur (rien ne doit alors s'ouvrir). */
  const chargerAVoir = useCallback(async (lang: 'fr' | 'en'): Promise<AVoir | null> => {
    try {
      const res = await api.get(`/api/nouveautes/a-voir?lang=${lang}`);
      return res.ok ? (res.data as AVoir) : null;
    } catch {
      return null;
    }
  }, []);

  /** Fermer = avoir vu : date côté serveur, puis profil relu. */
  const marquerVu = useCallback(async (): Promise<boolean> => {
    try {
      const res = await api.post('/api/nouveautes/vues');
      if (!res.ok) return false;
      await refreshUser();
      return true;
    } catch {
      return false;
    }
  }, [refreshUser]);

  /** Renvoie false en cas d'échec : l'appelant revient à l'état précédent. */
  const setAbonnement = useCallback(async (actif: boolean): Promise<boolean> => {
    const lang = i18n.language.startsWith('en') ? 'en' : 'fr';
    try {
      const res = await api.put('/api/nouveautes/abonnement', { actif, langue: lang });
      if (!res.ok) throw new Error(String(res.status));
      await refreshUser();
      return true;
    } catch {
      showToast('error', t('nouveautes.subscribe.error'));
      return false;
    }
  }, [refreshUser, t, i18n.language]);

  return { chargerAVoir, marquerVu, setAbonnement };
}
