import { authHeader, refreshAccessToken } from './api';

const API_KEY = import.meta.env.VITE_API_KEY || '';
const API_BASE = import.meta.env.VITE_API_BASE || '';

/**
 * Envoi unique du fichier (docs/etude-test-gros-fichier.md, option C).
 *
 * Le fichier part UNE fois, dès qu'il est choisi. L'analyse, l'aperçu de
 * l'original et la traduction envoient ensuite son identifiant au lieu du
 * fichier. Si le dépôt échoue ou a expiré, chacun renvoie le fichier lui-même,
 * comme avant : le dépôt ne peut que faire gagner du temps.
 */
const depots = new WeakMap<Blob, string>();

export function depotDe(blob: Blob): string | undefined {
  return depots.get(blob);
}

function envoyer(file: File, onProgress: (pct: number) => void, signal: AbortSignal) {
  return new Promise<{ status: number; body: { upload_id?: string } }>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${API_BASE}/api/upload?nom=${encodeURIComponent(file.name)}`);
    xhr.setRequestHeader('X-API-Key', API_KEY);
    for (const [k, v] of Object.entries(authHeader())) xhr.setRequestHeader(k, v);
    xhr.setRequestHeader('Content-Type', 'application/octet-stream');
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.min(99, Math.floor((e.loaded / e.total) * 100)));
    };
    xhr.onload = () => {
      let body = {};
      try { body = JSON.parse(xhr.responseText); } catch { /* corps vide */ }
      resolve({ status: xhr.status, body });
    };
    xhr.onerror = () => reject(new Error('network'));
    xhr.onabort = () => reject(new DOMException('aborted', 'AbortError'));
    signal.addEventListener('abort', () => xhr.abort());
    xhr.send(file);
  });
}

/** Dépose le fichier ; renvoie son identifiant, ou null si le dépôt a échoué. */
export async function deposer(
  file: File, onProgress: (pct: number) => void, signal: AbortSignal,
): Promise<string | null> {
  const deja = depots.get(file);
  if (deja) return deja;
  let res = await envoyer(file, onProgress, signal);
  if (res.status === 401 && await refreshAccessToken()) res = await envoyer(file, onProgress, signal);
  const id = res.status === 200 ? res.body.upload_id : undefined;
  if (!id) return null;
  depots.set(file, id);
  onProgress(100);
  return id;
}

/**
 * POST d'un formulaire qui porte le fichier : par son identifiant s'il est
 * déposé, sinon le fichier lui-même. Un dépôt expiré (410) est oublié et la
 * requête repart avec le fichier.
 */
export async function postAvecFichier(
  url: string, file: Blob, nom: string, champs: (form: FormData) => void, init: RequestInit,
): Promise<Response> {
  const appel = (id: string | undefined) => {
    const form = new FormData();
    if (id) form.append('upload_id', id);
    else form.append('file', file, nom);
    champs(form);
    return fetch(url, { ...init, method: 'POST', body: form });
  };
  const id = depots.get(file);
  const res = await appel(id);
  if (id && res.status === 410) {
    depots.delete(file);
    return appel(undefined);
  }
  return res;
}
