import { useTranslation } from 'react-i18next';

interface PlanToggleProps {
  isAnnual: boolean;
  onChange: (annual: boolean) => void;
}

export default function PlanToggle({ isAnnual, onChange }: PlanToggleProps) {
  const { t } = useTranslation();

  return (
    <div
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
        }}
      />
      <div
        onClick={() => onChange(false)}
        style={{
          flex: 1,
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
      </div>
      <div
        onClick={() => onChange(true)}
        style={{
          flex: 1,
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
      </div>
    </div>
  );
}
