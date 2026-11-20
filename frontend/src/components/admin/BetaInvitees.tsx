/**
 * Invitation bêta à plusieurs personnes : champ à sélection multiple (comptes
 * Précis suggérés, ou adresse tapée) et résultat personne par personne, avec
 * « Renvoyer » quand le mail n'est pas parti.
 */
import { useEffect, useId, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { RotateCcw, X } from 'lucide-react';
import api from '../../services/api';
import { betaError } from '../../lib/betaError';
import { showToast } from '../ui/Toast';

export const MAX_INVITEES = 20;
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export const isEmail = (text: string) => EMAIL.test(text.trim());

type Suggestion = { email: string; name: string | null };
export type InviteResult = { email: string; status: string; mail_sent?: boolean; enrollment?: { id: string } };

export function InviteeField({ labelId, value, onChange, pending, onPending }: {
  labelId: string; value: string[]; onChange: (next: string[]) => void; pending: string; onPending: (text: string) => void;
}) {
  const { t } = useTranslation();
  const listId = useId();
  const hintId = useId();
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [active, setActive] = useState(-1);
  const [open, setOpen] = useState(false);
  const query = pending.trim();

  useEffect(() => {
    if (query.length < 2) { setSuggestions([]); return; }
    let live = true;
    const timer = window.setTimeout(() => {
      void api.get('/api/admin/users?limit=8&q=' + encodeURIComponent(query)).then(result => {
        if (!live || !result.ok) return;
        const users = (result.data as { users?: Suggestion[] }).users ?? [];
        setSuggestions(users.filter(user => !value.includes(user.email.toLowerCase())));
        setActive(-1);
      });
    }, 250);
    return () => { live = false; window.clearTimeout(timer); };
  }, [query, value]);

  const add = (email: string) => {
    const clean = email.trim().toLowerCase();
    if (clean && !value.includes(clean) && value.length < MAX_INVITEES) onChange([...value, clean]);
    onPending(''); setSuggestions([]); setActive(-1);
  };
  const shown = open && query.length >= 2;
  const typed = EMAIL.test(query) && !suggestions.some(user => user.email.toLowerCase() === query.toLowerCase());

  return (
    <div className="beta-invitees">
      {value.length > 0 && (
        <ul className="beta-invitees__chips">
          {value.map(email => (
            <li key={email} className="beta-invitees__chip">
              <span>{email}</span>
              <button type="button" aria-label={t('beta.invitees.remove', { email })}
                onClick={() => onChange(value.filter(item => item !== email))}>
                <X size={14} strokeWidth={2.4} aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="beta-invitees__box">
      <input className="admin-input" type="text" inputMode="email" autoComplete="off" role="combobox"
        aria-expanded={shown} aria-controls={listId} aria-autocomplete="list" aria-labelledby={labelId} aria-describedby={hintId}
        aria-activedescendant={shown && active >= 0 ? `${listId}-${active}` : undefined}
        placeholder={t('beta.invitees.placeholder')} value={pending} disabled={value.length >= MAX_INVITEES}
        onChange={event => { onPending(event.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onBlur={() => { setOpen(false); if (EMAIL.test(query)) add(query); }}
        onKeyDown={event => {
          if (event.key === 'ArrowDown' && suggestions.length) {
            event.preventDefault(); setOpen(true); setActive(index => (index + 1) % suggestions.length);
          } else if (event.key === 'ArrowUp' && suggestions.length) {
            event.preventDefault(); setActive(index => (index <= 0 ? suggestions.length : index) - 1);
          } else if (event.key === 'Enter' || event.key === ',' || event.key === ';') {
            if (active >= 0 && suggestions[active]) { event.preventDefault(); add(suggestions[active].email); }
            else if (EMAIL.test(query)) { event.preventDefault(); add(query); }
            else if (event.key !== 'Enter') event.preventDefault();
          } else if (event.key === 'Escape' && shown) {
            event.preventDefault(); setOpen(false);
          } else if (event.key === 'Backspace' && !pending && value.length) {
            onChange(value.slice(0, -1));
          }
        }} />
      {shown && (suggestions.length > 0 || typed) && (
        <ul id={listId} role="listbox" className="beta-invitees__list">
          {suggestions.map((user, index) => (
            <li key={user.email} id={`${listId}-${index}`} role="option" aria-selected={index === active}
              className="beta-invitees__option" onMouseDown={event => { event.preventDefault(); add(user.email); }}>
              <strong>{user.name || user.email}</strong>
              {user.name && <span>{user.email}</span>}
            </li>
          ))}
          {typed && (
            <li role="option" aria-selected={false} className="beta-invitees__option"
              onMouseDown={event => { event.preventDefault(); add(query); }}>
              <span>{t('beta.invitees.add_typed', { email: query })}</span>
            </li>
          )}
        </ul>
      )}
      </div>
      <p id={hintId} className="admin-note">{t('beta.invitees.help', { max: MAX_INVITEES })}</p>
    </div>
  );
}

/** « Renvoyer » : renvoie le mail d'une invitation existante, sans la recréer. */
export function ResendMail({ enrollmentId, onSent }: { enrollmentId: string; onSent: () => void }) {
  const { t } = useTranslation();
  const [sending, setSending] = useState(false);
  const resend = async () => {
    setSending(true);
    try {
      const result = await api.post(`/api/admin/beta/enrollments/${enrollmentId}/email`, {});
      if (!result.ok) { showToast('error', betaError(t, result.data)); return; }
      if ((result.data as { mail_sent?: boolean }).mail_sent) {
        showToast('success', t('beta.invitees.resent')); onSent();
      } else showToast('error', t('beta.invitees.resend_failed'));
    } finally { setSending(false); }
  };
  return (
    <button type="button" className="tb-btn ghost" disabled={sending} onClick={() => void resend()}>
      <RotateCcw size={14} strokeWidth={2.2} aria-hidden="true" />{t('beta.invitees.resend')}
    </button>
  );
}

export function InviteResults({ results }: { results: InviteResult[] }) {
  const { t } = useTranslation();
  const [rows, setRows] = useState(results);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { setRows(results); heading.current?.focus(); }, [results]);
  const sent = (email: string) => setRows(list => list.map(row => row.email === email ? { ...row, mail_sent: true } : row));
  return (
    <section className="beta-results" aria-labelledby="beta-results-title">
      <h3 id="beta-results-title" ref={heading} tabIndex={-1}>{t('beta.invitees.results_title')}</h3>
      <ul>
        {rows.map(row => (
          <li key={row.email} className={'beta-results__row beta-results__row--' + (row.status === 'invited' ? 'ok' : 'refused')}>
            <span className="beta-results__email">{row.email}</span>
            <span className="beta-results__status">
              {row.status === 'invited'
                ? (row.mail_sent ? t('beta.invitees.invited_mailed') : t('beta.invitees.invited_not_mailed'))
                : t(`beta.errors.${row.status}`, { defaultValue: t('beta.error') })}
            </span>
            {row.status === 'invited' && !row.mail_sent && row.enrollment
              && <ResendMail enrollmentId={row.enrollment.id} onSent={() => sent(row.email)} />}
          </li>
        ))}
      </ul>
    </section>
  );
}
