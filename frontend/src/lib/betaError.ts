import type { TFunction } from 'i18next';

/** Translate a beta refusal from its stable server code; unknown codes get the generic message. */
export function betaError(t: TFunction, data: unknown): string {
  const detail = (data as { detail?: { code?: unknown } } | null)?.detail;
  const code = typeof detail === 'object' && detail ? detail.code : undefined;
  return typeof code === 'string'
    ? t(`beta.errors.${code}`, { defaultValue: t('beta.error') })
    : t('beta.error');
}
