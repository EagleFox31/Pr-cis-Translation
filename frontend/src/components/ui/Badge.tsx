interface BadgeProps {
  variant?: 'default' | 'success' | 'warning' | 'soon';
  children: React.ReactNode;
}

const styles: Record<string, React.CSSProperties> = {
  default: { background: '#dbeafe', color: '#1a4dc7', border: '1px solid #93c5fd' },
  success: { background: '#f0fdf4', color: '#15803d', border: '1px solid #bbf7d0' },
  warning: { background: '#fffbeb', color: '#b45309', border: '1px solid #fde68a' },
  soon: { background: '#f1f5f9', color: '#64748b', border: '1px solid #cbd5e1', fontSize: '10px' },
};

export default function Badge({ variant = 'default', children }: BadgeProps) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        padding: '3px 10px',
        borderRadius: '100px',
        fontSize: '11px',
        fontWeight: 600,
        letterSpacing: '0.02em',
        ...styles[variant],
      }}
    >
      {children}
    </span>
  );
}
