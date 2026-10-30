/**
 * Programmes Bêta — vue d'administration (`/admin/beta`).
 *
 * Liste des programmes à gauche, fiche du programme choisi à droite
 * (docs/etude-programmes-beta.md). Un seul programme est ouvert à la fois ;
 * les précédents restent consultables avec leurs candidatures et participants.
 * Le programme choisi est gardé dans l'URL (`?c=<id>`, `?c=new` pour en créer un).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router-dom';
import { Check, Link2, Pencil, Plus, RotateCcw, SlidersHorizontal, UserPlus, UserX, X } from 'lucide-react';
import AdminShell from '../components/admin/AdminShell';
import { UserLink } from '../components/admin/UserPanel';
import { AdminList, AdminStats, AdminToolbar, FileTypeIcon, RefreshButton } from '../components/admin/AdminParts';
import BetaAllowances, { BETA_FORMATS } from '../components/library/BetaAllowances';
import type { BetaApplication, BetaEnrollment, BetaFormat, BetaLimits } from '../hooks/useBeta';
import api from '../services/api';
import { betaError } from '../lib/betaError';
import { showToast } from '../components/ui/Toast';

const CAMPAIGN_PARAM = 'c';
const NEW = 'new';

interface Settings {
  name: string; capacity: number; first_wave_capacity: number; access_days: number; limits: BetaLimits;
}
interface Campaign extends Settings {
  id: string; state: 'draft' | 'open' | 'closed'; seats_used: number; current_capacity: number;
  starts_at: string | null; recruitment_ends_at: string | null; second_wave_at: string | null;
  recruitment_open: boolean; created_at: string | null;
}
interface BetaRisk {
  flags: { kind: 'same_mailbox' | 'same_ip' | 'same_browser' | 'rapid_sequence'; count: number }[];
  related_count: number; related: { email: string }[];
}
type ReviewedApplication = BetaApplication & { risk?: BetaRisk };
type ReviewedEnrollment = BetaEnrollment & { risk?: BetaRisk };
interface Dashboard {
  campaign: Campaign | null; campaigns: Campaign[]; enrollments: ReviewedEnrollment[];
  defaults: Settings; applications: ReviewedApplication[];
}
/** Une ligne de la liste unique de la fiche : candidature ou inscription. */
type Person = { kind: 'application'; row: ReviewedApplication } | { kind: 'enrollment'; row: ReviewedEnrollment };
const isPending = (person: Person) => person.kind === 'application' && person.row.state === 'pending';

const pickSettings = (from: Settings): Settings => ({
  name: from.name, capacity: from.capacity, first_wave_capacity: from.first_wave_capacity,
  access_days: from.access_days, limits: from.limits,
});
/** « Recrutement terminé » quand le programme est ouvert mais que ses deux mois sont passés. */
const stateKey = (campaign: Campaign) =>
  campaign.state === 'open' && !campaign.recruitment_open ? 'ended' : campaign.state;

function RiskNotice({ risk }: { risk?: BetaRisk }) {
  const { t } = useTranslation();
  if (!risk?.flags.length) return null;
  return <details className="beta-review-alert">
    <summary>{t('beta.safety.review')}</summary>
    <p className="beta-note">{t('beta.safety.hint')}</p>
    <ul>{risk.flags.map(flag => <li key={flag.kind}>
      {t(`beta.safety.${flag.kind}`, { count: flag.count })}
    </li>)}</ul>
    {risk.related.length > 0 && <>
      <strong>{t('beta.safety.related')}</strong>
      <ul>{risk.related.map(person => <li key={person.email}><UserLink email={person.email} /></li>)}</ul>
    </>}
  </details>;
}
/** Un champ par plafond, sur une ligne : icône du format et unité au-dessus du chiffre. */
const LIMIT_FIELDS: { key: keyof BetaLimits; format: BetaFormat; unit: string; max: number }[] = [
  { key: 'pdf', format: 'pdf', unit: 'pages', max: 100000 },
  { key: 'pptx', format: 'pptx', unit: 'slides', max: 100000 },
  { key: 'docx', format: 'docx', unit: 'words', max: 1000000 },
  { key: 'xlsx', format: 'xlsx', unit: 'sheets', max: 10000 },
  { key: 'xlsx_words', format: 'xlsx', unit: 'words', max: 1000000 },
];

/** Un bloc par format : Excel regroupe ses deux plafonds (feuilles et mots) sous un seul titre. */
function LimitsEditor({ value, onChange }: { value: BetaLimits; onChange: (v: BetaLimits) => void }) {
  const { t } = useTranslation();
  return <div className="beta-quota-grid">
    {BETA_FORMATS.map(format => {
      const fields = LIMIT_FIELDS.filter(field => field.format === format);
      return <div className={'beta-quota' + (fields.length > 1 ? ' beta-quota--double' : '')} key={format}>
        <span className="beta-quota__head" aria-hidden>
          <FileTypeIcon name={format} size={15} />{t(`beta.formats.${format}`)}
        </span>
        <div className="beta-quota__inputs">
          {fields.map(field => <label key={field.key}>
            <span className="beta-quota__unit" aria-hidden>{t(`beta.units.${field.unit}`)}</span>
            <input className="admin-input" type="number" min={0} max={field.max} required
              aria-label={t(`beta.limit_labels.${field.key}`)}
              value={value[field.key]} onChange={event => onChange({ ...value, [field.key]: Number(event.target.value) })} />
          </label>)}
        </div>
      </div>;
    })}
  </div>;
}

type Confirmation = { message: string; label: string; onConfirm: () => void };

/** Confirmation dans la page (remplace `window.confirm`). */
function ConfirmDialog({ ask, onClose }: { ask: Confirmation; onClose: () => void }) {
  const { t } = useTranslation();
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { if (ref.current && !ref.current.open) ref.current.showModal(); }, []);
  return <dialog ref={ref} className="beta-card beta-dialog beta-dialog--confirm" aria-labelledby="beta-confirm-text"
    onCancel={event => { event.preventDefault(); onClose(); }}>
    <p id="beta-confirm-text">{ask.message}</p>
    <div className="admin-form-footer">
      <span />
      <div className="admin-form-actions">
        <button className="tb-btn ghost" type="button" autoFocus onClick={onClose}>{t('beta.cancel')}</button>
        <button className="tb-btn admin-btn--danger" type="button" onClick={() => { onClose(); ask.onConfirm(); }}>{ask.label}</button>
      </div>
    </div>
  </dialog>;
}

/** Réglages d'un programme : création (`?c=new`) ou modification. */
function SettingsForm({ value, onChange, busy, submitLabel, onSubmit, onCancel, start, extra }: {
  value: Settings; onChange: (v: Settings) => void; busy: boolean;
  submitLabel: string; onSubmit: () => void; onCancel: () => void;
  /** Action à gauche du pied (ouvrir / fermer les inscriptions). */
  start?: React.ReactNode;
  /** Contenu au-dessus du pied (case « Fermer les programmes ouverts »). */
  extra?: React.ReactNode;
}) {
  const { t } = useTranslation();
  return <form onSubmit={event => { event.preventDefault(); onSubmit(); }}>
    <fieldset disabled={busy} className="beta-fieldset admin-form">
      <label className="admin-field--full">{t('beta.name')}<input className="admin-input" required maxLength={120} value={value.name}
        onChange={event => onChange({ ...value, name: event.target.value })} /></label>
      <div className="admin-form__group">
        {(['capacity', 'first_wave_capacity', 'access_days'] as const).map(key => (
          <label key={key}>{t(`beta.${key}`)}
            <input className="admin-input" required type="number" min={1} max={key === 'access_days' ? 90 : 1000}
              value={value[key]} onChange={event => onChange({ ...value, [key]: Number(event.target.value) })} />
          </label>
        ))}
      </div>
      <h3>{t('beta.default_limits')}</h3>
      <LimitsEditor value={value.limits} onChange={limits => onChange({ ...value, limits })} />
      <p className="admin-form-note">{t('beta.defaults_hint')}</p>
      {extra}
      <div className="admin-form-footer">
        {start || <span />}
        <div className="admin-form-actions">
          <button className="tb-btn ghost" type="button" onClick={onCancel}>{t('beta.cancel')}</button>
          <button className="beta-primary" type="submit">{submitLabel}</button>
        </div>
      </div>
    </fieldset>
  </form>;
}

export default function AdminBetaPage() {
  const { t, i18n } = useTranslation();
  const [params, setParams] = useSearchParams();
  const selected = params.get(CAMPAIGN_PARAM);
  const [data, setData] = useState<Dashboard | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [editingSettings, setEditingSettings] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const [email, setEmail] = useState('');
  const [format, setFormat] = useState<BetaFormat>('pdf');
  const [inviting, setInviting] = useState(false);
  const [editing, setEditing] = useState<BetaEnrollment | null>(null);
  const [editLimits, setEditLimits] = useState<BetaLimits | null>(null);
  const [ask, setAsk] = useState<Confirmation | null>(null);
  const [closeOthers, setCloseOthers] = useState(true);
  const dialog = useRef<HTMLDialogElement>(null);
  const inviteDialog = useRef<HTMLDialogElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), 2000);
    return () => window.clearTimeout(timer);
  }, [copied]);
  useEffect(() => {
    if (editing && dialog.current && !dialog.current.open) dialog.current.showModal();
  }, [editing]);
  useEffect(() => {
    if (inviting && inviteDialog.current && !inviteDialog.current.open) inviteDialog.current.showModal();
  }, [inviting]);

  const select = useCallback((id: string | null) => {
    setError('');
    setParams(prev => {
      const next = new URLSearchParams(prev);
      if (id) next.set(CAMPAIGN_PARAM, id); else next.delete(CAMPAIGN_PARAM);
      return next;
    }, { replace: !id });
  }, [setParams]);

  // Sans `?c`, la fiche montre le programme en cours (l'ouvert, sinon le dernier créé).
  // Seule la dernière requête écrit : un changement rapide de programme n'affiche pas l'ancien.
  const request = useRef(0);
  const shown = useRef(selected);
  shown.current = selected;
  const load = useCallback(async () => {
    const selected = shown.current;
    const query = selected && selected !== NEW ? '?campaign_id=' + encodeURIComponent(selected) : '';
    const ticket = ++request.current;
    const result = await api.get('/api/admin/beta' + query);
    if (ticket !== request.current) return;
    if (!result.ok) {
      const code = (result.data as { detail?: { code?: unknown } } | null)?.detail?.code;
      if (code === 'campaign_not_found') select(null);
      throw new Error(betaError(t, result.data));
    }
    setData(result.data as Dashboard);
  }, [select, t]);
  useEffect(() => {
    setEditingSettings(false); setSettings(null); setInviting(false);
    load().catch((failure: Error) => setError(failure.message || t('beta.error')));
  }, [selected, load, t]);

  // Une colonne (mobile) : la fiche passe au-dessus de la liste, on la montre.
  useEffect(() => {
    if (selected && window.matchMedia('(max-width: 899px)').matches) {
      cardRef.current?.scrollIntoView({ block: 'start' });
    }
  }, [selected]);

  const mutate = async (path: string, body: unknown, method: 'post' | 'patch' = 'post') => {
    setBusy(true); setError('');
    try {
      const result = await api[method](path, body);
      if (!result.ok) {
        throw new Error(betaError(t, result.data));
      }
      await load();
      showToast('success', t('beta.saved'));
      return result.data;
    } catch (failure) {
      setError((failure as Error).message || t('beta.error'));
      return null;
    } finally { setBusy(false); }
  };
  const date = (value: string | null) => value ? new Date(value).toLocaleDateString(i18n.language) : '—';
  const copyLink = async () => {
    try { await navigator.clipboard.writeText(window.location.origin + '/beta'); setCopied(true); }
    catch { setError(t('beta.copy_error')); }
  };
  const created = (row: Campaign | null) => { if (row) { setSettings(null); select(row.id); } };
  // Nouveau programme : fermer d'abord les programmes ouverts (sur confirmation), créer, puis ouvrir.
  const createCampaign = (values: Settings) => {
    const open = (data?.campaigns || []).filter(row => row.state === 'open');
    if (!closeOthers || !open.length) {
      void mutate('/api/admin/beta/campaigns', values).then(row => created(row as Campaign | null));
      return;
    }
    setAsk({
      label: t('beta.campaigns.close_others_ok'),
      message: t('beta.campaigns.close_others_confirm', { names: open.map(row => row.name).join(', '), name: values.name }),
      onConfirm: () => void (async () => {
        for (const row of open) {
          if (!await mutate('/api/admin/beta/campaigns/' + row.id, { state: 'closed' }, 'patch')) return;
        }
        const row = await mutate('/api/admin/beta/campaigns', values) as Campaign | null;
        if (row) await mutate('/api/admin/beta/campaigns/' + row.id, { state: 'open' }, 'patch');
        created(row);
      })(),
    });
  };

  const creating = selected === NEW;
  const campaign = creating ? null : data?.campaign || null;
  const campaigns = data?.campaigns || [];
  const otherOpen = campaigns.find(row => row.state === 'open' && row.id !== campaign?.id
    && !(row.recruitment_ends_at && new Date(row.recruitment_ends_at) <= new Date()));
  const applications = data?.applications || [];
  // Une seule liste : une candidature validée est déjà une inscription, on ne la montre qu'une fois.
  // Les candidatures en attente passent en tête.
  const people: Person[] = [
    ...applications.filter(row => row.state !== 'approved').map(row => ({ kind: 'application' as const, row })),
    ...(data?.enrollments || []).map(row => ({ kind: 'enrollment' as const, row })),
  ].sort((a, b) => Number(!isPending(a)) - Number(!isPending(b)));

  const seatsFull = !campaign?.recruitment_open || campaign.seats_used >= campaign.current_capacity;
  const recruitmentOver = Boolean(campaign?.recruitment_ends_at && new Date(campaign.recruitment_ends_at) <= new Date());
  const pendingCount = applications.filter(row => row.state === 'pending').length;
  const period = (row: Campaign) => row.starts_at
    ? t('beta.campaigns.period', { start: date(row.starts_at), end: date(row.recruitment_ends_at) })
    : t('beta.campaigns.created', { date: date(row.created_at) });

  const startCreate = () => select(NEW);
  const startEdit = () => {
    if (campaign) { setSettings(pickSettings(campaign)); setEditingSettings(true); }
  };
  // `?c=new` arrive sans réglages : on prend ceux par défaut une fois le chargement fait.
  useEffect(() => {
    if (creating && data && !settings) setSettings(pickSettings(data.defaults));
  }, [creating, data, settings]);

  const card = creating ? (
    <section className="admin-panel" aria-labelledby="beta-card-title">
      <header className="admin-panel__head">
        <div>
          <span className="admin-panel__eyebrow">{t('beta.campaigns.eyebrow')}</span>
          <h2 id="beta-card-title">{t('beta.campaigns.new_title')}</h2>
        </div>
      </header>
      <div className="admin-panel__body">
        <section className="admin-panel__block">
          <p className="admin-panel__muted">{t('beta.campaigns.new_hint')}</p>
          {settings && <SettingsForm value={settings} onChange={setSettings} busy={busy} submitLabel={t(closeOthers && campaigns.some(row => row.state === 'open') ? 'beta.create_open' : 'beta.create')}
            onCancel={() => { setSettings(null); select(null); }}
            extra={campaigns.some(row => row.state === 'open') && <label className="admin-check admin-field--full">
              <input type="checkbox" checked={closeOthers} onChange={event => setCloseOthers(event.target.checked)} />
              {t('beta.campaigns.close_others')}
            </label>}
            onSubmit={() => createCampaign(settings)} />}
        </section>
      </div>
    </section>
  ) : campaign ? (
    <section className="admin-panel" aria-labelledby="beta-card-title">
      <header className="admin-panel__head">
        <div>
          <span className="admin-panel__eyebrow">{t('beta.campaigns.eyebrow')}</span>
          <h2 id="beta-card-title">{campaign.name}</h2>
        </div>
        <div className="admin-panel__head-actions">
          <button type="button" className="tb-btn ghost admin-btn" aria-pressed={editingSettings} disabled={busy}
            onClick={editingSettings ? () => setEditingSettings(false) : startEdit}>
            <Pencil size={16} strokeWidth={2.2} aria-hidden="true" />{t('beta.campaigns.edit')}
          </button>
          {selected && <button type="button" className="tb-btn ghost admin-icon-btn" onClick={() => select(null)}
            aria-label={t('beta.campaigns.close_card')} title={t('beta.campaigns.close_card')}>
            <X size={16} strokeWidth={2.2} />
          </button>}
        </div>
      </header>
      <div className="admin-panel__body">
        <section className="admin-panel__block">
          <AdminStats items={[
            { label: t('beta.seats'), value: `${campaign.seats_used} / ${campaign.capacity}` },
            { label: t('beta.wave_capacity'), value: campaign.current_capacity },
            { label: t('beta.recruitment_end'), value: date(campaign.recruitment_ends_at) },
          ]} />
        </section>

        {editingSettings && settings ? (
          <section className="admin-panel__block" aria-labelledby="beta-settings-title">
            <div className="admin-panel__block-head"><h3 id="beta-settings-title">{t('beta.campaigns.settings')}</h3></div>
            {otherOpen && campaign.state !== 'open'
              && <p className="admin-note">{t('beta.campaigns.other_open', { name: otherOpen.name })}</p>}
            <SettingsForm value={settings} onChange={setSettings} busy={busy} submitLabel={t('beta.save')}
              start={campaign.state === 'open' ? <button className="tb-btn admin-btn--danger" type="button" disabled={busy}
                onClick={() => void mutate('/api/admin/beta/campaigns/' + campaign.id, { state: 'closed' }, 'patch')}>
                {t('beta.close')}
              </button> : <button className="tb-btn ghost" type="button" disabled={busy || recruitmentOver || !!otherOpen}
                onClick={() => void mutate('/api/admin/beta/campaigns/' + campaign.id, { state: 'open' }, 'patch')}>
                {t('beta.open')}
              </button>}
              onCancel={() => setEditingSettings(false)}
              onSubmit={() => void mutate('/api/admin/beta/campaigns/' + campaign.id, settings, 'patch').then(saved => {
                if (saved) setEditingSettings(false);
              })} />
          </section>
        ) : (
          <section className="admin-panel__block" aria-label={t('beta.campaigns.tabs')}>
            <AdminToolbar>
              <div className="admin-toolbar__title">
                <h3>{t('beta.participants')}</h3>
                {pendingCount > 0 && <span className="admin-panel__muted">{t('beta.application.pending_count', { count: pendingCount })}</span>}
              </div>
              <div className="admin-toolbar__end">
                <button className="tb-btn ghost admin-btn" type="button" onClick={() => void copyLink()}>
                  {copied
                    ? <><Check size={16} strokeWidth={2.4} aria-hidden="true" color="#16a34a" /><span role="status">{t('beta.copied')}</span></>
                    : <><Link2 size={16} strokeWidth={2.2} aria-hidden="true" />{t('beta.copy_link')}</>}
                </button>
                <button type="button" className="beta-soft admin-btn" disabled={busy || campaign.state !== 'open'}
                  title={campaign.state !== 'open' ? t('beta.recruitment_closed') : undefined} onClick={() => setInviting(true)}>
                  <UserPlus size={16} strokeWidth={2.2} aria-hidden="true" />{t('beta.invite_by_email')}
                </button>
              </div>
            </AdminToolbar>
            <AdminList empty={people.length === 0} emptyText={t('beta.no_testers')}>
              {people.map(person => person.kind === 'application' ? (
                <div className="admin-row" key={'a' + person.row.id}>
                  <div className="admin-row__main">
                    <div className="admin-row__title"><UserLink email={person.row.email} /></div>
                    <div className="admin-row__meta">{t('beta.campaigns.kind_application')} · {t(`beta.formats.${person.row.primary_format}`)} · {date(person.row.submitted_at)}</div>
                    <p className="admin-detail__text">{person.row.motivation}</p>
                    <RiskNotice risk={person.row.risk} />
                    {person.row.state === 'pending' && seatsFull
                      && <p className="admin-note">{t('beta.application.approval_unavailable')}</p>}
                  </div>
                  <div className="admin-row__side">
                    <span className={'beta-status beta-status--application-' + person.row.state}>{t(`beta.application.states.${person.row.state}`)}</span>
                    <button className="beta-primary" disabled={busy || seatsFull}
                      onClick={() => void mutate('/api/admin/beta/applications/' + person.row.id, { decision: 'approved' }, 'patch')}>
                      {t('beta.application.approve')}
                    </button>
                    {person.row.state === 'pending' && <button className="tb-btn ghost" disabled={busy} onClick={() => setAsk({
                      message: t('beta.application.decline_confirm', { email: person.row.email }), label: t('beta.application.decline'),
                      onConfirm: () => void mutate('/api/admin/beta/applications/' + person.row.id, { decision: 'declined' }, 'patch'),
                    })}>{t('beta.application.decline')}</button>}
                  </div>
                </div>
              ) : (
                <div className="admin-row" key={'e' + person.row.id}>
                  <div className="admin-row__main">
                    <div className="admin-row__title"><UserLink email={person.row.email} /></div>
                    <div className="admin-row__meta admin-row__meta--inline">
                      <span>{t(`beta.formats.${person.row.primary_format}`)}
                        {person.row.expires_at && ' · ' + t('beta.expires', { date: date(person.row.expires_at) })}</span>
                      <BetaAllowances enrollment={person.row} compact />
                    </div>
                    <RiskNotice risk={person.row.risk} />
                  </div>
                  <div className="admin-row__side">
                    <span className={'beta-status beta-status--' + person.row.state}>{t(`beta.states.${person.row.state}`)}</span>
                    <button className="tb-btn ghost admin-icon-btn" disabled={busy} aria-label={t('beta.edit_limits')} title={t('beta.edit_limits')}
                      onClick={() => { setEditing(person.row); setEditLimits(person.row.limits); }}>
                      <SlidersHorizontal size={16} strokeWidth={2.2} aria-hidden="true" />
                    </button>
                    <button className="tb-btn ghost admin-icon-btn" disabled={busy}
                      aria-label={person.row.state === 'revoked' ? t('beta.restore') : t('beta.revoke')}
                      title={person.row.state === 'revoked' ? t('beta.restore') : t('beta.revoke')} onClick={() => {
                      const toggle = () => void mutate('/api/admin/beta/enrollments/' + person.row.id, { revoke: person.row.state !== 'revoked' }, 'patch');
                      if (person.row.state === 'revoked') toggle();
                      else setAsk({ message: t('beta.revoke_confirm', { email: person.row.email }), label: t('beta.revoke'), onConfirm: toggle });
                    }}>{person.row.state === 'revoked'
                      ? <RotateCcw size={16} strokeWidth={2.2} aria-hidden="true" />
                      : <UserX size={16} strokeWidth={2.2} aria-hidden="true" />}</button>
                  </div>
                </div>
              ))}
            </AdminList>
          </section>
        )}
      </div>
    </section>
  ) : (
    <p className="admin-duo__invite">{t('beta.campaigns.none')}</p>
  );

  return (
    <AdminShell title={t('beta.admin_title')}
      count={data ? t('beta.campaigns.count', { count: campaigns.length }) : undefined}
      actions={<>
        <button type="button" className="tb-btn admin-btn" disabled={busy || !data} onClick={startCreate}>
          <Plus size={16} strokeWidth={2.2} aria-hidden="true" />{t('beta.campaigns.new')}
        </button>
        <RefreshButton disabled={busy} onClick={() => load().catch(() => setError(t('beta.error')))} />
      </>}>
      {error && <p role="alert" className="beta-error">{error}</p>}
      {!data ? <div className="admin-loading" role="status">{t('beta.loading')}</div> : (
        <div className={`admin-duo${selected ? ' admin-duo--open' : ''}`}>
          <AdminList empty={campaigns.length === 0} emptyText={t('beta.campaigns.empty')}>
            {campaigns.map(row => (
              <button key={row.id} type="button" className="admin-row admin-row--button admin-duo__row"
                aria-current={!creating && row.id === campaign?.id ? 'true' : undefined}
                onClick={() => select(row.id)}>
                <div className="admin-row__main">
                  <div className="admin-row__title">{row.name}</div>
                  <div className="admin-row__meta">
                    {t('beta.campaigns.seats', { used: row.seats_used, capacity: row.capacity })} · {period(row)}
                  </div>
                </div>
                <span className={'beta-status beta-status--campaign-' + stateKey(row)}>
                  {t(`beta.campaign_states.${stateKey(row)}`)}
                </span>
              </button>
            ))}
          </AdminList>
          <div ref={cardRef} className="admin-duo__card">{card}</div>
        </div>
      )}
      {inviting && campaign && (
        <dialog ref={inviteDialog} aria-labelledby="beta-invite-title" className="beta-card beta-dialog"
          onCancel={event => { if (busy) event.preventDefault(); else setInviting(false); }}>
          <h2 id="beta-invite-title">{t('beta.invite')}</h2>
          <p className="admin-panel__muted">{t('beta.invite_hint')}</p>
          {!campaign.recruitment_open && <p className="beta-note">{t('beta.recruitment_closed')}</p>}
          <form onSubmit={event => {
            event.preventDefault();
            void mutate('/api/admin/beta/invitations', { email, primary_format: format, campaign_id: campaign.id }).then(ok => {
              if (ok) { setEmail(''); setInviting(false); }
            });
          }}>
            <fieldset disabled={busy} className="beta-fieldset admin-form">
              <label className="admin-field--wide">{t('beta.email')}<input className="admin-input" type="email" required maxLength={255} value={email}
                onChange={event => setEmail(event.target.value)} /></label>
              <label>{t('beta.primary_format')}<select className="admin-select" value={format}
                onChange={event => setFormat(event.target.value as BetaFormat)}>
                {BETA_FORMATS.map(item => <option key={item} value={item}>{t(`beta.formats.${item}`)}</option>)}
              </select></label>
              <div className="admin-form-footer">
                <span />
                <div className="admin-form-actions">
                  <button className="tb-btn ghost" type="button" onClick={() => setInviting(false)}>{t('beta.cancel')}</button>
                  <button className="beta-primary" disabled={busy || seatsFull}>{t('beta.invite')}</button>
                </div>
              </div>
            </fieldset>
          </form>
          {error && <p role="alert" className="beta-error">{error}</p>}
        </dialog>
      )}
      {editing && editLimits && (
        <dialog ref={dialog} aria-labelledby="beta-edit-title" className="beta-card beta-dialog"
          onCancel={event => { if (busy) event.preventDefault(); else setEditing(null); }}>
          <h2 id="beta-edit-title">{t('beta.edit_limits')}</h2><p>{editing.email}</p>
          <form onSubmit={event => {
            event.preventDefault();
            void mutate('/api/admin/beta/enrollments/' + editing.id, { limits: editLimits }, 'patch').then(ok => {
              if (ok) { setEditing(null); setEditLimits(null); }
            });
          }}>
            <fieldset disabled={busy} className="beta-fieldset admin-form">
              <LimitsEditor value={editLimits} onChange={setEditLimits} />
              <p className="admin-form-note">{t('beta.no_reset')}</p>
              <div className="admin-form-footer">
                <span />
                <div className="admin-form-actions">
                  <button className="tb-btn ghost" type="button" onClick={() => setEditing(null)}>{t('beta.cancel')}</button>
                  <button className="beta-primary">{t('beta.save')}</button>
                </div>
              </div>
            </fieldset>
          </form>
          {error && <p role="alert" className="beta-error">{error}</p>}
        </dialog>
      )}
      {ask && <ConfirmDialog ask={ask} onClose={() => setAsk(null)} />}
    </AdminShell>
  );
}
