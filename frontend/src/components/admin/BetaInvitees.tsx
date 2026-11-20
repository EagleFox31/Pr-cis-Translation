/**
 * Invitation bêta à plusieurs personnes : champ à sélection multiple (seuls les
 * comptes Précis, choisis dans les suggestions) et résultat personne par personne,
 * avec « Renvoyer » quand le mail n'est pas parti.
 */
import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { RotateCcw, Send, X } from 'lucide-react';
import api from '../../services/api';
import { betaError } from '../../lib/betaError';
import { showToast } from '../ui/Toast';

export const MAX_INVITEES = 20;
const SHOWN_SUGGESTIONS = 8;

type Suggestion = { email: string; name: string | null };
export type InviteResult = { email: string; status: string; mail_sent?: boolean; enrollment?: { id: string } };

/**
 * Les adresses choisies restent dans le champ, sur une ligne : celles qui ne
 * tiennent pas sont comptées dans une étiquette « +N » qui déplie la liste.
 */
export function InviteeField({ labelId, value, onChange, exclude }: {
  labelId: string; value: string[]; onChange: (next: string[]) => void;
  /** Adresses déjà inscrites au programme : jamais suggérées. */
  exclude: string[];
}) {
  const { t } = useTranslation();
  const listId = useId();
  const hintId = useId();
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [active, setActive] = useState(-1);
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [hidden, setHidden] = useState(0);
  const [announce, setAnnounce] = useState('');
  const chips = useRef<HTMLUListElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const excluded = exclude.join('\n');

  // Suggestions dès l'ouverture (derniers inscrits), filtrées à la frappe.
  useEffect(() => {
    if (!open) return;
    let live = true;
    const term = query.trim();
    const timer = window.setTimeout(() => {
      void api.get('/api/admin/users?limit=20' + (term ? '&q=' + encodeURIComponent(term) : '')).then(result => {
        if (!live || !result.ok) return;
        const taken = new Set([...value, ...excluded.split('\n')].map(email => email.toLowerCase()));
        const users = (result.data as { users?: Suggestion[] }).users ?? [];
        setSuggestions(users.filter(user => !taken.has(user.email.toLowerCase())).slice(0, SHOWN_SUGGESTIONS));
        setLoaded(true); setActive(-1);
      });
    }, term ? 250 : 0);
    return () => { live = false; window.clearTimeout(timer); };
  }, [open, query, value, excluded]);

  // Combien d'adresses passent à la ligne (donc masquées) quand le champ est replié.
  useLayoutEffect(() => {
    const list = chips.current;
    if (!list || expanded) { setHidden(0); return; }
    const measure = () => {
      const items = Array.from(list.children) as HTMLElement[];
      const top = items[0]?.offsetTop ?? 0;
      setHidden(items.filter(item => item.offsetTop > top).length);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(list);
    return () => observer.disconnect();
  }, [value, expanded]);

  const add = (email: string) => {
    const clean = email.trim().toLowerCase();
    if (clean && !value.includes(clean) && value.length < MAX_INVITEES) {
      onChange([...value, clean]);
      setAnnounce(t('beta.invitees.added', { email: clean }));
    }
    setQuery(''); setActive(-1);
  };
  const remove = (email: string) => {
    onChange(value.filter(item => item !== email));
    setAnnounce(t('beta.invitees.removed', { email }));
    input.current?.focus();
  };
  const shown = open && loaded;
  const full = value.length >= MAX_INVITEES;

  return (
    <div className="beta-invitees">
      <div className={'beta-invitees__box' + (expanded ? ' beta-invitees__box--open' : '')}
        onMouseDown={event => { if (event.target === event.currentTarget) { event.preventDefault(); input.current?.focus(); } }}>
        {value.length > 0 && (
          <ul ref={chips} className="beta-invitees__chips">
            {value.map(email => (
              <li key={email} className="beta-invitees__chip" title={email}>
                <span>{email}</span>
                <button type="button" aria-label={t('beta.invitees.remove', { email })} onClick={() => remove(email)}>
                  <X size={14} strokeWidth={2.4} aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>
        )}
        {(hidden > 0 || expanded) && (
          <button type="button" className="beta-invitees__more" aria-expanded={expanded}
            aria-label={expanded ? t('beta.invitees.less') : t('beta.invitees.more', { count: hidden })}
            onClick={() => setExpanded(value => !value)}>
            {expanded ? t('beta.invitees.less') : `+${hidden}`}
          </button>
        )}
        <input ref={input} className="beta-invitees__input" type="text" autoComplete="off" role="combobox"
          aria-expanded={shown} aria-controls={listId} aria-autocomplete="list" aria-labelledby={labelId} aria-describedby={hintId}
          aria-activedescendant={shown && active >= 0 ? `${listId}-${active}` : undefined}
          placeholder={full ? '' : t('beta.invitees.placeholder')} value={query} disabled={full}
          onChange={event => { setQuery(event.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={event => {
            if (event.key === 'ArrowDown' && suggestions.length) {
              event.preventDefault(); setOpen(true); setActive(index => (index + 1) % suggestions.length);
            } else if (event.key === 'ArrowUp' && suggestions.length) {
              event.preventDefault(); setActive(index => (index <= 0 ? suggestions.length : index) - 1);
            } else if (event.key === 'Enter' && shown) {
              // Entrée choisit la suggestion active ; elle n'envoie jamais le formulaire depuis la liste.
              event.preventDefault();
              const pick = suggestions[active >= 0 ? active : suggestions.length === 1 ? 0 : -1];
              if (pick) add(pick.email);
            } else if (event.key === 'Escape' && shown) {
              event.preventDefault(); event.stopPropagation(); setOpen(false);
            } else if (event.key === 'Backspace' && !query && value.length) {
              remove(value[value.length - 1]);
            }
          }} />
      </div>
      {shown && (
        <ul id={listId} role="listbox" aria-labelledby={labelId} className="beta-invitees__list">
          {suggestions.map((user, index) => (
            <li key={user.email} id={`${listId}-${index}`} role="option" aria-selected={index === active}
              className="beta-invitees__option" onMouseDown={event => { event.preventDefault(); add(user.email); }}>
              <strong>{user.name || user.email}</strong>
              {user.name && <span>{user.email}</span>}
            </li>
          ))}
          {suggestions.length === 0 && <li className="beta-invitees__empty">{t('beta.invitees.no_match')}</li>}
        </ul>
      )}
      <p id={hintId} className="admin-note">{t('beta.invitees.help', { max: MAX_INVITEES })}</p>
      <span className="sr-only" role="status">{announce}</span>
    </div>
  );
}

/**
 * « Renvoyer » : renvoie le mail d'une invitation existante, sans la recréer.
 * `icon` : petite icône de ligne (liste des participants) au lieu du bouton texte.
 */
export function ResendMail({ enrollmentId, onSent, icon = false }: { enrollmentId: string; onSent: () => void; icon?: boolean }) {
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
  if (icon) return (
    <button type="button" className="tb-btn ghost admin-icon-btn" disabled={sending} onClick={() => void resend()}
      aria-label={t('beta.invitees.resend_mail')} title={t('beta.invitees.resend_mail')}>
      <Send size={16} strokeWidth={2.2} aria-hidden="true" />
    </button>
  );
  return (
    <button type="button" className="tb-btn ghost" disabled={sending} onClick={() => void resend()}>
      <RotateCcw size={14} strokeWidth={2.2} aria-hidden="true" />{t('beta.invitees.resend')}
    </button>
  );
}

export function InviteResults({ results, onResent }: { results: InviteResult[]; onResent?: () => void }) {
  const { t } = useTranslation();
  const [rows, setRows] = useState(results);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { setRows(results); heading.current?.focus(); }, [results]);
  const sent = (email: string) => {
    setRows(list => list.map(row => row.email === email ? { ...row, mail_sent: true } : row));
    onResent?.();
  };
  return (
    <section className="beta-results" aria-labelledby="beta-results-title">
      <h3 id="beta-results-title" ref={heading} tabIndex={-1}>{t('beta.invitees.results_title')}</h3>
      <ul>
        {rows.map(row => (
          <li key={row.email} className={'beta-results__row beta-results__row--' + (row.status === 'invited' ? 'ok' : 'refused')}>
            <span className="beta-results__email" title={row.email}>{row.email}</span>
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
