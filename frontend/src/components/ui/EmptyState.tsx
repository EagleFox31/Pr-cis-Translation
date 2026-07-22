/**
 * État vide : une icône, une phrase, et — si quelque chose peut être fait — une
 * action.
 *
 * Un écran vide sans issue laisse l'utilisateur deviner. Quand il y a un geste
 * possible (se connecter, déposer un fichier), il est ici, pas ailleurs.
 */
import type { ReactNode } from 'react';
import { motion } from 'motion/react';

interface EmptyStateProps {
  icon: ReactNode;
  title?: string;
  message: string;
  action?: ReactNode;
}

export default function EmptyState({ icon, title, message, action }: EmptyStateProps) {
  return (
    <motion.div
      className="ui-empty"
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <span className="ui-empty__icone" aria-hidden>{icon}</span>
      {title && <p className="ui-empty__titre">{title}</p>}
      <p className="ui-empty__texte">{message}</p>
      {action}
    </motion.div>
  );
}
