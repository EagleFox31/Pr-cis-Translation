import { useTranslation } from 'react-i18next';
import type { BetaProgram } from '../../hooks/useBetaProgram';

export default function BetaProgramDetails({ program, heading: Heading = 'h3' }: {
  program: BetaProgram; heading?: 'h2' | 'h3';
}) {
  const { t, i18n } = useTranslation();
  const number = (value: number) => value.toLocaleString(i18n.language);
  return <>
    <div className="beta-heading">
      <span className="section-tag">{t('beta.public.tag')}</span>
      <span className="beta-status">{t(`beta.public.availability.${program.availability}`)}</span>
    </div>
    <Heading>{t('beta.public.title', { days: program.access_days })}</Heading>
    <p>{t('beta.public.description', { capacity: program.capacity })}</p>
    <ul className="beta-program-quotas" aria-label={t('beta.default_limits')}>
      <li><strong>PDF</strong><span>{number(program.limits.pdf)} {t('beta.units.pages')}</span></li>
      <li><strong>PowerPoint</strong><span>{number(program.limits.pptx)} {t('beta.units.slides')}</span></li>
      <li><strong>Word</strong><span>{number(program.limits.docx)} {t('beta.units.words')}</span></li>
      <li><strong>Excel</strong><span>{t('beta.public.excel', {
        sheets: number(program.limits.xlsx), words: number(program.limits.xlsx_words),
      })}</span></li>
    </ul>
    <p className="beta-note">{t('beta.public.conditions')}</p>
    {!program.applications_open && <p className="beta-note">{t(`beta.public.closed_hint.${program.availability}`)}</p>}
  </>;
}
