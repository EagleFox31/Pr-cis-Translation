/**
 * Haut du panneau de compte : qui je suis, ce qu'il me reste.
 *
 * Deux blocs de la maquette : l'identité (`.p-head`, avec la sortie du panneau)
 * et le solde (`.bal`). Replié : le solde débité en premier (nom, disponible /
 * total, barre, date). Déplié : une ligne par solde (Bêta, forfait, pages
 * achetées), où se choisit celui qui passe en premier.
 * La déconnexion vit en pied de panneau, là où elle ne défile jamais.
 */
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { ChevronDown, X } from 'lucide-react';

import { useAuth, type AuthUser } from '../../contexts/AuthContext';
import api from '../../services/api';
import { percent } from '../../lib/format';
import { useBeta } from '../../hooks/useBeta';
import { useBetaProgram } from '../../hooks/useBetaProgram';
import { useBetaPreference } from '../../hooks/useBetaPreference';
import BetaAllowances from './BetaAllowances';

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
  const credits = usage?.page_credits ?? 0;

  // Bêta d'abord (elle expire avant le forfait), sauf si le client a choisi son
  // forfait : même préférence que la case de la zone de traduction.
  const enrollment = useBeta(refreshKey).data?.enrollment ?? null;
  // Bêta échue (état ou date passée) : retirée de la liste, sans barre.
  const betaExpiree = !!enrollment && (enrollment.state === 'expired'
    || (!!enrollment.expires_at && new Date(enrollment.expires_at).getTime() <= Date.now()));
  const betaActive = enrollment?.state === 'active' && !betaExpiree;
  const [betaFirst, setBetaFirst] = useBetaPreference();
  const surBeta = betaActive && betaFirst;
  const candidatures = useBetaProgram().program?.applications_open === true;

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
  const jour = (iso?: string | null) => {
    const d = iso ? new Date(iso) : null;
    return !d || Number.isNaN(d.getTime()) ? '—'
      : d.toLocaleDateString(i18n.language, { day: 'numeric', month: 'short', year: 'numeric' });
  };

  // Une seule date au replié : renouvellement (gratuit) ou expiration.
  const nomForfait = t(`plans.${user.plan}`, user.plan);
  const expireForfait = user.plan !== 'free' && user.plan_expires_at
    ? t('account.expires_on', { date: jour(user.plan_expires_at) }) : '';
  const dateForfait = expireForfait
    || (usage && !illimite ? t('account.renews_on', { date: jour(usage.resets_at) }) : '');
  const expireBeta = enrollment?.expires_at ? t('account.expires_on', { date: jour(enrollment.expires_at) }) : '';

  // Solde replié : celui qui sera débité en premier pour un document courant.
  // Côté Bêta : le format principal, sinon le premier qui a encore du solde.
  const fmtBeta = enrollment && (enrollment.formats[enrollment.primary_format]?.remaining > 0
    ? enrollment.primary_format
    : (Object.keys(enrollment.formats) as (keyof typeof enrollment.formats)[])
        .find((f) => enrollment.formats[f].remaining > 0) ?? enrollment.primary_format);
  const qBeta = enrollment && fmtBeta ? enrollment.formats[fmtBeta] : null;
  const actif = surBeta && enrollment && qBeta
    ? { nom: `${t('account.beta_name')} · ${t(`beta.formats.${fmtBeta}`)}`,
        dispo: qBeta.remaining, total: qBeta.limit, unite: qBeta.unit, illimite: false, date: expireBeta }
    : { nom: nomForfait, dispo: restantes, total, unite: 'pages', illimite, date: dateForfait };
  const qte = (cle: string, valeur: number) =>
    t(cle, { count: valeur, n: valeur.toLocaleString(i18n.language) });
  const pret = surBeta ? !!qBeta : !!usage;

  const ligneBeta = enrollment && !betaExpiree && (
    <li key="beta" className={betaActive ? undefined : 'off'}>
      <label>
        <input type="radio" name="bal-src" checked={surBeta} disabled={!betaActive}
          onChange={() => setBetaFirst(true)} />
        <b>{t('account.beta_name')}</b>
        <span className="meta">{betaActive ? expireBeta : t(`beta.states.${enrollment.state}`)}</span>
      </label>
      {betaActive && <BetaAllowances enrollment={enrollment} compact />}
    </li>
  );
  const ligneForfait = (
    <li key="plan">
      <label>
        {betaActive && <input type="radio" name="bal-src" checked={!surBeta}
          onChange={() => setBetaFirst(false)} />}
        <b>{nomForfait}</b>
        <span className="meta tab">{illimite ? t('account.unlimited') : usage ? qte('account.qty_pages', restantes) : ''}</span>
      </label>
      {usage && (
        <small>
          {[!illimite && t('account.renews_on', { date: jour(usage.resets_at) }), expireForfait]
            .filter(Boolean).join(' · ')}
        </small>
      )}
    </li>
  );

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
          <span className="plan">{actif.nom}</span>
          {pret && (
            <span className="sum tab">
              {actif.illimite ? t('account.unlimited') : qte(`account.balance_${actif.unite}`, actif.dispo)}
            </span>
          )}
          <ChevronDown className="chev" size={18} strokeWidth={2} aria-hidden="true" />
        </button>
        {pret && (
          <div className="bal-active">
            {!actif.illimite && actif.total > 0 && (
              <div className="bar" role="progressbar" aria-label={actif.nom}
                aria-valuenow={actif.dispo} aria-valuemin={0} aria-valuemax={actif.total}>
                <i className={actif.dispo <= actif.total * 0.1 ? 'low' : undefined}
                  style={{ width: `${percent(actif.dispo, actif.total)}%` }} />
              </div>
            )}
            {actif.date && <small>{actif.date}</small>}
          </div>
        )}

        {ouvert && (
          <div className="bal-detail" id="bal-detail">
            <ul className="bal-lines" aria-label={t('account.use_first')}>
              {surBeta ? [ligneBeta, ligneForfait] : [ligneForfait, ligneBeta]}
              {credits > 0 && (
                <li key="credits">
                  <label><b>{t('account.detail_credits')}</b><span className="meta tab">{credits}</span></label>
                  <small>{t('account.credits_after')}</small>
                </li>
              )}
              {!enrollment && candidatures && (
                <li key="apply"><Link to="/beta" className="bal-apply">{t('account.beta_apply')}</Link></li>
              )}
            </ul>
          </div>
        )}
      </div>
    </>
  );
}
