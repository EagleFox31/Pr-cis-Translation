/**
 * Haut du panneau de compte : qui je suis, ce qu'il me reste.
 *
 * Deux blocs de la maquette : l'identité (`.p-head`, avec la sortie du panneau)
 * et le solde (`.bal`) : une ligne repliée (forfait + pages disponibles) qui
 * se déplie sur la barre, le détail des pages et les dates.
 * La déconnexion vit en pied de panneau, là où elle ne défile jamais ; le
 * stockage et le renouvellement ne sont plus affichés ici.
 */
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronDown, X } from 'lucide-react';

import { useAuth, type AuthUser } from '../../contexts/AuthContext';
import api from '../../services/api';
import { percent } from '../../lib/format';

interface AccountPanelProps {
  user: AuthUser;
  /** Change quand la liste des documents change : la consommation est relue. */
  refreshKey?: string;
  /** Ferme le panneau. */
  onClose: () => void;
}

/** Réponse de `/api/auth/me/usage` — calculée par le module qui FAIT
 *  respecter les quotas : ce qui est affiché est ce que la route acceptera. */
interface Usage {
  kind: 'free' | 'plan';
  free_translations_remaining?: number;
  monthly_pages?: number | null;
  pages_used?: number;
  pages_remaining?: number | null;
  page_credits: number;
  resets_at: string;
}

export default function AccountPanel({ user, refreshKey, onClose }: AccountPanelProps) {
  const { t, i18n } = useTranslation();
  const { refreshUser } = useAuth();
  const [usage, setUsage] = useState<Usage | null>(null);

  // Relu à chaque changement de la liste : une traduction consomme des pages —
  // le profil chargé à la connexion serait périmé.
  useEffect(() => {
    let vivant = true;
    refreshUser().catch(() => { /* l'affichage précédent reste valable */ });
    api.get('/api/auth/me/usage').then(res => {
      if (vivant && res.ok) setUsage(res.data as Usage);
    });
    return () => { vivant = false; };
  }, [refreshKey, user.plan, refreshUser]);

  const nom = user.name || t('account.default_name');
  const initiale = (user.name || user.email || '?').trim()[0]?.toUpperCase() ?? '?';

  const illimite = !!usage && usage.kind === 'plan' && usage.monthly_pages == null;
  const restantes = usage?.pages_remaining ?? 0;
  const total = usage?.monthly_pages ?? 0;
  // La barre montre ce qui RESTE : elle se vide à mesure qu'on traduit.
  const reste = percent(restantes, total);
  const libelleBarre = usage?.kind === 'free' ? t('account.pages_free_left', { count: restantes })
    : t('account.pages_left');
  // Ce qu'on peut encore traduire : quota du mois + pages achetées.
  const disponibles = restantes + (usage?.page_credits ?? 0);
  const [ouvert, setOuvert] = useState(false);
  const balRef = useRef<HTMLDivElement>(null);
  // Se replie dès qu'on quitte le bloc : focus parti (onBlur) ou clic ailleurs —
  // Safari ne donne pas le focus aux boutons cliqués, d'où le pointerdown.
  useEffect(() => {
    if (!ouvert) return;
    const ailleurs = (e: PointerEvent) => {
      if (!balRef.current?.contains(e.target as Node)) setOuvert(false);
    };
    document.addEventListener('pointerdown', ailleurs);
    return () => document.removeEventListener('pointerdown', ailleurs);
  }, [ouvert]);
  const jour = (iso: string) => {
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? '—'
      : d.toLocaleDateString(i18n.language, { day: 'numeric', month: 'long', year: 'numeric' });
  };

  return (
    <>
      <header className="p-head">
        <span className="av" aria-hidden="true">{initiale}</span>
        <div className="who">
          <b>{nom}</b>
          <span title={user.email}>{user.email}</span>
        </div>
        <button type="button" className="iconbtn" aria-label={t('library.close')} onClick={onClose}>
          <X size={20} strokeWidth={2} aria-hidden="true" />
        </button>
      </header>

      <div className="bal" ref={balRef}
        // relatedTarget nul = clic sur du texte du bloc (ou hors page) : le
        // pointerdown extérieur gère déjà la souris, on ne replie que sur Tab sortant.
        onBlur={e => {
          const vers = e.relatedTarget as Node | null;
          if (vers && !e.currentTarget.contains(vers)) setOuvert(false);
        }}>
        <button type="button" className="bal-row" aria-expanded={ouvert}
          aria-controls={ouvert ? 'bal-detail' : undefined}
          onClick={() => setOuvert(o => !o)}>
          <span className="plan">{t(`plans.${user.plan}`, user.plan)}</span>
          {usage && (
            <span className="sum">
              {illimite ? t('account.unlimited')
                : <><b className="tab">{disponibles}</b> {t('account.pages_available', { count: disponibles })}</>}
            </span>
          )}
          <ChevronDown className="chev" size={18} strokeWidth={2} aria-hidden="true" />
        </button>

        {ouvert && (
          <div className="bal-detail" id="bal-detail">
            {usage && !illimite && total > 0 && (
              <div className="bar" role="progressbar" aria-label={libelleBarre}
                aria-valuenow={restantes} aria-valuemin={0} aria-valuemax={total}>
                <i className={restantes <= total * 0.1 ? 'low' : undefined} style={{ width: `${reste}%` }} />
              </div>
            )}
            {usage && (
              <dl>
                {!illimite && (
                  <div>
                    <dt>{usage.kind === 'free' ? t('account.detail_free') : t('account.detail_plan')}</dt>
                    <dd className="tab">{restantes} / {total}</dd>
                  </div>
                )}
                {usage.page_credits > 0 && (
                  <div>
                    <dt>{t('account.detail_credits')}</dt>
                    <dd className="tab">{usage.page_credits}</dd>
                  </div>
                )}
                {!illimite && (
                  <div>
                    <dt>{usage.kind === 'free' ? t('account.detail_free_resets') : t('account.detail_plan_resets')}</dt>
                    <dd>{jour(usage.resets_at)}</dd>
                  </div>
                )}
                {user.plan !== 'free' && user.plan_expires_at && (
                  <div>
                    <dt>{t('account.detail_expires')}</dt>
                    <dd>{jour(user.plan_expires_at)}</dd>
                  </div>
                )}
              </dl>
            )}
          </div>
        )}
      </div>
    </>
  );
}
