/**
 * Invitation bêta à plusieurs personnes : champ à sélection multiple (seuls les
 * comptes Précis, choisis dans les suggestions) et résultat personne par personne,
 * avec « Renvoyer » dans la liste quand le mail n'est pas parti.
 */
import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, RotateCcw, Send } from 'lucide-react';
import api from '../../services/api';
import { betaError } from '../../lib/betaError';
import { showToast } from '../ui/Toast';

export const MAX_INVITEES = 20;
const SHOWN_SUGGESTIONS = 8;

type Suggestion = { email: string; name: string | null };
export type InviteResult = { email: string; status: string; mail_sent?: boolean; enrollment?: { id: string } };

/**
 * Champ replié : les noms choisis tiennent sur une ligne, une étiquette « +N »
 * compte ceux qui ne tiennent pas. Un clic ouvre la liste des comptes, où les
 * personnes déjà choisies sont cochées ; on coche ou décoche pour composer la liste.
 */
export function InviteeField({ labelId, value, onChange, exclude }: {
  labelId: string; value: string[]; onChange: (next: string[]) => void;
  /** Adresses déjà inscrites au programme : jamais proposées. */
  exclude: string[];
}) {
  const { t } = useTranslation();
  const listId = useId();
  const hintId = useId();
  const [query, setQuery] = useState('');
  const [found, setFound] = useState<Suggestion[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [active, setActive] = useState(-1);
  const [open, setOpen] = useState(false);
  const [hidden, setHidden] = useState(0);
  const [announce, setAnnounce] = useState('');
  // Nom affiché pour chaque adresse choisie (l'adresse sert de repli).
  const [names, setNames] = useState<Record<string, string | null>>({});
  const chips = useRef<HTMLUListElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const excluded = exclude.join('\n');

  // Liste dès l'ouverture (derniers inscrits), filtrée à la frappe.
  useEffect(() => {
    if (!open) return;
    let live = true;
    const term = query.trim();
    const timer = window.setTimeout(() => {
      void api.get('/api/admin/users?limit=20' + (term ? '&q=' + encodeURIComponent(term) : '')).then(result => {
        if (!live || !result.ok) return;
        const taken = new Set(excluded.split('\n').map(email => email.toLowerCase()));
        const users = (result.data as { users?: Suggestion[] }).users ?? [];
        setFound(users.filter(user => !taken.has(user.email.toLowerCase()))
          .map(user => ({ ...user, email: user.email.toLowerCase() })));
        setLoaded(true); setActive(-1);
      });
    }, term ? 250 : 0);
    return () => { live = false; window.clearTimeout(timer); };
  }, [open, query, excluded]);

  // Sans recherche, les personnes choisies sont en tête ; avec une recherche, seuls les résultats.
  const options: Suggestion[] = query.trim()
    ? found
    : [...value.map(email => ({ email, name: names[email] ?? null })),
       ...found.filter(user => !value.includes(user.email)).slice(0, SHOWN_SUGGESTIONS)];

  // Combien de noms ne tiennent pas sur la ligne du champ replié.
  useLayoutEffect(() => {
    const list = chips.current;
    if (!list) { setHidden(0); return; }
    const measure = () => {
      const items = Array.from(list.children) as HTMLElement[];
      const top = items[0]?.offsetTop ?? 0;
      setHidden(items.filter(item => item.offsetTop > top).length);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(list);
    return () => observer.disconnect();
  }, [value, open, names]);

  const full = value.length >= MAX_INVITEES;
  const toggle = (user: Suggestion) => {
    const email = user.email;
    if (value.includes(email)) {
      onChange(value.filter(item => item !== email));
      setAnnounce(t('beta.invitees.removed', { email }));
    } else if (!full) {
      onChange([...value, email]);
      setNames(map => ({ ...map, [email]: user.name }));
      setAnnounce(t('beta.invitees.added', { email }));
    }
  };
  const shown = open && loaded;
  const idle = !open && value.length > 0;
  const close = () => { setOpen(false); setQuery(''); setActive(-1); };

  return (
    <div className="beta-invitees">
      {/* La liste flotte sous le champ : la fermer ne déplace pas les boutons pendant un clic. */}
      <div className="beta-invitees__anchor">
        <div className="beta-invitees__box"
          onMouseDown={event => { if (event.target !== input.current) { event.preventDefault(); input.current?.focus(); } }}>
          {idle && (
            <>
              {/* Copie invisible qui mesure combien de noms tiennent ; on n'affiche que ceux-là, « +N » collé à la suite. */}
              <ul ref={chips} className="beta-invitees__chips beta-invitees__chips--measure" aria-hidden="true">
                {value.map(email => <li key={email} className="beta-invitees__chip">{names[email] || email}</li>)}
              </ul>
              <ul className={'beta-invitees__chips' + (hidden > 0 ? ' beta-invitees__chips--fill' : '')} aria-hidden="true">
                {value.slice(0, value.length - hidden).map(email => (
                  <li key={email} className="beta-invitees__chip" title={email}>{names[email] || email}</li>
                ))}
              </ul>
              {hidden > 0 && <span className="beta-invitees__more" aria-hidden="true">+{hidden}</span>}
            </>
          )}
          <input ref={input} className={'beta-invitees__input' + (idle ? ' beta-invitees__input--idle' : '')}
            type="text" autoComplete="off" role="combobox"
            aria-expanded={shown} aria-controls={listId} aria-autocomplete="list" aria-labelledby={labelId} aria-describedby={hintId}
            aria-activedescendant={shown && active >= 0 ? `${listId}-${active}` : undefined}
            placeholder={idle ? '' : t('beta.invitees.placeholder')} value={query}
            onChange={event => { setQuery(event.target.value); setOpen(true); }}
            onFocus={() => setOpen(true)}
            onBlur={close}
            onKeyDown={event => {
              if (event.key === 'ArrowDown' && options.length) {
                event.preventDefault(); setOpen(true); setActive(index => (index + 1) % options.length);
              } else if (event.key === 'ArrowUp' && options.length) {
                event.preventDefault(); setActive(index => (index <= 0 ? options.length : index) - 1);
              } else if (event.key === 'Enter' && shown) {
                // Entrée coche ou décoche l'option active ; elle n'envoie jamais le formulaire depuis la liste.
                event.preventDefault();
                const pick = options[active >= 0 ? active : options.length === 1 ? 0 : -1];
                if (pick) toggle(pick);
              } else if (event.key === 'Escape' && shown) {
                event.preventDefault(); event.stopPropagation(); input.current?.blur();
              }
            }} />
        </div>
        {shown && (
          <ul id={listId} role="listbox" aria-multiselectable="true" aria-labelledby={labelId} className="beta-invitees__list">
            {options.map((user, index) => {
              const checked = value.includes(user.email);
              return (
                <li key={user.email} id={`${listId}-${index}`} role="option" aria-selected={checked}
                  aria-disabled={!checked && full}
                  className={'beta-invitees__option' + (index === active ? ' beta-invitees__option--active' : '')}
                  onMouseDown={event => { event.preventDefault(); toggle(user); }}>
                  <span className={'beta-invitees__check' + (checked ? ' beta-invitees__check--on' : '')} aria-hidden="true">
                    {checked && <Check size={14} strokeWidth={3} />}
                  </span>
                  <span className="beta-invitees__who">
                    <strong>{user.name || user.email}</strong>
                    {user.name && <span>{user.email}</span>}
                  </span>
                </li>
              );
            })}
            {options.length === 0 && <li className="beta-invitees__empty">{t('beta.invitees.no_match')}</li>}
          </ul>
        )}
      </div>
      <p id={hintId} className="admin-note beta-invitees__hint">
        <span>{t('beta.invitees.help')}</span>
        <span className="beta-invitees__count">{value.length} / {MAX_INVITEES}</span>
      </p>
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
