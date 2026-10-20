import { useTranslation } from 'react-i18next';
import type { BetaEnrollment, BetaFormat } from '../../hooks/useBeta';

export const BETA_FORMATS: BetaFormat[] = ['pdf', 'pptx', 'docx', 'xlsx'];

export default function BetaAllowances({ enrollment }: { enrollment: BetaEnrollment }) {
  const { t } = useTranslation();
  return (
    <div className="beta-allowances">
      {BETA_FORMATS.map(format => {
        const quota = enrollment.formats[format];
        return (
          <div className="beta-allowance" key={format}>
            <strong>{t(`beta.formats.${format}`)}</strong>
            <span>{quota.remaining.toLocaleString()} / {quota.limit.toLocaleString()} {t(`beta.units.${quota.unit}`)}</span>
            <progress max={Math.max(1, quota.limit)} value={quota.remaining}
              aria-label={t('beta.remaining_for', { format: t(`beta.formats.${format}`) })} />
            {format === 'xlsx' && (
              <small>{t('beta.excel_words', {
                remaining: quota.words_remaining?.toLocaleString(),
                limit: quota.word_limit?.toLocaleString(),
              })}</small>
            )}
          </div>
        );
      })}
    </div>
  );
}
