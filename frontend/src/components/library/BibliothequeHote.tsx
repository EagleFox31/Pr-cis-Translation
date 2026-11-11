/**
 * Tiroir « Mes documents » hors de l'accueil (administration, intégrations).
 *
 * L'avatar doit faire la même chose sur toutes les pages : ouvrir ce tiroir.
 * La liste, la suppression, le paiement et l'arrêt se font sur place ; l'aperçu
 * et la relance vivent dans l'accueil, on y passe donc avec la demande dans
 * l'état de navigation (`DemandeBibliotheque`), que l'accueil exécute.
 */
import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import DocumentLibrary from './DocumentLibrary';
import { useDocumentLibrary, type DocMeta } from '../../hooks/useDocumentLibrary';
import { stopTranslation, type StopMode } from '../../hooks/useStreamingTranslation';
import { useAuth } from '../../contexts/AuthContext';
import { showToast } from '../ui/Toast';

export interface DemandeBibliotheque {
  bibliotheque: { action: 'apercu' | 'relance'; docId: string };
}

// Le fichier d'origine demandé par le tiroir pour l'aperçu : l'accueil le
// reprend au lieu de le télécharger une seconde fois (une promesse ne passe
// pas par l'état de navigation).
let sourceEnAttente: { docId: string; source: Promise<Blob | undefined> } | null = null;

export function prendreSource(docId: string): Promise<Blob | undefined> | null {
  const s = sourceEnAttente?.docId === docId ? sourceEnAttente.source : null;
  sourceEnAttente = null;
  return s;
}

export default function BibliothequeHote({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { refreshUser } = useAuth();
  const { documents, charge, erreur, refresh, getBlob, getOriginalBlob, deleteDocument, clearAll } = useDocumentLibrary();

  const versAccueil = useCallback((action: 'apercu' | 'relance', docId: string) => {
    const state: DemandeBibliotheque = { bibliotheque: { action, docId } };
    navigate('/home', { state });
  }, [navigate]);

  const arreter = useCallback(async (doc: DocMeta, mode: StopMode) => {
    if (!doc.jobId) return;
    try {
      await stopTranslation(doc.jobId, mode);
    } catch (err) {
      showToast('error', t('story.stop_failed'), err instanceof Error ? err.message : undefined);
      throw err;
    }
    refresh();
  }, [refresh, t]);

  return (
    <DocumentLibrary
      isOpen={isOpen}
      onClose={onClose}
      documents={documents}
      loading={!charge}
      erreur={erreur}
      onRefresh={refresh}
      onPreview={(req) => {
        sourceEnAttente = { docId: req.docId, source: req.source };
        versAccueil('apercu', req.docId);
      }}
      onDelete={deleteDocument}
      onClearAll={clearAll}
      getBlob={getBlob}
      getOriginalBlob={getOriginalBlob}
      onPaid={() => { refresh(); refreshUser(); }}
      onRetry={(doc) => versAccueil('relance', doc.id)}
      onStop={arreter}
    />
  );
}
