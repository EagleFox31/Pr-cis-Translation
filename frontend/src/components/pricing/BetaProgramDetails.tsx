import { useTranslation } from 'react-i18next';
import type { BetaProgram } from '../../hooks/useBetaProgram';

type Format = 'pdf' | 'pptx' | 'docx' | 'xlsx';

function FormatIcon({ format }: { format: Format }) {
  const label = { pdf: 'PDF', pptx: 'P', docx: 'W', xlsx: 'X' }[format];
  return (
    <svg className={'beta-format-icon beta-format-icon--' + format}
      viewBox="0 0 40 44" aria-hidden="true" focusable="false">
      <path d="M12 2h14l10 10v26a4 4 0 0 1-4 4H12a4 4 0 0 1-4-4V6a4 4 0 0 1 4-4Z"
        fill="currentColor" opacity=".12" />
      <path d="M26 2v8a2 2 0 0 0 2 2h8" fill="none"
        stroke="currentColor" strokeWidth="1.5" opacity=".45" />
      <rect x="1" y="14" width="29" height="25" rx="5" fill="currentColor" />
      <text x="15.5" y="31" textAnchor="middle" fill="#fff"
        fontFamily="Arial, sans-serif" fontWeight="700" fontSize={format === 'pdf' ? 10 : 17}>
        {label}
      </text>
    </svg>
  );
}

export default function BetaProgramDetails({ program, heading: Heading = 'h3' }: {
  program: BetaProgram; heading?: 'h2' | 'h3';
}) {
  const { t, i18n } = useTranslation();
  const number = (value: number) => value.toLocaleString(i18n.language);
  const formats = [
    { key: 'pdf', label: 'PDF', allowance: number(program.limits.pdf) + ' ' + t('beta.units.pages') },
    { key: 'pptx', label: 'PowerPoint', allowance: number(program.limits.pptx) + ' ' + t('beta.units.slides') },
    { key: 'docx', label: 'Word', allowance: number(program.limits.docx) + ' ' + t('beta.units.words') },
    { key: 'xlsx', label: 'Excel', allowance: t('beta.public.excel', {
      sheets: number(program.limits.xlsx), words: number(program.limits.xlsx_words),
    }) },
  ] as const;

  return <>
    <span className="beta-program-tag">{t('beta.public.tag')}</span>
    <Heading className="beta-program-title">{t('beta.public.title', { days: program.access_days })}</Heading>
    <p className="beta-program-description">{t('beta.public.description')}</p>
    <ul className="beta-program-quotas" aria-label={t('beta.default_limits')}>
      {formats.map(format => (
        <li key={format.key}>
          <FormatIcon format={format.key} />
          <div className="beta-format-copy">
            <strong>{format.label}</strong>
            <span>{format.allowance}</span>
          </div>
        </li>
      ))}
    </ul>
    {!program.applications_open && (
      <p className="beta-program-status" role="status">{t(`beta.public.availability.${program.availability}`)}</p>
    )}
  </>;
}
