import type { TFunction } from 'i18next';

/** Message d'une traduction : envoyé en direct pendant le travail, et gardé
 *  avec le document pour être relu en revenant par « Mes documents ».
 *  Le serveur garde les DONNÉES ; la phrase s'écrit ici, dans la langue de
 *  l'interface, avec UNE seule fonction pour les deux cas. */
export type Avis = { type?: unknown } & Record<string, unknown>;

const RAISONS_OBJETS = ['lie', 'visio', 'pdf', 'equation', 'paquet', 'absent',
  'conversion', 'erreur', 'profondeur', 'illisible', 'reinjection', 'hors_diapo'];

/** Diapos citées avant « … et N autres ». */
const DIAPOS_CITEES = 10;

type ObjetSignale = { cible?: string | null; raison?: string };

function phrasesObjets(avis: Avis, t: TFunction): string[] {
  const liste: ObjetSignale[] = Array.isArray(avis.non_traites) ? avis.non_traites : [];
  const nomDe = (o: ObjetSignale) => (o.cible
    ? String(o.cible).split(' › ').map((part) => part.split(/[\\/]/).pop() || part).join(' › ')
    : t('story.objects_report.sans_nom'));
  const resume = (noms: string[], total: number) => noms.join(', ')
    + (total > noms.length ? ' ' + t('story.objects_report.more', { count: total - noms.length }) : '');
  const apercus = liste.filter((o) => o.raison === 'apercu');
  const autres = liste.filter((o) => o.raison !== 'apercu');
  const phrases: string[] = [];
  if (autres.length) {
    const noms = autres.slice(0, 5).map((o) => {
      const raison = RAISONS_OBJETS.includes(String(o.raison)) ? String(o.raison) : 'autre';
      return `${nomDe(o)} (${t(`story.objects_report.raisons.${raison}`)})`;
    });
    phrases.push(t('story.objects_report.intro', { detail: resume(noms, autres.length) }));
  }
  if (apercus.length) {
    phrases.push(t('story.objects_report.apercus', {
      detail: resume(apercus.slice(0, 5).map(nomDe), apercus.length),
    }));
  }
  return phrases;
}

function phraseCoherence(avis: Avis, t: TFunction): string {
  const slides = (Array.isArray(avis.slides) ? avis.slides : [])
    .map(Number).filter((n) => Number.isInteger(n) && n > 0);
  if (!slides.length) return '';
  const cites = slides.slice(0, DIAPOS_CITEES).join(', ');
  const reste = slides.length - DIAPOS_CITEES;
  const detail = reste > 0 ? cites + t('story.coherence_report.more', { count: reste }) : cites;
  return t('story.coherence_report.intro', { count: slides.length, detail });
}

function phraseImages(avis: Avis, t: TFunction): string {
  const bilan = ['traduites', 'inchangees', 'sans_credit', 'echecs']
    .map((cle) => {
      const count = Number(avis[cle]) || 0;
      return count > 0 ? t(`story.images_report.${cle}`, { count }) : '';
    })
    .filter(Boolean)
    .join(', ');
  return bilan ? t('story.images_report.intro', { detail: bilan }) : '';
}

/** Phrases d'UN message ; type inconnu ou message vide : aucune.
 *  `relu` : message relu après coup (« Mes documents »), écrit au passé. */
export function phrasesAvis(avis: Avis, t: TFunction, relu = false): string[] {
  switch (avis.type) {
    case 'ocr': {
      const count = Number(avis.pages) || 0;
      return count > 0 ? [t(relu ? 'story.ocr_notice_done' : 'story.ocr_notice', { count })] : [];
    }
    case 'objets': return phrasesObjets(avis, t);
    case 'coherence': return [phraseCoherence(avis, t)].filter(Boolean);
    case 'images': return [phraseImages(avis, t)].filter(Boolean);
    default: return [];
  }
}

/** Tous les messages gardés avec un document, en un seul texte (ou null). */
export function texteAvis(liste: readonly Avis[] | null | undefined, t: TFunction): string | null {
  const phrases = (liste ?? []).flatMap((a) => phrasesAvis(a, t, true));
  return phrases.length ? phrases.join(' ') : null;
}

/** Types de message d'un flux de traduction que `phrasesAvis` sait écrire. */
export const TYPES_AVIS: readonly string[] = ['ocr', 'objets', 'coherence', 'images'];
