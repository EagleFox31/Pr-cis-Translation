/**
 * Anti-robots à la création de compte (Cloudflare Turnstile).
 *
 * Le script de Cloudflare n'est chargé que sur les pages qui créent un compte.
 * En mode « interaction-only », le widget reste invisible sauf si Cloudflare
 * doute : l'humain n'a rien à faire dans la plupart des cas.
 * Sans VITE_TURNSTILE_SITE_KEY, rien n'est rendu et aucun jeton n'est exigé.
 * Un jeton ne sert qu'une fois : changer `resetKey` en redemande un.
 */
import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';

const SITE_KEY = ((import.meta as any).env.VITE_TURNSTILE_SITE_KEY as string | undefined) || '';
const SCRIPT_URL = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';

export const turnstileActif = SITE_KEY !== '';

type TurnstileApi = {
  render: (el: HTMLElement, options: Record<string, unknown>) => string;
  reset: (id: string) => void;
  remove: (id: string) => void;
};

let chargement: Promise<TurnstileApi> | null = null;

function chargerScript(): Promise<TurnstileApi> {
  chargement ??= new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = SCRIPT_URL;
    script.async = true;
    script.onload = () => resolve((window as any).turnstile);
    script.onerror = () => { chargement = null; reject(new Error('turnstile')); };
    document.head.appendChild(script);
  });
  return chargement;
}

interface Props {
  onToken: (token: string) => void;
  // Script bloqué ou widget en erreur : la page réactive l'envoi et le
  // serveur tranche (message clair) plutôt qu'un bouton grisé sans fin.
  onUnavailable?: () => void;
  resetKey?: number;
}

export default function Turnstile({ onToken, onUnavailable, resetKey = 0 }: Props) {
  const { i18n } = useTranslation();
  const conteneur = useRef<HTMLDivElement>(null);
  const widget = useRef<{ api: TurnstileApi; id: string } | null>(null);
  const rappel = useRef(onToken);
  rappel.current = onToken;
  const panne = useRef(onUnavailable);
  panne.current = onUnavailable;

  useEffect(() => {
    if (!turnstileActif) return;
    let annule = false;
    chargerScript().then((api) => {
      if (annule || !conteneur.current) return;
      const id = api.render(conteneur.current, {
        sitekey: SITE_KEY,
        appearance: 'interaction-only',
        language: i18n.language?.slice(0, 2) || 'auto',
        callback: (token: string) => rappel.current(token),
        'expired-callback': () => rappel.current(''),
        'error-callback': () => { rappel.current(''); panne.current?.(); },
      });
      widget.current = { api, id };
    }).catch(() => { if (!annule) panne.current?.(); });
    return () => {
      annule = true;
      if (widget.current) widget.current.api.remove(widget.current.id);
      widget.current = null;
    };
  }, [i18n.language]);

  useEffect(() => {
    if (resetKey && widget.current) {
      rappel.current('');
      widget.current.api.reset(widget.current.id);
    }
  }, [resetKey]);

  if (!turnstileActif) return null;
  return <div ref={conteneur} className="auth-turnstile" />;
}
