/**
 * Option à cocher : icône, intitulé, explication — et la case elle-même.
 *
 * Le bloc existait deux fois dans `TranslationSection`, à trente-cinq lignes
 * pièce, identique à la couleur près. La seule vraie différence entre « mode
 * précis » et « mode structure » était le TON : le premier se met en évidence
 * quand il est actif, le second reste discret.
 *
 * L'étiquette enveloppe la case : cliquer n'importe où dans le bloc — titre,
 * description, marge — coche l'option. Une case de 16 px est une cible
 * difficile, en particulier au doigt.
 */
import type { ReactNode } from 'react';

interface CheckboxOptionProps {
  id: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  icon?: ReactNode;
  label: string;
  description?: string;
  /** `highlight` : le bloc s'allume quand l'option est active. */
  tone?: 'plain' | 'highlight';
}

export default function CheckboxOption({
  id, checked, onChange, disabled, icon, label, description, tone = 'plain',
}: CheckboxOptionProps) {
  const actif = tone === 'highlight' && checked;

  return (
    <label
      htmlFor={id}
      className={`option${actif ? ' option--allumee' : ''}${disabled ? ' option--inactive' : ''}`}
    >
      <input
        id={id}
        type="checkbox"
        className={`option__case option__case--${tone}`}
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="option__texte">
        <span className="option__intitule">
          {icon}
          {label}
        </span>
        {description && <span className="option__desc">{description}</span>}
      </span>
    </label>
  );
}
