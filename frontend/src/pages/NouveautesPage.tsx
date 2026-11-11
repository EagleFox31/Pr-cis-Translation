import { Fragment, useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ChevronDown, Columns2, FileText, Puzzle, User, type LucideIcon } from 'lucide-react';

import AppBar from '../components/navbar/AppBar';
import Button from '../components/ui/Button';
import Skeleton from '../components/ui/Skeleton';
import { useAuth } from '../contexts/AuthContext';
import api from '../services/api';
import '../nouveautes.css';

type Type = 'nouveaute' | 'amelioration' | 'correctif';
type Domaine = 'documents' | 'visionneuse' | 'extension' | 'compte';

interface Entree {
  id: string;
  date: string;
  type: Type;
  domaine: Domaine;
  titre: string;
  resume: string;
  detail: string;
}
interface Catalogue { version: string; date_version: string; elements: Entree[] }

// Ordre d'affichage et ancres (celles de la maquette : /fonctionnalites#ameliorations-compte).
const TYPES: ReadonlyArray<{ type: Type; ancre: string }> = [
  { type: 'nouveaute', ancre: 'fonctionnalites' },
  { type: 'amelioration', ancre: 'ameliorations' },
  { type: 'correctif', ancre: 'correctifs' },
];
const DOMAINES: ReadonlyArray<{ domaine: Domaine; Icone: LucideIcon }> = [
  { domaine: 'documents', Icone: FileText },
  { domaine: 'visionneuse', Icone: Columns2 },
  { domaine: 'extension', Icone: Puzzle },
  { domaine: 'compte', Icone: User },
];

type Etat = 'chargement' | 'ok' | 'erreur';

// Midi : évite qu'un fuseau horaire recule la date d'un jour.
const jour = (iso: string) => new Date(`${iso}T12:00:00`);

export default function NouveautesPage() {
  const { t, i18n } = useTranslation();
  const { user, loading: authLoading, refreshUser } = useAuth();
  const lang = (i18n.language || 'fr').startsWith('en') ? 'en' : 'fr';

  const [etat, setEtat] = useState<Etat>('chargement');
  const [data, setData] = useState<Catalogue | null>(null);
  const [essai, setEssai] = useState(0);
  const [actif, setActif] = useState('');

  const [abonne, setAbonne] = useState(false);
  const [envoi, setEnvoi] = useState(false);
  const [erreurAbo, setErreurAbo] = useState(false);
  const cibleRef = useRef(decodeURIComponent(window.location.hash.slice(1)));

  useEffect(() => { document.title = t('nouveautes.page_title'); }, [t, i18n.language]);
  useEffect(() => { setAbonne(!!user?.abonne_nouveautes); }, [user?.abonne_nouveautes]);

  useEffect(() => {
    let annule = false;
    setEtat('chargement');
    (async () => {
      try {
        const res = await api.get(`/api/nouveautes?lang=${lang}`);
        if (annule) return;
        if (res.ok) { setData(res.data as Catalogue); setEtat('ok'); } else setEtat('erreur');
      } catch {
        if (!annule) setEtat('erreur');
      }
    })();
    return () => { annule = true; };
  }, [lang, essai]);

  // Groupes (type > domaine) non vides, dans l'ordre d'affichage.
  const groupes = TYPES.map(({ type, ancre }) => {
    const parType = (data?.elements ?? []).filter((e) => e.type === type);
    return {
      type, ancre, total: parType.length,
      domaines: DOMAINES
        .map(({ domaine, Icone }) => ({
          domaine, Icone, id: `${ancre}-${domaine}`,
          // Le plus récent d'abord.
          elements: parType.filter((e) => e.domaine === domaine).sort((a, b) => b.date.localeCompare(a.date)),
        }))
        .filter((d) => d.elements.length > 0),
    };
  }).filter((g) => g.total > 0);
  const premierDomaine = groupes[0]?.domaines[0]?.id ?? '';

  // Une fois la liste affichée : rejoint l'ancre de l'adresse, sinon suit le défilement.
  useEffect(() => {
    if (etat !== 'ok') return;
    setActif(premierDomaine);
    if (cibleRef.current) {
      document.getElementById(cibleRef.current)?.scrollIntoView();
      cibleRef.current = '';
    }
    const zones = document.querySelectorAll<HTMLElement>('.nv-domain');
    const io = new IntersectionObserver((es) => {
      es.forEach((e) => { if (e.isIntersecting) setActif((e.target as HTMLElement).id); });
    }, { rootMargin: '-90px 0px -70% 0px' });
    zones.forEach((z) => io.observe(z));
    return () => io.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [etat, data]);

  const basculer = useCallback(async () => {
    if (envoi) return;
    const cible = !abonne;
    setEnvoi(true);
    setErreurAbo(false);
    setAbonne(cible);
    try {
      const res = await api.put('/api/nouveautes/abonnement', { actif: cible, langue: lang });
      if (!res.ok) throw new Error(String(res.status));
      await refreshUser();
    } catch {
      setAbonne(!cible);
      setErreurAbo(true);
    } finally {
      setEnvoi(false);
    }
  }, [abonne, envoi, lang, refreshUser]);

  const groupeActif = actif.split('-')[0];
  const date = (iso: string, opts: Intl.DateTimeFormatOptions) => jour(iso).toLocaleDateString(lang, opts);

  const abonnement = authLoading ? <div className="nv-sub" /> : user ? (
    <div className="nv-sub">
      <label id="nv-lab-sub">{t('nouveautes.subscribe.label')}<small>{t('nouveautes.subscribe.hint')}</small></label>
      <button
        type="button" role="switch" className="nv-switch" aria-checked={abonne}
        aria-labelledby="nv-lab-sub" disabled={envoi} onClick={basculer}
      />
      {erreurAbo && <p className="nv-sub__err" role="alert">{t('nouveautes.subscribe.error')}</p>}
    </div>
  ) : (
    <div className="nv-sub">
      <Link to="/login" className="nv-sub__login">{t('nouveautes.subscribe.login')}</Link>
    </div>
  );

  return (
    <div className="nv-page">
      <AppBar exit />
      <main className="nv-wrap">
        <header className="nv-head">
          <div className="nv-head__line">
            <h1>{t('nouveautes.title')}</h1>
            {data && etat === 'ok' && (
              <span className="nv-head__ver">
                {t('nouveautes.version', { version: data.version })}
                {' · '}
                <time dateTime={data.date_version}>
                  {date(data.date_version, { day: 'numeric', month: 'long', year: 'numeric' })}
                </time>
              </span>
            )}
          </div>
          <p>{t('nouveautes.lead')}</p>
        </header>

        {etat === 'chargement' && (
          <div className="nv-skel" role="status" aria-busy="true" aria-label={t('nouveautes.loading')}>
            <Skeleton height="28px" width="40%" />
            <Skeleton height="64px" />
            <Skeleton height="64px" />
            <Skeleton height="64px" />
          </div>
        )}

        {etat === 'erreur' && (
          <div className="nv-state" role="alert">
            <p>{t('nouveautes.error.text')}</p>
            <Button variant="secondary" onClick={() => setEssai((n) => n + 1)}>{t('nouveautes.error.retry')}</Button>
          </div>
        )}

        {etat === 'ok' && (
          <div className="nv-layout">
            <aside className="nv-side">
              <nav className="nv-toc" aria-label={t('nouveautes.toc_label')}>
                {groupes.map((g) => (
                  <Fragment key={g.ancre}>
                    <a
                      href={`#${g.ancre}`} className={g.ancre === groupeActif ? 'on' : undefined}
                      aria-current={g.ancre === groupeActif ? 'true' : undefined}
                    >
                      {t(`nouveautes.types.${g.type}.title`)}
                      <span className={`nv-badge nv-badge--${g.type}`}>{g.total}</span>
                    </a>
                    <ul className="nv-doms">
                      {g.domaines.map((d) => (
                        <li key={d.id}>
                          <a href={`#${d.id}`} className={d.id === actif ? 'on' : undefined}>
                            {t(`nouveautes.domains.${d.domaine}`)}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </Fragment>
                ))}
              </nav>
              {abonnement}
            </aside>

            <div className="nv-col">
              {groupes.map((g) => (
                <section key={g.ancre} aria-labelledby={g.ancre}>
                  <h2 id={g.ancre}>{t(`nouveautes.types.${g.type}.title`)}</h2>
                  <p>{t(`nouveautes.types.${g.type}.intro`)}</p>
                  {g.domaines.map((d) => (
                    <div className="nv-domain" id={d.id} key={d.id}>
                      <h3>
                        <d.Icone size={16} aria-hidden="true" />
                        {t(`nouveautes.domains.${d.domaine}`)}
                      </h3>
                      <div className="nv-list">
                        {d.elements.map((e) => (
                          <details key={e.id} id={e.id} open={d.id === premierDomaine && e === d.elements[0] ? true : undefined}>
                            <summary>
                              <strong>{e.titre}</strong>
                              <time dateTime={e.date}>{date(e.date, { month: 'short', year: 'numeric' })}</time>
                              <span className="nv-sum">{e.resume}</span>
                              <span className="nv-chev"><ChevronDown size={18} aria-hidden="true" /></span>
                            </summary>
                            <div className="nv-more"><p>{e.detail}</p></div>
                          </details>
                        ))}
                      </div>
                    </div>
                  ))}
                </section>
              ))}
            </div>
          </div>
        )}
      </main>
      <footer className="nv-foot">
        <div>
          <span>{t('footer.rights')}</span>
          <Link to="/mentions-legales">{t('footer.legal')}</Link>
          <Link to="/confidentialite">{t('footer.privacy')}</Link>
          <Link to="/fonctionnalites" aria-current="page">{t('nouveautes.footer_link')}</Link>
        </div>
      </footer>
    </div>
  );
}
