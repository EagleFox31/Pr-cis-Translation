import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import { X, ArrowLeft, ArrowRight, Mail, Sparkles, TrendingUp, Wrench } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { useNouveautes } from '../../hooks/useNouveautes';
import { goToSection } from '../../lib/sectionBus';
import VisiteScenes from './visiteScenes';
import { useVisite } from './useVisite';
import { ETAPES, IC, SEQ } from './visiteData';
import './visite.css';

interface Props {
  /** Ferme la visite (= « vu »). `false` : ne pas rendre le focus (on quitte l'écran). */
  onClose: (restaurerFocus?: boolean) => void;
}

const icone = (n: string) => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
    dangerouslySetInnerHTML={{ __html: IC[n] }} />
);

/** Visite d'accueil en cinq diapositives. Montée seulement quand elle est ouverte. */
export default function VisiteAccueil({ onClose }: Props) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const { setAbonnement } = useNouveautes();
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const [diapo, setDiapo] = useState(0);
  // Écran de fin « recevoir les nouveautés par e-mail » : comptes connectés non abonnés seulement,
  // atteint par « Passer la visite » ou le bouton final ; la croix et Échap ferment sans le montrer.
  const [proposerFin] = useState(() => !!user && !user.abonne_nouveautes);
  const [fin, setFin] = useState(false);
  const [envoi, setEnvoi] = useState(false);
  const apres = useRef<(() => void) | null>(null);
  const ouiRef = useRef<HTMLButtonElement>(null);
  const racine = useRef<HTMLDivElement>(null);
  const scene = useRef<HTMLDivElement>(null);
  const suivantRef = useRef<HTMLButtonElement>(null);
  const ctaRef = useRef<HTMLAnchorElement>(null);
  const premier = useRef(true);

  const etape = useVisite(scene, diapo);
  const def = ETAPES[diapo];
  const derniere = diapo === ETAPES.length - 1;
  const p = (suffixe: string) => t(`nouveautes.visite.etapes.${def.cle}.${suffixe}`);

  const aller = useCallback((n: number) => {
    setDiapo(Math.min(ETAPES.length - 1, Math.max(0, n)));
  }, []);

  // Flèches gauche / droite : changent de diapositive.
  useEffect(() => {
    if (fin) return;
    const touche = (e: KeyboardEvent) => {
      if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
      if (e.key === 'ArrowRight') { e.preventDefault(); setDiapo((d) => Math.min(ETAPES.length - 1, d + 1)); }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); setDiapo((d) => Math.max(0, d - 1)); }
    };
    document.addEventListener('keydown', touche);
    return () => document.removeEventListener('keydown', touche);
  }, [fin]);

  useEffect(() => { if (fin) ouiRef.current?.focus(); }, [fin]);

  // Un bouton masqué ne doit pas emporter le focus avec lui.
  useEffect(() => {
    if (premier.current) { premier.current = false; return; }
    if (racine.current?.contains(document.activeElement)) return;
    (derniere ? ctaRef.current : suivantRef.current)?.focus();
  }, [diapo, derniere]);

  // Passer / bouton final : écran de fin d'abord si on doit le proposer.
  const quitter = (action: (() => void) | null) => {
    if (proposerFin && !fin) { apres.current = action; setFin(true); return; }
    onClose(!action);
    action?.();
  };

  const repondre = async (oui: boolean) => {
    if (oui) {
      setEnvoi(true);
      const ok = await setAbonnement(true);
      setEnvoi(false);
      if (!ok) return; // le message d'erreur est affiché ; l'utilisateur peut réessayer ou refuser
    }
    const action = apres.current;
    onClose(!action);
    action?.();
  };

  // Fin de visite : on ferme (= « vu »), puis on va vers la bonne section de l'accueil.
  const finir = (e: React.MouseEvent) => {
    e.preventDefault();
    quitter(user && user.plan !== 'free' ? null : allerVers);
  };

  const allerVers = () => {
    if (!user) { navigate('/register'); return; }
    const cible = 'pricing';
    const surAccueil = pathname === '/home';
    if (!surAccueil) navigate('/home');
    const debut = Date.now();
    const viser = () => {
      if (document.getElementById(cible)) goToSection(cible);
      else if (Date.now() - debut < 8000) window.setTimeout(viser, 150);
    };
    window.setTimeout(viser, surAccueil ? 0 : 150);
  };

  const libelleFin = !user ? t('nouveautes.visite.cta.guest')
    : user.plan === 'free' ? t('nouveautes.visite.cta.free')
    : t('nouveautes.visite.cta.paid');
  const hrefFin = !user ? '/register' : user.plan === 'free' ? '/home#pricing' : pathname;
  const suivante = ETAPES[diapo + 1];

  return (
    <div
      ref={racine}
      className="vst"
      role="dialog"
      aria-modal="true"
      tabIndex={-1}
      aria-roledescription={t('nouveautes.visite.role')}
      aria-labelledby="vst-titre"
    >
      <button type="button" className="vst-close" aria-label={t('nouveautes.visite.close')} onClick={() => onClose()}>
        <X size={20} aria-hidden="true" />
      </button>

      <div className="vst-stage" ref={scene} aria-hidden="true">
        <VisiteScenes courant={diapo} />
        <div className="vst-legend">
          <b>{etape + 1}/{SEQ[diapo].length}</b>
          <span>{t(`nouveautes.visite.legendes.${def.cle}.${etape + 1}`)}</span>
        </div>
      </div>

      {fin ? (
      <div className="vst-side vst-fin">
        <nav className="vst-steps" aria-label={t('nouveautes.visite.steps_label')}>
          {ETAPES.map((d, n) => (
            <button
              key={d.cle}
              type="button"
              className="done"
              aria-label={`${n + 1}. ${t(`nouveautes.visite.etapes.${d.cle}.kicker`)}`}
              onClick={() => { setFin(false); apres.current = null; aller(n); }}
            >
              {t(`nouveautes.visite.etapes.${d.cle}.court`)}
            </button>
          ))}
        </nav>
        <div className="vst-copy">
          <div className="vst-kicker">
            <Mail size={15} aria-hidden="true" />
            <span>{t('nouveautes.visite.fin.kicker')}</span>
          </div>
          <h2 id="vst-titre">{t('nouveautes.visite.fin.titre')}</h2>
          <p className="vst-lede">{t('nouveautes.visite.fin.texte')}</p>
          <ul className="vst-points">
            {[Sparkles, TrendingUp, Wrench].map((Ic, i) => (
              <li key={i}>
                <span className="vst-ic-sq"><Ic size={18} aria-hidden="true" /></span>
                <div><b>{t(`nouveautes.visite.fin.pts.${i + 1}.t`)}</b><span>{t(`nouveautes.visite.fin.pts.${i + 1}.d`)}</span></div>
              </li>
            ))}
          </ul>
          <p className="vst-fin-q">{t('nouveautes.visite.fin.question')}</p>
        </div>
        <div className="vst-actions">
          <span className="vst-spacer" />
          <button type="button" className="vst-btn" disabled={envoi} onClick={() => repondre(false)}>{t('nouveautes.visite.fin.non')}</button>
          <button ref={ouiRef} type="button" className="vst-btn vst-primary" disabled={envoi} onClick={() => repondre(true)}>{t('nouveautes.visite.fin.oui')}</button>
        </div>
      </div>
      ) : (
      <div className="vst-side">
        <nav className="vst-steps" aria-label={t('nouveautes.visite.steps_label')}>
          {ETAPES.map((d, n) => (
            <button
              key={d.cle}
              type="button"
              className={n < diapo ? 'done' : undefined}
              aria-current={n === diapo ? 'step' : undefined}
              aria-label={`${n + 1}. ${t(`nouveautes.visite.etapes.${d.cle}.kicker`)}`}
              onClick={() => aller(n)}
            >
              {t(`nouveautes.visite.etapes.${d.cle}.court`)}
            </button>
          ))}
        </nav>

        <div className="vst-copy" aria-live="polite">
          <div className="vst-kicker">
            <span>{String(diapo + 1).padStart(2, '0')} — {p('kicker')}</span>
            {def.soon && <span className="vst-soon">{t('nouveautes.visite.soon')}</span>}
          </div>
          <h2 id="vst-titre">{p('titre')}</h2>
          <p className="vst-lede">{p('lede')}</p>
          <ul className="vst-points">
            {def.pts.map((pt, i) => (
              <li key={i} className={pt.later ? 'later' : undefined}>
                <span className="vst-ic-sq">{icone(pt.icone)}</span>
                <div><b>{p(`pts.${i + 1}.t`)}</b><span>{p(`pts.${i + 1}.d`)}</span></div>
              </li>
            ))}
          </ul>
          {derniere && (
            <a className="vst-link vst-more" href="/fonctionnalites"
              onClick={(e) => { e.preventDefault(); onClose(false); navigate('/fonctionnalites'); }}>
              {t('nouveautes.visite.all')}
            </a>
          )}
        </div>

        <div className="vst-actions">
          {!derniere && (
            <button type="button" className="vst-skip" onClick={() => quitter(null)}>{t('nouveautes.visite.skip')}</button>
          )}
          <span className="vst-spacer" />
          {diapo > 0 && (
            <button type="button" className="vst-btn vst-icon" aria-label={t('nouveautes.visite.prev')} onClick={() => aller(diapo - 1)}>
              <ArrowLeft size={18} aria-hidden="true" />
            </button>
          )}
          {!derniere ? (
            <button ref={suivantRef} type="button" className="vst-btn vst-primary" onClick={() => aller(diapo + 1)}>
              <span>{t('nouveautes.visite.next')}</span>
              <small>· {t(`nouveautes.visite.etapes.${suivante.cle}.court`)}</small>
              <ArrowRight size={18} aria-hidden="true" />
            </button>
          ) : (
            <a ref={ctaRef} className="vst-btn vst-primary" href={hrefFin} onClick={finir}>{libelleFin}</a>
          )}
        </div>
      </div>
      )}
    </div>
  );
}
