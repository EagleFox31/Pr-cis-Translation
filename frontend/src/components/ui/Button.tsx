/**
 * Bouton — LA primitive. Toutes les variantes de l'application passent par là.
 *
 * POURQUOI DES CLASSES ET NON DES STYLES EN LIGNE
 * ----------------------------------------------
 * Un style en ligne ne sait pas exprimer `:hover`, `:focus-visible` ni
 * `:disabled`. Le code les simulait donc en mutant le DOM à la main :
 *
 *     onMouseEnter={e => { e.currentTarget.style.color = '#dc2626'; … }}
 *     onMouseLeave={e => { e.currentTarget.style.color = 'var(--gray-500)'; … }}
 *
 * Trois lignes par bouton, à maintenir en double, et rien au clavier : un
 * utilisateur qui tabule ne voyait aucun état. Les états vivent maintenant dans
 * `index.css` (bloc « Primitives d'interface »), où le navigateur les gère.
 */
import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { Loader2 } from 'lucide-react';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Occupe toute la largeur disponible. */
  block?: boolean;
  /** Affiche un indicateur et désactive le bouton — sans changer sa largeur. */
  loading?: boolean;
  /** Icône à gauche du libellé. */
  icon?: ReactNode;
  children?: ReactNode;
}

export default function Button({
  variant = 'primary', size = 'md', block, loading, icon,
  children, className, disabled, ...rest
}: ButtonProps) {
  const classes = [
    'ui-btn', `ui-btn--${variant}`, `ui-btn--${size}`,
    block ? 'ui-btn--block' : '',
    className ?? '',
  ].filter(Boolean).join(' ');

  return (
    <button className={classes} disabled={disabled || loading} {...rest}>
      {loading
        ? <Loader2 size={15} strokeWidth={2.4} className="ui-spin" aria-hidden />
        : icon}
      {children}
    </button>
  );
}
