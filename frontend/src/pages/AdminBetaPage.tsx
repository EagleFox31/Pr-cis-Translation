import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import AdminShell from '../components/admin/AdminShell';
import BetaAllowances, { BETA_FORMATS } from '../components/library/BetaAllowances';
import type { BetaApplication, BetaEnrollment, BetaFormat, BetaLimits } from '../hooks/useBeta';
import api from '../services/api';

interface Settings {
  name: string; capacity: number; first_wave_capacity: number; access_days: number; limits: BetaLimits;
}
interface Campaign extends Settings {
  id: string; state: 'draft' | 'open' | 'closed'; seats_used: number; current_capacity: number;
  starts_at: string | null; recruitment_ends_at: string | null; second_wave_at: string | null;
  recruitment_open: boolean;
}
interface BetaRisk {
  flags: { kind: 'same_mailbox' | 'same_ip' | 'same_browser' | 'rapid_sequence'; count: number }[];
  related_count: number; related: { email: string }[];
}
type ReviewedApplication = BetaApplication & { risk?: BetaRisk };
type ReviewedEnrollment = BetaEnrollment & { risk?: BetaRisk };
interface Dashboard { campaign: Campaign | null; enrollments: ReviewedEnrollment[]; defaults: Settings; applications: ReviewedApplication[] }

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
      <ul>{risk.related.map(person => <li key={person.email}>{person.email}</li>)}</ul>
    </>}
  </details>;
}
const LIMIT_KEYS: (keyof BetaLimits)[] = ['pdf', 'pptx', 'docx', 'xlsx', 'xlsx_words'];

function LimitsEditor({ value, onChange }: { value: BetaLimits; onChange: (v: BetaLimits) => void }) {
  const { t } = useTranslation();
  return <div className="beta-fields">
    {LIMIT_KEYS.map(key => (
      <label key={key}>{t(`beta.limit_labels.${key}`)}
        <input type="number" min={0} max={key === 'docx' || key === 'xlsx_words' ? 1000000 : key === 'xlsx' ? 10000 : 100000}
          required value={value[key]} onChange={event => onChange({ ...value, [key]: Number(event.target.value) })} />
      </label>
    ))}
  </div>;
}

export default function AdminBetaPage() {
  const { t, i18n } = useTranslation();
  const [data, setData] = useState<Dashboard | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [email, setEmail] = useState('');
  const [format, setFormat] = useState<BetaFormat>('pdf');
  const [editing, setEditing] = useState<BetaEnrollment | null>(null);
  const [editLimits, setEditLimits] = useState<BetaLimits | null>(null);
  const [filter, setFilter] = useState('all');
  const [applicationFilter, setApplicationFilter] = useState('pending');
  const [riskOnly, setRiskOnly] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (editing && dialog.current && !dialog.current.open) dialog.current.showModal();
  }, [editing]);
  const load = useCallback(async () => {
    const result = await api.get('/api/admin/beta');
    if (!result.ok) throw new Error(t('beta.error'));
    const dashboard = result.data as Dashboard;
    setData(dashboard);
    const current = dashboard.campaign || dashboard.defaults;
    setSettings({ name: current.name, capacity: current.capacity,
      first_wave_capacity: current.first_wave_capacity, access_days: current.access_days, limits: current.limits });
  }, [t]);
  useEffect(() => { load().catch(() => setError(t('beta.error'))); }, [load, t]);

  const mutate = async (path: string, body: unknown, method: 'post' | 'patch' = 'post') => {
    setBusy(true); setError(''); setNotice('');
    try {
      const result = await api[method](path, body);
      if (!result.ok) {
        const detail = (result.data as { detail?: unknown })?.detail;
        throw new Error(typeof detail === 'string' ? detail : t('beta.error'));
      }
      await load();
      setNotice(t('beta.saved'));
      return true;
    } catch (failure) {
      setError((failure as Error).message || t('beta.error'));
      return false;
    } finally { setBusy(false); }
  };
  const campaign = data?.campaign;
  const applications = data?.applications || [];
  const shownApplications = applications.filter(row =>
    (applicationFilter === 'all' || row.state === applicationFilter) && (!riskOnly || !!row.risk?.flags.length));
  const date = (value: string | null) => value ? new Date(value).toLocaleDateString(i18n.language) : '—';
  const copyLink = async () => {
    try { await navigator.clipboard.writeText(window.location.origin + '/beta'); setNotice(t('beta.copied')); }
    catch { setError(t('beta.copy_error')); }
  };

  const campaignState = campaign?.state === 'open' && !campaign.recruitment_open ? 'ended' : campaign?.state || 'draft';
  return (
    <AdminShell title={t('beta.admin_title')} actions={
      <button className="tb-btn ghost" disabled={busy} onClick={() => load().catch(() => setError(t('beta.error')))}>
        {t('beta.refresh')}
      </button>
    }>
      {error && <p role="alert" className="beta-error">{error}</p>}
      {notice && <p role="status" className="beta-notice">{notice}</p>}
      {!data || !settings ? <p>{t('beta.loading')}</p> : (
        <>
          <section className="beta-card">
            <div className="beta-heading">
              <div><h2>{t('beta.campaign')}</h2><p>{t('beta.campaign_hint')}</p></div>
              <span className="beta-status">{t(`beta.campaign_states.${campaignState}`)}</span>
            </div>
            {campaign && <div className="beta-metrics">
              <div><strong>{campaign.seats_used} / {campaign.capacity}</strong><span>{t('beta.seats')}</span></div>
              <div><strong>{campaign.current_capacity}</strong><span>{t('beta.wave_capacity')}</span></div>
              <div><strong>{date(campaign.second_wave_at)}</strong><span>{t('beta.second_wave')}</span></div>
              <div><strong>{date(campaign.recruitment_ends_at)}</strong><span>{t('beta.recruitment_end')}</span></div>
            </div>}
            <form onSubmit={event => {
              event.preventDefault();
              void mutate('/api/admin/beta/campaign',
                { ...settings, ...(campaign ? { state: campaign.state } : {}) }, campaign ? 'patch' : 'post');
            }}>
              <fieldset disabled={busy} className="beta-fieldset">
                <div className="beta-fields">
                  <label>{t('beta.name')}<input required maxLength={120} value={settings.name}
                    onChange={event => setSettings({ ...settings, name: event.target.value })} /></label>
                  {(['capacity', 'first_wave_capacity', 'access_days'] as const).map(key => (
                    <label key={key}>{t(`beta.${key}`)}
                      <input required type="number" min={1} max={key === 'access_days' ? 90 : 1000}
                        value={settings[key]} onChange={event => setSettings({ ...settings, [key]: Number(event.target.value) })} />
                    </label>
                  ))}
                </div>
                <h3>{t('beta.default_limits')}</h3>
                <LimitsEditor value={settings.limits} onChange={limits => setSettings({ ...settings, limits })} />
                <p className="beta-note">{t('beta.defaults_hint')}</p>
                <div className="beta-actions">
                  <button className="tb-btn" type="submit">{campaign ? t('beta.save') : t('beta.create')}</button>
                  {campaign && campaign.state !== 'open' && (
                    <button className="tb-btn" type="button"
                      disabled={Boolean(campaign.recruitment_ends_at && new Date(campaign.recruitment_ends_at) <= new Date())}
                      onClick={() => void mutate('/api/admin/beta/campaign', { ...settings, state: 'open' }, 'patch')}>
                      {t('beta.open')}
                    </button>
                  )}
                  {campaign?.state === 'open' && <button className="tb-btn ghost" type="button"
                    onClick={() => void mutate('/api/admin/beta/campaign', { ...settings, state: 'closed' }, 'patch')}>
                    {t('beta.close')}
                  </button>}
                </div>
              </fieldset>
            </form>
          </section>

          <section className="beta-card" aria-label={t('beta.application.admin_title')}>
            <div className="beta-heading">
              <div><h2>{t('beta.application.admin_title')}</h2>
                <p>{t('beta.application.pending_count', { count: applications.filter(row => row.state === 'pending').length })}</p>
              </div>
              <div className="beta-review-filters">
                <select aria-label={t('beta.application.filter')} value={applicationFilter}
                  onChange={event => setApplicationFilter(event.target.value)}>
                  <option value="all">{t('beta.all')}</option>
                  {['pending', 'approved', 'declined'].map(state => <option key={state} value={state}>
                    {t(`beta.application.states.${state}`)}
                  </option>)}
                </select>
                <label className="beta-risk-only"><input type="checkbox" checked={riskOnly}
                  onChange={event => setRiskOnly(event.target.checked)} />
                  {t('beta.safety.only_flagged')}
                </label>
              </div>
            </div>
            <p className="beta-note">{t('beta.application.admin_hint')}</p>
            {shownApplications.length === 0 && <p>{t('beta.application.none')}</p>}
            {shownApplications.map(row => <article className="beta-tester" key={row.id}>
              <div className="beta-heading">
                <div><strong>{row.email}</strong><p>{t(`beta.formats.${row.primary_format}`)} · {date(row.submitted_at)}</p></div>
                <span className="beta-status">{t(`beta.application.states.${row.state}`)}</span>
              </div>
              <p className="beta-application-text">{row.motivation}</p>
              <RiskNotice risk={row.risk} />
              {row.state !== 'approved' && <div className="beta-actions">
                <button className="beta-primary" disabled={busy || !campaign?.recruitment_open || campaign.seats_used >= campaign.current_capacity}
                  onClick={() => void mutate('/api/admin/beta/applications/' + row.id, { decision: 'approved' }, 'patch')}>
                  {t('beta.application.approve')}
                </button>
                {row.state === 'pending' && <button className="tb-btn ghost" disabled={busy} onClick={() => {
                  if (window.confirm(t('beta.application.decline_confirm', { email: row.email })))
                    void mutate('/api/admin/beta/applications/' + row.id, { decision: 'declined' }, 'patch');
                }}>{t('beta.application.decline')}</button>}
              </div>}
              {row.state === 'pending' && (!campaign?.recruitment_open || campaign.seats_used >= campaign.current_capacity)
                && <p className="beta-note">{t('beta.application.approval_unavailable')}</p>}
            </article>)}
          </section>

          {campaign && <section className="beta-card">
            <h2>{t('beta.invite')}</h2><p>{t('beta.invite_hint')}</p>
            {!campaign.recruitment_open && <p className="beta-note">{t('beta.recruitment_closed')}</p>}
            <form className="beta-invite" onSubmit={event => {
              event.preventDefault();
              void mutate('/api/admin/beta/invitations', { email, primary_format: format }).then(ok => { if (ok) setEmail(''); });
            }}>
              <label>{t('beta.email')}<input type="email" required maxLength={255} value={email}
                onChange={event => setEmail(event.target.value)} /></label>
              <label>{t('beta.primary_format')}<select value={format}
                onChange={event => setFormat(event.target.value as BetaFormat)}>
                {BETA_FORMATS.map(item => <option key={item} value={item}>{t(`beta.formats.${item}`)}</option>)}
              </select></label>
              <button className="tb-btn" disabled={busy || !campaign.recruitment_open || campaign.seats_used >= campaign.current_capacity}>
                {t('beta.invite')}
              </button>
              <button className="tb-btn ghost" type="button" onClick={() => void copyLink()}>{t('beta.copy_link')}</button>
            </form>
          </section>}

          <section className="beta-card">
            <div className="beta-heading"><h2>{t('beta.testers')}</h2>
              <select aria-label={t('beta.filter')} value={filter} onChange={event => setFilter(event.target.value)}>
                <option value="all">{t('beta.all')}</option>
                {['invited', 'active', 'expired', 'revoked'].map(state => <option key={state} value={state}>
                  {t(`beta.states.${state}`)}
                </option>)}
              </select>
            </div>
            {data.enrollments.length === 0 && <p>{t('beta.no_testers')}</p>}
            {data.enrollments.filter(row => filter === 'all' || row.state === filter).map(row => (
              <article className="beta-tester" key={row.id}>
                <div className="beta-heading">
                  <div><strong>{row.email}</strong><p>{t(`beta.formats.${row.primary_format}`)}
                    {row.expires_at && ' · ' + t('beta.expires', { date: date(row.expires_at) })}</p></div>
                  <span className={'beta-status beta-status--' + row.state}>{t(`beta.states.${row.state}`)}</span>
                </div>
                <RiskNotice risk={row.risk} />
                <BetaAllowances enrollment={row} />
                <div className="beta-actions">
                  <button className="tb-btn ghost" disabled={busy} onClick={() => { setEditing(row); setEditLimits(row.limits); }}>
                    {t('beta.edit_limits')}
                  </button>
                  <button className="tb-btn ghost" disabled={busy} onClick={() => {
                    if (row.state === 'revoked' || window.confirm(t('beta.revoke_confirm', { email: row.email })))
                      void mutate('/api/admin/beta/enrollments/' + row.id, { revoke: row.state !== 'revoked' }, 'patch');
                  }}>{row.state === 'revoked' ? t('beta.restore') : t('beta.revoke')}</button>
                </div>
              </article>
            ))}
          </section>
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
                <fieldset disabled={busy} className="beta-fieldset">
                  <LimitsEditor value={editLimits} onChange={setEditLimits} />
                  <p>{t('beta.no_reset')}</p>
                  <div className="beta-actions"><button className="tb-btn">{t('beta.save')}</button>
                    <button className="tb-btn ghost" type="button" onClick={() => setEditing(null)}>{t('beta.cancel')}</button></div>
                </fieldset>
              </form>
              {error && <p role="alert" className="beta-error">{error}</p>}
            </dialog>
          )}
        </>
      )}
    </AdminShell>
  );
}
