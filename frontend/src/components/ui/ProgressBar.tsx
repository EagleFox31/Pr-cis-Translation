/**
 * Barre de progression — quota de stockage, avancement d'une traduction.
 *
 * `value` est un pourcentage DÉJÀ borné (voir `lib/format.percent`). La barre ne
 * corrige rien : une valeur hors bornes est un défaut d'appelant, et la masquer
 * ici la rendrait invisible partout.
 */
interface ProgressBarProps {
  /** 0 à 100. */
  value: number;
  tone?: 'blue' | 'gold' | 'green' | 'danger';
  height?: number;
  /** Décrit ce que la barre mesure, pour les lecteurs d'écran. */
  label?: string;
}

export default function ProgressBar({
  value, tone = 'blue', height = 4, label,
}: ProgressBarProps) {
  return (
    <div
      className="ui-progress"
      style={{ height }}
      role="progressbar"
      aria-valuenow={Math.round(value)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
    >
      <div
        className={`ui-progress__barre ui-progress__barre--${tone}`}
        style={{ width: `${value}%` }}
      />
    </div>
  );
}
