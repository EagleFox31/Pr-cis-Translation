import { useTranslation } from 'react-i18next';
import { FileTypeIcon } from '../admin/AdminParts';
import type { BetaEnrollment, BetaFormat } from '../../hooks/useBeta';

export const BETA_FORMATS: BetaFormat[] = ['pdf', 'pptx', 'docx', 'xlsx'];

export default function BetaAllowances({ enrollment, compact = false }: { enrollment: BetaEnrollment; compact?: boolean }) {
  const { t, i18n } = useTranslation();
  const left = (unit: string, remaining = 0, limit = 0) => t(`beta.left.${unit}`, {
    count: remaining,
    remaining: remaining.toLocaleString(i18n.language),
    limit: limit.toLocaleString(i18n.language),
  });
  const n = (value = 0) => value.toLocaleString(i18n.language);
  if (compact) return (
    <ul className="beta-allowances--compact">
      {BETA_FORMATS.map(format => {
        const quota = enrollment.formats[format];
        return (
          <li key={format} title={left(quota.unit, quota.remaining, quota.limit)}>
            <span role="img" aria-label={t(`beta.formats.${format}`)}><FileTypeIcon name={'.' + format} size={15} /></span>{n(quota.remaining)}/{n(quota.limit)}
          </li>
        );
      })}
    </ul>
  );
  return (
    <div className="beta-allowances">
      {BETA_FORMATS.map(format => {
        const quota = enrollment.formats[format];
        return (
          <div className="beta-allowance" key={format}>
            <strong>{t(`beta.formats.${format}`)}</strong>
            <span>{left(quota.unit, quota.remaining, quota.limit)}</span>
            <progress max={Math.max(1, quota.limit)} value={quota.remaining}
              aria-label={t('beta.remaining_for', { format: t(`beta.formats.${format}`) })} />
            {format === 'xlsx' && (
              <small>{left('words', quota.words_remaining, quota.word_limit)}</small>
            )}
          </div>
        );
      })}
    </div>
  );
}
