/**
 * Bandeau de message : erreur, information, succès.
 *
 * Le même bloc de sept propriétés en ligne était recopié dans les quatre pages
 * d'authentification, avec des couleurs légèrement différentes à chaque fois.
 *
 * `role="alert"` sur l'erreur : un message qui apparaît après un envoi de
 * formulaire n'est PAS lu par un lecteur d'écran si rien ne le signale. Une
 * personne aveugle voyait donc son formulaire ne rien faire.
 */
import type { ReactNode } from 'react';

interface AlertProps {
  tone?: 'error' | 'info' | 'success';
  children: ReactNode;
}

export default function Alert({ tone = 'error', children }: AlertProps) {
  return (
    <div
      className={`ui-alerte ui-alerte--${tone}`}
      role={tone === 'error' ? 'alert' : 'status'}
    >
      {children}
    </div>
  );
}
