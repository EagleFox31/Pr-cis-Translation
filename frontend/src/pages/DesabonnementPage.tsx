import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import AppBar from '../components/navbar/AppBar';
import Button from '../components/ui/Button';
import Skeleton from '../components/ui/Skeleton';
import api from '../services/api';
import '../nouveautes.css';

// invalide : jeton refusé ; abonne : en attente de confirmation ; fait : plus abonné ;
// reseau : serveur injoignable (on peut réessayer).
type Etat = 'chargement' | 'invalide' | 'abonne' | 'fait' | 'reseau';

export default function DesabonnementPage() {
  const { t, i18n } = useTranslation();
  const [params] = useSearchParams();
  const jeton = params.get('jeton') ?? '';
  const [etat, setEtat] = useState<Etat>('chargement');
  const [envoi, setEnvoi] = useState(false);
  const [essai, setEssai] = useState(0);

  useEffect(() => { document.title = t('nouveautes.unsub.subscribed.title'); }, [t, i18n.language]);

  // Le GET ne fait que lire l'état : seul le bouton désabonne (les antivirus de messagerie suivent les liens).
  useEffect(() => {
    if (!jeton) { setEtat('invalide'); return; }
    let annule = false;
    setEtat('chargement');
    (async () => {
      try {
        const res = await api.get(`/api/nouveautes/desabonnement?jeton=${encodeURIComponent(jeton)}`);
        if (annule) return;
        if (!res.ok) setEtat(res.status === 400 ? 'invalide' : 'reseau');
        else setEtat((res.data as { abonne_nouveautes?: boolean }).abonne_nouveautes ? 'abonne' : 'fait');
      } catch {
        if (!annule) setEtat('reseau');
      }
    })();
    return () => { annule = true; };
  }, [jeton, essai]);

  const desabonner = async () => {
    setEnvoi(true);
    try {
      const res = await api.post(`/api/nouveautes/desabonnement?jeton=${encodeURIComponent(jeton)}`);
      setEtat(res.ok ? 'fait' : res.status === 400 ? 'invalide' : 'reseau');
    } catch {
      setEtat('reseau');
    } finally {
      setEnvoi(false);
    }
  };

  const accueil = <Link className="nv-card__link" to="/">{t('nouveautes.unsub.home')}</Link>;

  return (
    <div className="nv-page">
      <AppBar />
      <main className="nv-unsub">
        <div className="nv-card" aria-live="polite">
          {etat === 'chargement' && (
            <div role="status" aria-busy="true" aria-label={t('nouveautes.unsub.loading')} style={{ width: '100%', display: 'grid', gap: 12 }}>
              <Skeleton height="28px" width="60%" />
              <Skeleton height="16px" />
              <Skeleton height="16px" width="80%" />
            </div>
          )}

          {etat === 'invalide' && (
            <>
              <h1>{t('nouveautes.unsub.invalid.title')}</h1>
              <p>{t('nouveautes.unsub.invalid.text')}</p>
              <div className="nv-card__actions">
                <Link className="ui-btn ui-btn--secondary ui-btn--md" to="/fonctionnalites">{t('nouveautes.unsub.see')}</Link>
              </div>
              {accueil}
            </>
          )}

          {etat === 'abonne' && (
            <>
              <h1>{t('nouveautes.unsub.subscribed.title')}</h1>
              <p>{t('nouveautes.unsub.subscribed.text')}</p>
              <div className="nv-card__actions">
                <Button onClick={desabonner} loading={envoi}>{t('nouveautes.unsub.subscribed.button')}</Button>
              </div>
              {accueil}
            </>
          )}

          {etat === 'fait' && (
            <>
              <h1>{t('nouveautes.unsub.done.title')}</h1>
              <p>{t('nouveautes.unsub.done.text')}</p>
              <div className="nv-card__actions">
                <Link className="ui-btn ui-btn--secondary ui-btn--md" to="/fonctionnalites">{t('nouveautes.unsub.see')}</Link>
              </div>
              {accueil}
            </>
          )}

          {etat === 'reseau' && (
            <>
              <h1>{t('nouveautes.unsub.network.title')}</h1>
              <p>{t('nouveautes.unsub.network.text')}</p>
              <div className="nv-card__actions">
                <Button variant="secondary" onClick={() => setEssai((n) => n + 1)}>{t('nouveautes.unsub.network.retry')}</Button>
              </div>
              {accueil}
            </>
          )}
        </div>
      </main>
    </div>
  );
}
