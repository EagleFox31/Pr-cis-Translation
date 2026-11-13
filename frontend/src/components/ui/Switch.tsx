import './switch.css';

interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  size?: 'md' | 'sm';
  disabled?: boolean;
  'aria-labelledby'?: string;
  'aria-describedby'?: string;
}

/** Interrupteur accessible (role="switch"). */
export default function Switch({
  checked, onChange, size = 'md', disabled,
  'aria-labelledby': labelledBy, 'aria-describedby': describedBy,
}: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-labelledby={labelledBy}
      aria-describedby={describedBy}
      disabled={disabled}
      className={`ui-switch${size === 'sm' ? ' ui-switch--sm' : ''}`}
      onClick={() => onChange(!checked)}
    />
  );
}
