import { Fragment, useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Check, Columns2, FileText, History, Mail, Puzzle, User, X, type LucideIcon } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import {
  useNouveautes,
  type AVoir, type DomaineNouveaute, type ElementNouveaute, type TypeNouveaute,
} from '../../hooks/useNouveautes';
import '../ui/switch.css';
import './modal.css';

interface Props {
  donnees: AVoir;
  /** Ferme la fenêtre (= « vu »). `false` : ne pas rendre le focus (on quitte l'écran). */
  onClose: (restaurerFocus?: boolean) => void;
}

const TYPES: ReadonlyArray<{ type: TypeNouveaute; ancre: string }> = [
  { type: 'nouveaute', ancre: 'fonctionnalites' },
  { type: 'amelioration', ancre: 'ameliorations' },
  { type: 'correctif', ancre: 'correctifs' },
];

const DOMAINES: ReadonlyArray<{ domaine: DomaineNouveaute; Icone: LucideIcon }> = [
  { domaine: 'documents', Icone: FileText },
  { domaine: 'visionneuse', Icone: Columns2 },
  { domaine: 'extension', Icone: Puzzle },
  { domaine: 'compte', Icone: User },
];

// Midi : évite qu'un fuseau horaire recule la date d'un jour.
const jour = (iso: string) => new Date(`${iso.slice(0, 10)}T12:00:00`);

/** Fenêtre « depuis votre dernière visite » : ce qui a changé, par type. */
export default function DepuisModal({ donnees, onClose }: Props) {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const { setAbonnement } = useNouveautes();
  const navigate = useNavigate();
  const lang = i18n.language.startsWith('en') ? 'en' : 'fr';
  const uid = useId();

  // Onglets : seuls ceux qui contiennent quelque chose.
  const onglets = useMemo(() => TYPES
    .map((ty) => ({ ...ty, elements: donnees.elements.filter((e) => e.type === ty.type) }))
    .filter((o) => o.elements.length > 0), [donnees]);

  const [actif, setActif] = useState(0);
  const refsOnglets = useRef<Array<HTMLButtonElement | null>>([]);

  // Abonnement : ligne cochée, puis remplacée par la confirmation.
  const [ligne, setLigne] = useState<'ligne' | 'fait'>('ligne');
  const [coche, setCoche] = useState(false);
  const doneRef = useRef<HTMLParagraphElement>(null);
  const monte = useRef(true);
  useEffect(() => () => { monte.current = false; }, []);

  const choisir = (i: number, focus: boolean) => {
    setActif(i);
    if (focus) refsOnglets.current[i]?.focus();
  };

  const clavier = (e: KeyboardEvent, i: number) => {
    const n = onglets.length;
    const j = ({ ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: n - 1 } as Record<string, number>)[e.key];
    if (j === undefined) return;
    e.preventDefault();
    choisir((j + n) % n, true);
  };

  const sAbonner = async () => {
    if (coche) return;
    setCoche(true);
    const [ok] = await Promise.all([
      setAbonnement(true),
      new Promise((r) => window.setTimeout(r, 260)),
    ]);
    if (!monte.current) return;
    if (!ok) { setCoche(false); return; }
    setLigne('fait');
    window.requestAnimationFrame(() => doneRef.current?.focus());
  };

  const voirTout = (e: React.MouseEvent) => {
    e.preventDefault();
    onClose(false);
    navigate(`/fonctionnalites#${onglets[actif]?.ancre ?? TYPES[0].ancre}`);
  };

  const dateDepuis = donnees.depuis
    ? new Date(donnees.depuis).toLocaleDateString(lang, { day: 'numeric', month: 'long', year: 'numeric' })
    : '';
  const dateCourte = (iso: string) => jour(iso).toLocaleDateString(lang, { month: 'short', year: 'numeric' });
  const abonnable = !!user && !user.abonne_nouveautes;
  const ancreActive = onglets[actif]?.ancre ?? TYPES[0].ancre;

  return (
    <div className="nvd" role="dialog" aria-modal="true" tabIndex={-1} aria-labelledby={`${uid}-t`}>
      <button type="button" className="nvd__x" aria-label={t('nouveautes.depuis.close')} onClick={() => onClose()}>
        <X size={18} aria-hidden="true" />
      </button>
      <div className="nvd__head">
        <History size={20} aria-hidden="true" />
        <h2 id={`${uid}-t`}>{t('nouveautes.depuis.title')}</h2>
      </div>
      <p className="nvd__sub">
        {t('nouveautes.depuis.sub', { count: donnees.elements.length, date: dateDepuis })}
      </p>

      <div className="nvd-seg" role="tablist" aria-label={t('nouveautes.depuis.tabs_label')}>
        {onglets.map((o, i) => (
          <button
            key={o.type}
            ref={(el) => { refsOnglets.current[i] = el; }}
            type="button"
            role="tab"
            id={`${uid}-tab-${o.type}`}
            aria-selected={i === actif}
            aria-controls={`${uid}-pan-${o.type}`}
            tabIndex={i === actif ? 0 : -1}
            onClick={() => choisir(i, false)}
            onKeyDown={(e) => clavier(e, i)}
          >
            {t(`nouveautes.depuis.tabs.${o.type}`)}
            <span className={`nvd-badge nvd-badge--${o.type}`} aria-label={t('nouveautes.depuis.count', { count: o.elements.length })}>
              {o.elements.length}
            </span>
          </button>
        ))}
      </div>

      <div className="nvd-panes">
        {onglets.map((o, i) => (
          <div
            key={o.type}
            role="tabpanel"
            id={`${uid}-pan-${o.type}`}
            aria-labelledby={`${uid}-tab-${o.type}`}
            tabIndex={0}
            hidden={i !== actif}
          >
            {DOMAINES.map(({ domaine, Icone }) => {
              const liste: ElementNouveaute[] = o.elements.filter((e) => e.domaine === domaine);
              if (liste.length === 0) return null;
              return (
                <Fragment key={domaine}>
                  <p className="nvd-dom"><Icone size={15} aria-hidden="true" />{t(`nouveautes.domains.${domaine}`)}</p>
                  <ul>
                    {liste.map((e) => (
                      <li key={e.id}>
                        <b>{e.titre}</b>
                        <time dateTime={e.date}>{dateCourte(e.date)}</time>
                        <span>{e.resume}</span>
                      </li>
                    ))}
                  </ul>
                </Fragment>
              );
            })}
          </div>
        ))}
      </div>

      {abonnable && (
        <div className="nvd-optin" aria-live="polite">
          {ligne === 'ligne' ? (
            <button
              type="button"
              role="switch"
              className="nvd-optin__row"
              aria-checked={coche}
              aria-labelledby={`${uid}-oi-l`}
              aria-describedby={`${uid}-oi-h`}
              onClick={sAbonner}
            >
              <Mail size={20} aria-hidden="true" />
              <span className="nvd-optin__txt">
                <b id={`${uid}-oi-l`}>{t('nouveautes.depuis.optin')}</b>
                <small id={`${uid}-oi-h`}>{t('nouveautes.depuis.optin_hint')}</small>
              </span>
              <span className="ui-switch" aria-hidden="true" />
            </button>
          ) : (
            <p className="nvd-optin__done" ref={doneRef} tabIndex={-1}>
              <Check size={18} aria-hidden="true" />{t('nouveautes.depuis.optin_done')}
            </p>
          )}
        </div>
      )}

      <a className="nvd-cta" href={`/fonctionnalites#${ancreActive}`} onClick={voirTout}>
        {t('nouveautes.depuis.cta')} <ArrowRight size={16} aria-hidden="true" />
      </a>
    </div>
  );
}
