/**
 * Fiche utilisateur, affichée à droite de la liste des comptes
 * (docs/etude-fiche-utilisateur-integree.md).
 *
 * Son adresse est `/admin/users?user=<e-mail>` : un clic sur un e-mail
 * (`UserLink`) y mène depuis n'importe quelle page admin, le bouton Retour du
 * navigateur ramène à la vue précédente, un lien copié rouvre la même fiche.
 *
 * La fiche recoupe les listes admin existantes sur l'e-mail exact (comptes,
 * documents, assistance) et le journal ; seul l'historique des forfaits a sa
 * route (docs/etude-historique-forfaits.md). Documents, assistance et erreurs
 * n'y sont que comptés : la tuile mène à la page dédiée, filtrée sur le compte.
 */
import { useEffect, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowRight, X } from 'lucide-react';

import api from '../../services/api';
import { useAuth } from '../../contexts/AuthContext';
import { postUserPlan, type AdminUser } from '../../hooks/useAdminUsers';
import type { AdminDocument } from '../../hooks/useAdminDocuments';
import type { Ticket } from '../../hooks/useAdminSupport';
import { toastPlanResult, USERS_CHANGED_EVENT } from './planChange';

export const USER_PARAM = 'user';
const USERS_PATH = '/admin/users';
const PLAN_COLOR: Record<string, string> = {
  free: '#6b7280', starter: '#2563eb', pro: '#7c3aed',
  enterprise: '#0d9488', admin: '#b91c1c',
};

function fmt(iso: string | null): string {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleDateString(); } catch { return iso; }
}

const same = (a: string | null | undefined, b: string) => (a || '').toLowerCase() === b.toLowerCase();

/** E-mail cliquable : ouvre la fiche sur la page Comptes. Déjà sur cette page,
 *  la recherche en cours est gardée. */
export function UserLink({ email, className, children }: { email: string; className?: string; children?: ReactNode }) {
  const [, setParams] = useSearchParams();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  return (
    <button
      type="button"
      className={className ?? 'admin-userlink'}
      title={email}
      onClick={(e) => {
        e.stopPropagation();
        if (pathname !== USERS_PATH) {
          navigate(`${USERS_PATH}?${USER_PARAM}=${encodeURIComponent(email)}`);
          return;
        }
        setParams((prev) => {
          const next = new URLSearchParams(prev);
          next.set(USER_PARAM, email);
          return next;
        });
      }}
    >
      {children ?? email}
    </button>
  );
}

type Status = 'loading' | 'ready' | 'error';
interface Block<T> { status: Status; data: T | null }

/** Charge un bloc de la fiche ; `null` ou une exception donnent l'état « erreur ».
 *  Sans clé, le bloc reste en chargement. */
function useBlock<T>(load: (key: string) => Promise<T | null>, key: string | null, reload = 0): Block<T> {
  const [block, setBlock] = useState<Block<T>>({ status: 'loading', data: null });
  useEffect(() => {
    if (!key) return;
    let off = false;
    setBlock({ status: 'loading', data: null });
    load(key)
      .then((r) => { if (!off) setBlock(r === null ? { status: 'error', data: null } : { status: 'ready', data: r }); })
      .catch(() => { if (!off) setBlock({ status: 'error', data: null }); });
    return () => { off = true; };
  }, [load, key, reload]);
  return block;
}

const q = (email: string) => `?q=${encodeURIComponent(email)}&limit=200`;

async function countDocuments(email: string): Promise<number | null> {
  const res = await api.get(`/api/admin/documents${q(email)}`);
  if (!res.ok || !res.data) return null;
  return ((res.data as { items: AdminDocument[] }).items || []).filter((d) => same(d.user_email, email)).length;
}

async function countTickets(email: string): Promise<number | null> {
  const res = await api.get(`/api/support${q(email)}`);
  if (!res.ok || !res.data) return null;
  return ((res.data as { tickets: Ticket[] }).tickets || []).filter((tk) => same(tk.user_email, email)).length;
}

/** Le journal est regroupé par empreinte et ne porte pas l'e-mail par ligne :
 *  le filtre exact `user_email` ne compte que les erreurs de ce compte. */
async function countErrors(email: string): Promise<number | null> {
  const res = await api.get(`/api/logs?user_email=${encodeURIComponent(email)}&limit=1`);
  if (!res.ok || !res.data) return null;
  return (res.data as { total_groups: number }).total_groups || 0;
}

interface Identity { user: AdminUser | null; plans: string[] }

async function loadIdentity(email: string): Promise<Identity | null> {
  const res = await api.get(`/api/admin/users${q(email)}`);
  if (!res.ok || !res.data) return null;
  const d = res.data as { users: AdminUser[]; assignable_plans: string[] };
  return { user: (d.users || []).find((u) => same(u.email, email)) || null, plans: d.assignable_plans || [] };
}

type PlanEventKind = 'signup' | 'subscription' | 'renewal' | 'admin' | 'expiry';
interface PlanEvent { kind: PlanEventKind; plan: string; months: number | null; at: string | null; expires_at: string | null }
interface PlanHistory { subscriptions: number; renewals: number; expiries: number; items: PlanEvent[] }

async function loadHistory(userId: string): Promise<PlanHistory | null> {
  const res = await api.get(`/api/admin/users/${encodeURIComponent(userId)}/plan-history`);
  return res.ok && res.data ? res.data as PlanHistory : null;
}

/** Tuile entière cliquable : le nombre, puis la page dédiée filtrée sur le compte. */
function CountTile({ title, count, to, cta }: { title: string; count: Block<number>; to: string; cta: string }) {
  const { t } = useTranslation();
  return (
    <Link to={to} className="admin-panel__tile">
      <span className="admin-panel__tile-title">{title}</span>
      <span className="admin-panel__tile-count">
        {count.status === 'ready' ? count.data : count.status === 'error' ? '—' : '…'}
      </span>
      {count.status === 'error' && <span className="admin-panel__muted">{t('admin_panel.load_error', 'Impossible de charger ce bloc.')}</span>}
      <span className="admin-panel__tile-cta">{cta} <ArrowRight size={13} strokeWidth={2.2} aria-hidden="true" /></span>
    </Link>
  );
}

/** Fiche d'un compte, dans la colonne de droite de la page Comptes. */
export function UserCard({ email, onClose }: { email: string; onClose: () => void }) {
  const { t } = useTranslation();
  const { user: me } = useAuth();

  const identity = useBlock<Identity>(loadIdentity, email);
  const docs = useBlock<number>(countDocuments, email);
  const tickets = useBlock<number>(countTickets, email);
  const errors = useBlock<number>(countErrors, email);

  const [plan, setPlan] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [historyRev, setHistoryRev] = useState(0);

  const found = identity.data?.user ?? null;
  const plans = identity.data?.plans ?? [];
  const currentPlan = plan ?? found?.plan ?? '';
  const isSelf = !!found && me?.id === found.id;
  const history = useBlock<PlanHistory>(loadHistory, found?.id ?? null, historyRev);

  const onPlan = async (next: string) => {
    if (!found || next === currentPlan) return;
    setBusy(true);
    let res = { ok: false, status: 0 };
    try {
      const r = await postUserPlan(found.id, next);
      res = { ok: r.ok, status: r.status };
    } catch { /* l'échec réseau est signalé par le toast ci-dessous */ }
    setBusy(false);
    toastPlanResult(t, found.email, res);
    if (res.ok) {
      setPlan(next);
      setHistoryRev((n) => n + 1);
      window.dispatchEvent(new Event(USERS_CHANGED_EVENT));
    }
  };

  const enc = encodeURIComponent(email);
  const color = PLAN_COLOR[currentPlan] || '#6b7280';
  const kindLabel: Record<PlanEventKind, string> = {
    signup: t('admin_panel.ev_signup', 'Inscription'),
    subscription: t('admin_panel.ev_subscription', 'Abonnement'),
    renewal: t('admin_panel.ev_renewal', 'Renouvellement'),
    admin: t('admin_panel.ev_admin', 'Attribué par l’administration'),
    expiry: t('admin_panel.ev_expiry', 'Échéance, retour au Gratuit'),
  };

  return (
    <section className="admin-panel" aria-labelledby="admin-panel-title">
      <header className="admin-panel__head">
        <div>
          <span className="admin-panel__eyebrow">{t('admin_panel.title', 'Fiche utilisateur')}</span>
          <h2 id="admin-panel-title">{email}</h2>
        </div>
        <button type="button" className="tb-btn ghost admin-icon-btn"
          onClick={onClose} aria-label={t('admin_panel.close', 'Fermer la fiche')} title={t('admin_panel.close', 'Fermer la fiche')}>
          <X size={16} strokeWidth={2.2} />
        </button>
      </header>

      <div className="admin-panel__body">
        <section className="admin-panel__block" aria-label={t('admin_panel.identity', 'Identité')}>
          {identity.status === 'loading' && <p className="admin-panel__muted" role="status">{t('admin.loading', 'Chargement…')}</p>}
          {identity.status === 'error' && <p className="admin-panel__muted">{t('admin_panel.load_error', 'Impossible de charger ce bloc.')}</p>}
          {identity.status === 'ready' && !found && (
            <p className="admin-panel__muted">{t('admin_panel.not_found', 'Aucun compte ne correspond à cet e-mail.')}</p>
          )}
          {found && (
            <dl className="admin-panel__facts">
              <div><dt>{t('admin_panel.name', 'Nom')}</dt><dd>{found.name || '—'}</dd></div>
              <div><dt>{t('admin_panel.since', 'Inscrit le')}</dt><dd>{fmt(found.created_at)}</dd></div>
              <div>
                <dt>{t('admin_panel.email', 'E-mail')}</dt>
                <dd className={found.email_verified ? undefined : 'admin-panel__warn'}>
                  {found.email_verified ? t('admin_panel.verified', 'vérifié') : t('admin_users.unverified', 'non vérifié')}
                </dd>
              </div>
              <div>
                <dt><label htmlFor="admin-panel-plan">{t('admin_panel.plan', 'Plan')}</label></dt>
                <dd><select
                  id="admin-panel-plan"
                  className="admin-select"
                  value={currentPlan}
                  disabled={isSelf || busy}
                  onChange={(e) => void onPlan(e.target.value)}
                  title={isSelf ? t('admin_users.cant_self', 'Vous ne pouvez pas changer votre propre plan') : ''}
                  style={{ color, borderColor: color }}
                >
                  {(plans.includes(currentPlan) ? plans : [currentPlan, ...plans]).map((p) => <option key={p} value={p}>{p}</option>)}
                </select></dd>
              </div>
            </dl>
          )}
        </section>

        {!(identity.status === 'ready' && !found) && (
          <div className="admin-panel__grid">
            <CountTile title={t('admin_panel.documents', 'Documents')} count={docs}
              to={`/admin/documents?q=${enc}`} cta={t('admin_panel.see_documents', 'Voir les documents')} />
            <CountTile title={t('admin_panel.support', 'Assistance')} count={tickets}
              to={`/admin/support?q=${enc}`} cta={t('admin_panel.see_tickets', 'Voir les demandes')} />
            <CountTile title={t('admin_panel.errors', 'Erreurs')} count={errors}
              to={`/admin/logs?q=${enc}`} cta={t('admin_panel.see_errors', 'Voir les erreurs')} />
          </div>
        )}

        {found && (
          <section className="admin-panel__block admin-panel__history" aria-labelledby="admin-panel-history">
            <div className="admin-panel__block-head">
              <h3 id="admin-panel-history">{t('admin_panel.history', 'Historique des forfaits')}</h3>
              {history.data && (
                <span className="admin-panel__muted">
                  {t('admin_panel.history_counts', '{{s}} abonnement(s) · {{r}} renouvellement(s) · {{e}} échéance(s)',
                    { s: history.data.subscriptions, r: history.data.renewals, e: history.data.expiries })}
                </span>
              )}
            </div>
            {history.status === 'loading' && <p className="admin-panel__muted" role="status">{t('admin.loading', 'Chargement…')}</p>}
            {history.status === 'error' && <p className="admin-panel__muted">{t('admin_panel.load_error', 'Impossible de charger ce bloc.')}</p>}
            {history.data && (
              <ol className="admin-panel__timeline">
                {history.data.items.map((ev, i) => {
                  const c = PLAN_COLOR[ev.plan] || '#6b7280';
                  const detail = [
                    ev.months ? t('admin_panel.ev_months', '{{n}} mois', { n: ev.months }) : '',
                    ev.expires_at ? t('admin_panel.ev_until', 'jusqu’au {{d}}', { d: fmt(ev.expires_at) }) : '',
                  ].filter(Boolean).join(' · ');
                  return (
                    <li key={`${ev.kind}-${ev.at}-${i}`}>
                      <time dateTime={ev.at ?? undefined}>{fmt(ev.at)}</time>
                      <span className="admin-panel__ev">{kindLabel[ev.kind] ?? ev.kind}</span>
                      <span className="admin-tag" style={{ color: c, background: `${c}14`, border: `1px solid ${c}55` }}>{ev.plan}</span>
                      {detail && <span className="admin-panel__muted">{detail}</span>}
                    </li>
                  );
                })}
              </ol>
            )}
          </section>
        )}
      </div>
    </section>
  );
}
