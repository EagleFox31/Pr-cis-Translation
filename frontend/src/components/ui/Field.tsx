/**
 * Champ de formulaire : étiquette, icône, saisie — et son état de focus en CSS.
 *
 * Les pages d'authentification portaient ce bloc SIX fois, à l'identique, avec
 * le focus simulé à la main :
 *
 *     const focusIn  = e => { e.target.style.borderColor = 'var(--blue)'; … };
 *     const focusOut = e => { e.target.style.borderColor = 'var(--gray-200)'; … };
 *
 * Déclaré deux fois (Login et Register), passé à chaque `<input>`. Le
 * navigateur sait faire `:focus` ; il fallait juste lui laisser la main.
 *
 * `label` est relié à l'`<input>` par `htmlFor`/`id` : cliquer sur l'étiquette
 * place le curseur dans le champ, et un lecteur d'écran annonce le bon nom.
 */
import { useId } from 'react';
import type { InputHTMLAttributes, ReactNode } from 'react';

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  icon?: ReactNode;
  /** Affiché à droite de l'étiquette — « Mot de passe oublié ? », « (optionnel) ». */
  aside?: ReactNode;
  /** Précision sous le champ. */
  hint?: string;
}

export default function Field({ label, icon, aside, hint, id, ...rest }: FieldProps) {
  const genere = useId();
  const champId = id ?? genere;

  return (
    <div className="champ">
      <div className="champ__entete">
        <label className="champ__label" htmlFor={champId}>{label}</label>
        {aside}
      </div>
      <div className="champ__boite">
        {icon && <span className="champ__icone" aria-hidden>{icon}</span>}
        <input
          id={champId}
          className={`champ__saisie${icon ? ' champ__saisie--avec-icone' : ''}`}
          {...rest}
        />
      </div>
      {hint && <p className="champ__aide">{hint}</p>}
    </div>
  );
}
