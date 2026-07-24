/**
 * Fenêtre d'assistance — l'utilisateur SIGNALE un problème ou demande de l'aide
 * sur son ABONNEMENT. Trois catégories, un sujet, un message. Rien de plus : une
 * demande d'aide qui exige un formulaire long ne se remplit jamais.
 *
 * Le contexte (page d'où l'on écrit) part avec la demande sans qu'on le tape —
 * c'est au support de savoir où on était, pas à l'utilisateur de le raconter.
 */
import { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { X, LifeBuoy, Loader2, Send } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import api from '../../services/api';
import { showToast } from '../ui/Toast';

interface SupportModalProps {
  open: boolean;
  onClose: () => void;
}

type Category = 'problem' | 'subscription' | 'other';

const field: React.CSSProperties = {
  width: '100%', padding: '11px 12px', borderRadius: '10px', fontSize: '14px',
  outline: 'none', border: '1.5px solid var(--gray-200)', background: 'var(--gray-50)',
  fontFamily: 'inherit', boxSizing: 'border-box',
};

export default function SupportModal({ open, onClose }: SupportModalProps) {
  const { t } = useTranslation();
  const [category, setCategory] = useState<Category>('problem');
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);

  const cats: { key: Category; label: string }[] = [
    { key: 'problem', label: t('support.cat_problem', 'Signaler un problème') },
    { key: 'subscription', label: t('support.cat_subscription', 'Mon abonnement') },
    { key: 'other', label: t('support.cat_other', 'Autre') },
  ];

  const reset = () => { setCategory('problem'); setSubject(''); setMessage(''); };

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!subject.trim() || !message.trim()) return;
    setSending(true);
    const res = await api.post('/api/support', {
      category, subject: subject.trim(), message: message.trim(),
      url: window.location.pathname + window.location.hash,
    });
    setSending(false);
    if (res.ok) {
      showToast('success', t('support.sent_title', 'Message envoyé'),
        t('support.sent_body', 'Nous revenons vers vous par e-mail.'));
      reset();
      onClose();
    } else {
      showToast('error', t('support.error_title', 'Envoi impossible'),
        t('support.error_body', 'Réessayez dans un instant.'));
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={sending ? undefined : onClose}
            style={{ position: 'fixed', inset: 0, background: 'rgba(13,27,62,0.45)',
                     zIndex: 1200, backdropFilter: 'blur(3px)' }}
          />
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.98 }}
            style={{
              position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
              width: 'min(440px, 92vw)', background: 'white', borderRadius: '18px',
              boxShadow: '0 24px 70px rgba(13,27,62,0.28)', zIndex: 1201, padding: '26px 24px',
            }}
          >
            {!sending && (
              <button onClick={onClose} aria-label={t('support.close', 'Fermer')}
                style={{ position: 'absolute', top: 14, right: 14, background: 'none',
                         border: 'none', cursor: 'pointer', color: 'var(--gray-400)' }}>
                <X size={18} />
              </button>
            )}

            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
              <LifeBuoy size={20} color="var(--blue)" strokeWidth={2.2} />
              <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0 }}>
                {t('support.title', 'Aide & support')}
              </h2>
            </div>
            <p style={{ fontSize: '13px', color: 'var(--gray-500)', margin: '0 0 18px' }}>
              {t('support.subtitle', 'Un souci, une question sur votre offre ? Écrivez-nous.')}
            </p>

            <form onSubmit={submit}>
              {/* Catégorie */}
              <div style={{ display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap' }}>
                {cats.map((c) => (
                  <button key={c.key} type="button" onClick={() => setCategory(c.key)}
                    style={{
                      flex: '1 1 auto', padding: '8px 10px', borderRadius: '9px',
                      border: `1.5px solid ${category === c.key ? 'var(--blue)' : 'var(--gray-200)'}`,
                      background: category === c.key ? 'var(--blue-light, #eff6ff)' : 'white',
                      color: category === c.key ? 'var(--blue)' : 'var(--gray-600)',
                      fontWeight: 600, fontSize: '12.5px', cursor: 'pointer',
                      fontFamily: 'inherit', whiteSpace: 'nowrap',
                    }}>
                    {c.label}
                  </button>
                ))}
              </div>

              <input
                value={subject} onChange={(e) => setSubject(e.target.value)}
                placeholder={t('support.subject_ph', 'Sujet')} maxLength={200}
                required style={{ ...field, marginBottom: 12 }}
              />
              <textarea
                value={message} onChange={(e) => setMessage(e.target.value)}
                placeholder={t('support.message_ph', 'Décrivez votre demande…')}
                required maxLength={5000} rows={5}
                style={{ ...field, resize: 'vertical', minHeight: 110 }}
              />

              <button type="submit" disabled={sending || !subject.trim() || !message.trim()}
                style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                         gap: 8, padding: '12px', marginTop: 16, borderRadius: '10px', border: 'none',
                         background: 'var(--blue)', color: 'white', fontWeight: 600, fontSize: '14.5px',
                         cursor: sending ? 'default' : 'pointer', fontFamily: 'inherit',
                         opacity: sending || !subject.trim() || !message.trim() ? 0.6 : 1 }}>
                {sending
                  ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
                  : <Send size={16} />}
                {t('support.send', 'Envoyer')}
              </button>
            </form>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
