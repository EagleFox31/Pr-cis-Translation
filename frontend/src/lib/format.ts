/**
 * Formatage des tailles et des dates — UN SEUL endroit.
 *
 * `DocumentLibrary` en portait DEUX, dans le même fichier : `formatSize()` qui
 * passait par i18next (« 12 Ko » / « 12 KB ») et `formatBytes()` qui écrivait
 * « Ko » et « Mo » en dur. Deux tailles affichées côte à côte dans la même
 * barre latérale, dans deux langues différentes selon l'endroit.
 *
 * Ce n'est pas de la cosmétique : c'est la preuve qu'un doublon finit toujours
 * par diverger. Une seule fonction, une seule source d'unités.
 */
import type { TFunction } from 'i18next';

const KO = 1024;
const MO = KO * 1024;
const GO = MO * 1024;

/**
 * Taille lisible, dans la langue de l'interface.
 *
 * Les unités viennent des locales (`units.b` … `units.gb`) : « Ko » en français,
 * « KB » en anglais. `units.gb` a été ajouté aux deux dictionnaires — l'ancien
 * `formatBytes` gérait le gigaoctet mais l'écrivait en dur, donc en français
 * quelle que soit la langue.
 */
export function formatSize(bytes: number, t: TFunction): string {
  if (!Number.isFinite(bytes) || bytes < 0) return `0 ${t('units.b')}`;
  if (bytes < KO) return `${bytes} ${t('units.b')}`;
  if (bytes < MO) return `${(bytes / KO).toFixed(0)} ${t('units.kb')}`;
  if (bytes < GO) return `${(bytes / MO).toFixed(0)} ${t('units.mb')}`;
  return `${(bytes / GO).toFixed(1)} ${t('units.gb')}`;
}

/** Date + heure courtes, dans la locale de l'interface. */
export function formatDate(iso: string, locale: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleDateString(locale, {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

/**
 * Date courte pour une ligne de liste : relative sous 24 h (« il y a 2 h »),
 * puis « 3 nov. », puis « 3 nov. 2025 » hors de l'année en cours.
 * `now` est le libellé de « à l'instant » (traduit par l'appelant) ; la date
 * complète reste disponible via `formatDate` pour l'infobulle.
 *
 * Les durées sont tronquées (jamais arrondies à l'unité supérieure) : 23 h 40
 * donne « il y a 23 heures », pas « il y a 24 heures » juste avant de basculer
 * sur la date.
 */
export function formatRelative(iso: string, locale: string, now: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  const ecart = Date.now() - d.getTime();
  if (ecart < 24 * 3600 * 1000) {
    const minutes = Math.floor(ecart / 60000);
    if (minutes < 1) return now;
    const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' });
    if (minutes < 60) return rtf.format(-minutes, 'minute');
    return rtf.format(-Math.floor(minutes / 60), 'hour');
  }
  const memeAnnee = d.getFullYear() === new Date().getFullYear();
  return d.toLocaleDateString(locale, memeAnnee
    ? { day: 'numeric', month: 'short' }
    : { day: 'numeric', month: 'short', year: 'numeric' });
}

/** Pourcentage borné à [0, 100] — jamais une barre qui déborde. */
export function percent(part: number, total: number): number {
  if (!total || total <= 0) return 0;
  return Math.min(100, Math.max(0, Math.round((part / total) * 100)));
}
