/**
 * L'étape « un code vient de partir vers votre boîte ».
 *
 * Elle servait à TROIS choses avec trois copies : valider une inscription,
 * ouvrir une session sans mot de passe, réinitialiser un mot de passe. Le
 * geste est le même — prouver qu'on relève cette boîte — donc l'écran l'est
 * aussi. Ce qui change (le titre, le libellé du bouton, un champ en plus) est
 * passé en propriété.
 */
import type { FormEvent, ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { ArrowRight, RefreshCw, MailCheck } from 'lucide-react';

import Alert from '../ui/Alert';
import Button from '../ui/Button';
import CodeInput from './CodeInput';

interface CodeStepProps {
  email: string;
  code: string[];
  onCodeChange: (code: string[]) => void;
  onSubmit: (e: FormEvent) => void;
  onResend: () => void;
  resent: boolean;
  busy: boolean;
  error?: string;
  info?: string;
  title: string;
  submitLabel: string;
  /** Champs supplémentaires — le nouveau mot de passe, par exemple. */
  children?: ReactNode;
}

export default function CodeStep({
  email, code, onCodeChange, onSubmit, onResend, resent, busy,
  error, info, title, submitLabel, children,
}: CodeStepProps) {
  const { t } = useTranslation();

  return (
    <>
      <div className="auth-etape">
        <span className="auth-etape__pastille" aria-hidden><MailCheck size={20} /></span>
        <h1 className="auth-titre">{title}</h1>
        <p className="auth-sous-titre">
          {t('auth.code_sent_to')} <strong>{email}</strong>
        </p>
      </div>

      <form onSubmit={onSubmit} className="auth-form">
        {error && <Alert tone="error">{error}</Alert>}
        {info && <Alert tone="info">{info}</Alert>}

        <CodeInput value={code} onChange={onCodeChange}
          label={t('auth.code_label')} autoFocus />

        {children}

        <Button type="submit" variant="primary" size="lg" block
          loading={busy} icon={<ArrowRight size={15} />}>
          {submitLabel}
        </Button>

        <button type="button" className="auth-lien-discret" onClick={onResend}>
          <RefreshCw size={13} className={resent ? 'ui-spin' : undefined} aria-hidden />
          {resent ? t('auth.code_resent') : t('auth.resend_code')}
        </button>
      </form>
    </>
  );
}
