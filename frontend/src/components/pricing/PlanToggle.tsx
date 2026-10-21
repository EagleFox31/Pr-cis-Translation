import { useTranslation } from 'react-i18next';

interface PlanToggleProps {
  isAnnual: boolean;
  onChange: (annual: boolean) => void;
}

export default function PlanToggle({ isAnnual, onChange }: PlanToggleProps) {
  const { t } = useTranslation();

  return (
    <div
      role="group"
      aria-label={`${t('pricing.monthly')} / ${t('pricing.annual')}`}
      style={{
        display: 'flex',
        background: 'var(--gray-100)',
        borderRadius: '30px',
        padding: '4px',
        position: 'relative',
        cursor: 'pointer',
        minWidth: '250px',
      }}
    >
      <div
        style={{
          position: 'absolute',
          top: '4px',
          left: isAnnual ? '50%' : '4px',
          width: 'calc(50% - 4px)',
          height: 'calc(100% - 8px)',
          background: 'white',
          borderRadius: '25px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
          transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
          zIndex: 1,
          pointerEvents: 'none',
        }}
      />
      <button
        type="button"
        aria-pressed={!isAnnual}
        onClick={() => onChange(false)}
        style={{
          flex: 1,
          border: 0,
          borderRadius: '26px',
          background: 'transparent',
          cursor: 'pointer',
          fontFamily: 'inherit',
          textAlign: 'center',
          padding: '8px 16px',
          fontSize: '13px',
          fontWeight: !isAnnual ? 600 : 500,
          color: !isAnnual ? 'var(--navy)' : 'var(--gray-500)',
          position: 'relative',
          zIndex: 2,
          transition: 'color 0.3s',
          whiteSpace: 'nowrap',
        }}
      >
        {t('pricing.monthly')}
      </button>
      <button
        type="button"
        aria-pressed={isAnnual}
        onClick={() => onChange(true)}
        style={{
          flex: 1,
          border: 0,
          borderRadius: '26px',
          background: 'transparent',
          cursor: 'pointer',
          fontFamily: 'inherit',
          textAlign: 'center',
          padding: '8px 16px',
          fontSize: '13px',
          fontWeight: isAnnual ? 600 : 500,
          color: isAnnual ? 'var(--navy)' : 'var(--gray-500)',
          position: 'relative',
          zIndex: 2,
          transition: 'color 0.3s',
          whiteSpace: 'nowrap',
        }}
      >
        {t('pricing.annual')}{' '}
        <span style={{ color: '#1a4dc7', fontSize: '11px', fontWeight: 700 }}>
          {t('pricing.discount')}
        </span>
      </button>
    </div>
  );
}
