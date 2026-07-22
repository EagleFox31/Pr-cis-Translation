/**
 * Bouton carré ne portant qu'une icône (fermer, supprimer, …).
 *
 * `label` est OBLIGATOIRE : une icône seule n'a pas de nom accessible, et un
 * lecteur d'écran annonce « bouton », rien de plus. Il sert d'`aria-label` et
 * d'infobulle — un seul mot à écrire, les deux besoins couverts.
 */
import type { ButtonHTMLAttributes, ReactNode } from 'react';

interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'> {
  label: string;
  variant?: 'neutral' | 'ghost' | 'danger';
  size?: 'sm' | 'md';
  children: ReactNode;
}

export default function IconButton({
  label, variant = 'neutral', size = 'md', children, className, ...rest
}: IconButtonProps) {
  const classes = [
    'ui-iconbtn', `ui-iconbtn--${variant}`, `ui-iconbtn--${size}`, className ?? '',
  ].filter(Boolean).join(' ');

  return (
    <button className={classes} aria-label={label} title={label} {...rest}>
      {children}
    </button>
  );
}
