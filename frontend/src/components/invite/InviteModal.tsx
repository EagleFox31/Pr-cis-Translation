/**
 * Fenêtre d'invitation — l'utilisateur invite des proches à découvrir Précis.
 * Une ou plusieurs adresses (virgule, espace, Entrée ou collage d'une liste),
 * un mot facultatif. L'e-mail part au nom de l'utilisateur, à la marque Précis.
 *
 * Même hôte unique que `SupportModal`, ouvert par `openInvite()`.
 * Le serveur borne les envois (10 par envoi, quota quotidien) et ne dit jamais
 * quelles adresses ont déjà un compte : on affiche un succès générique.
 *
 * Repli « copier le lien » : là où l'e-mail n'est pas le canal habituel
 * (WhatsApp…), l'utilisateur partage lui-même l'adresse du site.
 */
import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { X, UserPlus, Loader2, Send, Link2, Check } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import api from '../../services/api';
import { showToast } from '../ui/Toast';
import { useAuth } from '../../contexts/AuthContext';
import { subscribeInvite } from './inviteBus';

const MAX_EMAILS = 10;
const MAX_MESSAGE = 500;
const EMAIL_RE = /^[^\s@,;]+@[^\s@,;]+\.[^\s@,;]+$/;
const SEPARATEURS = /[\s,;]+/;
const LIEN_APP = window.location.origin;

const field: React.CSSProperties = {
  width: '100%', padding: '11px 12px', borderRadius: '10px', fontSize: '14px',
  outline: 'none', border: '1.5px solid var(--gray-200)', background: 'var(--gray-50)',
  fontFamily: 'inherit', boxSizing: 'border-box',
};

export default function InviteModal() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [emails, setEmails] = useState<string[]>([]);
  const [draft, setDraft] = useState('');
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [copied, setCopied] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => subscribeInvite(() => {
    setEmails([]);
    setDraft('');
    setMessage('');
    setCopied(false);
    setOpen(true);
  }), []);

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(LIEN_APP);
      setCopied(true);
    } catch {
      showToast('error', t('invite.copy_error', 'Copie impossible'), LIEN_APP);
    }
  }

  const close = () => setOpen(false);
  const self = user?.email?.toLowerCase();

  /** Ajoute les adresses valides du texte ; renvoie ce qui n'a pas pu l'être. */
  function absorb(text: string): string {
    const rejet: string[] = [];
    const next = [...emails];
    for (const brut of text.split(SEPARATEURS)) {
      const e = brut.trim().toLowerCase();
      if (!e) continue;
      if (!EMAIL_RE.test(e) || e === self || next.length >= MAX_EMAILS) { rejet.push(brut); continue; }
      if (!next.includes(e)) next.push(e);
    }
    setEmails(next);
    return rejet.join(' ');
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (['Enter', ',', ';', ' ', 'Tab'].includes(e.key) && draft.trim()) {
      if (e.key !== 'Tab' || EMAIL_RE.test(draft.trim())) e.preventDefault();
      setDraft(absorb(draft));
    } else if (e.key === 'Backspace' && !draft && emails.length) {
      setEmails(emails.slice(0, -1));
    }
  }

  function onPaste(e: React.ClipboardEvent<HTMLInputElement>) {
    const text = e.clipboardData.getData('text');
    if (SEPARATEURS.test(text.trim())) {
      e.preventDefault();
      setDraft(absorb(draft + ' ' + text));
    }
  }

  // Le brouillon est pris en compte à l'envoi : on ne doit pas exiger
  // d'appuyer sur Entrée pour une adresse unique.
  const pending = draft.trim().toLowerCase();
  const draftValid = EMAIL_RE.test(pending) && pending !== self;
  const all = draftValid && !emails.includes(pending) ? [...emails, pending] : emails;
  const draftInvalid = !!pending && !draftValid;
  const canSend = !sending && all.length > 0 && all.length <= MAX_EMAILS && !draftInvalid;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSend) return;
    setSending(true);
    let res;
    try {
      res = await api.post('/api/invitations', {
        emails: all, message: message.trim() || null,
      });
    } catch {
      res = null;
    } finally {
      setSending(false);
    }
    if (res?.ok) {
      showToast('success', t('invite.sent_title', 'Invitations envoyées'),
        t('invite.sent_body', { count: all.length,
          defaultValue: '{{count}} invitation(s) en route.' }));
      close();
    } else if (res?.status === 429) {
      showToast('error', t('invite.limit_title', 'Limite atteinte'),
        t('invite.limit_body', 'Vous avez atteint le nombre d’invitations du jour. Réessayez demain.'));
    } else if (res?.status === 422) {
      showToast('error', t('invite.error_title', 'Envoi impossible'),
        t('invite.rejected_body', 'Une des adresses est refusée : vérifiez-les.'));
    } else {
      showToast('error', t('invite.error_title', 'Envoi impossible'),
        t('invite.error_body', 'Réessayez dans un instant.'));
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={sending ? undefined : close}
            style={{ position: 'fixed', inset: 0, background: 'rgba(13,27,62,0.45)',
                     zIndex: 1200, backdropFilter: 'blur(3px)' }}
          />
          <motion.div
            role="dialog" aria-modal="true" aria-labelledby="invite-title"
            initial={{ opacity: 0, y: 20, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.98 }}
            style={{
              position: 'fixed', right: '20px', bottom: '20px',
              width: 'min(440px, 92vw)', maxHeight: 'calc(100vh - 40px)',
              overflowY: 'auto', background: 'white', borderRadius: '18px',
              boxShadow: '0 24px 70px rgba(13,27,62,0.28)', zIndex: 1201, padding: '26px 24px',
            }}
          >
            {!sending && (
              <button onClick={close} aria-label={t('invite.close', 'Fermer')}
                style={{ position: 'absolute', top: 14, right: 14, background: 'none',
                         border: 'none', cursor: 'pointer', color: 'var(--gray-400)' }}>
                <X size={18} />
              </button>
            )}

            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
              <UserPlus size={20} color="var(--blue)" strokeWidth={2.2} />
              <h2 id="invite-title" style={{ fontSize: '18px', fontWeight: 700, margin: 0 }}>
                {t('invite.title', 'Inviter des proches')}
              </h2>
            </div>
            <p style={{ fontSize: '13px', color: 'var(--gray-500)', margin: '0 0 16px' }}>
              {t('invite.subtitle', 'Ils recevront un e-mail de votre part pour découvrir Précis.')}
            </p>

            <form onSubmit={submit}>
              <label htmlFor="invite-emails" style={{ fontSize: '12.5px', fontWeight: 600,
                     color: 'var(--gray-600)', display: 'block', marginBottom: 6 }}>
                {t('invite.emails_label', 'Adresses e-mail')}
              </label>
              {/* Champ « à puces » : chaque adresse validée devient une pastille. */}
              <div onClick={() => inputRef.current?.focus()}
                style={{ ...field, display: 'flex', flexWrap: 'wrap', gap: 6, padding: '7px 8px',
                         cursor: 'text', minHeight: 44,
                         borderColor: draftInvalid ? 'var(--red, #dc2626)' : 'var(--gray-200)' }}>
                {emails.map((e) => (
                  <span key={e} style={{
                    display: 'inline-flex', alignItems: 'center', gap: 4, maxWidth: '100%',
                    padding: '4px 6px 4px 10px', borderRadius: 999, fontSize: '12.5px',
                    background: 'var(--blue-light, #eff6ff)', color: '#1e40af',
                    border: '1px solid #bfdbfe',
                  }}>
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e}</span>
                    <button type="button" disabled={sending}
                      aria-label={t('invite.remove', { email: e, defaultValue: 'Retirer {{email}}' })}
                      onClick={(ev) => { ev.stopPropagation(); setEmails(emails.filter((x) => x !== e)); }}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 2,
                               color: '#1e40af', display: 'flex' }}>
                      <X size={12} strokeWidth={2.6} />
                    </button>
                  </span>
                ))}
                <input
                  id="invite-emails" ref={inputRef} type="email" multiple autoFocus
                  value={draft} disabled={sending || emails.length >= MAX_EMAILS}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={onKeyDown} onPaste={onPaste}
                  onBlur={() => { if (draftValid) setDraft(absorb(draft)); }}
                  placeholder={emails.length ? '' : t('invite.emails_ph', 'nom@exemple.com, …')}
                  aria-invalid={draftInvalid}
                  style={{ flex: '1 1 140px', minWidth: 0, border: 'none', outline: 'none',
                           background: 'transparent', fontSize: '14px', fontFamily: 'inherit',
                           padding: '4px 2px' }}
                />
              </div>
              <p style={{ fontSize: '11.5px', margin: '6px 0 14px',
                          color: draftInvalid ? 'var(--red, #dc2626)' : 'var(--gray-400)' }}>
                {draftInvalid
                  ? t('invite.invalid', 'Adresse invalide.')
                  : emails.length >= MAX_EMAILS
                  ? t('invite.full', { max: MAX_EMAILS,
                      defaultValue: '{{max}} adresses au maximum par envoi.' })
                  : t('invite.hint', { max: MAX_EMAILS,
                      defaultValue: 'Séparez par une virgule ou Entrée — {{max}} au maximum.' })}
              </p>

              <label htmlFor="invite-message" style={{ fontSize: '12.5px', fontWeight: 600,
                     color: 'var(--gray-600)', display: 'block', marginBottom: 6 }}>
                {t('invite.message_label', 'Un mot (facultatif)')}
              </label>
              <textarea
                id="invite-message" value={message} onChange={(e) => setMessage(e.target.value)}
                placeholder={t('invite.message_ph', 'J’utilise Précis pour traduire mes documents, essaie-le !')}
                maxLength={MAX_MESSAGE} rows={3} disabled={sending}
                style={{ ...field, resize: 'vertical', minHeight: 80 }}
              />

              <button type="submit" disabled={!canSend}
                style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                         gap: 8, padding: '12px', marginTop: 16, borderRadius: '10px', border: 'none',
                         background: 'var(--blue)', color: 'white', fontWeight: 600, fontSize: '14.5px',
                         cursor: canSend ? 'pointer' : 'default', fontFamily: 'inherit',
                         opacity: canSend ? 1 : 0.6 }}>
                {sending
                  ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
                  : <Send size={16} />}
                {all.length > 1
                  ? t('invite.send_n', { count: all.length, defaultValue: 'Envoyer {{count}} invitations' })
                  : t('invite.send', 'Envoyer l’invitation')}
              </button>
            </form>

            <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '18px 0 12px',
                          fontSize: '12px', color: 'var(--gray-500)' }}>
              <span style={{ flex: 1, height: 1, background: 'var(--gray-200)' }} />
              {t('invite.or_share', 'ou partagez le lien vous-même')}
              <span style={{ flex: 1, height: 1, background: 'var(--gray-200)' }} />
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <input readOnly value={LIEN_APP} aria-label={t('invite.link_label', 'Lien de Précis')}
                onFocus={(e) => e.currentTarget.select()}
                style={{ ...field, flex: 1, minWidth: 0, color: 'var(--gray-600)' }} />
              <button type="button" onClick={copyLink}
                style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '0 14px',
                         borderRadius: '10px', border: '1px solid var(--gray-200)',
                         background: 'white', color: copied ? '#047857' : 'var(--gray-700)',
                         fontWeight: 600, fontSize: '13.5px', cursor: 'pointer',
                         fontFamily: 'inherit', whiteSpace: 'nowrap' }}>
                {copied ? <Check size={15} /> : <Link2 size={15} />}
                <span aria-live="polite">
                  {copied ? t('invite.copied', 'Lien copié') : t('invite.copy', 'Copier le lien')}
                </span>
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
