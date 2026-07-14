import { useState, useEffect, useCallback } from 'react';
import { idbSet, idbGet, idbDelete } from '../utils/idbStore';

const LS_KEY = 'precis_doc_library';
const MAX_STORAGE_BYTES = 50 * 1024 * 1024; // 50 Mo

export interface DocMeta {
  id: string;
  filename: string;
  originalName: string;
  targetLang: string;
  date: string;       // ISO string
  sizeByes: number;
  ext: string;
}

function loadMeta(): DocMeta[] {
  try {
    return JSON.parse(localStorage.getItem(LS_KEY) || '[]');
  } catch {
    return [];
  }
}

function saveMeta(docs: DocMeta[]) {
  localStorage.setItem(LS_KEY, JSON.stringify(docs));
}

export function useDocumentLibrary() {
  const [documents, setDocuments] = useState<DocMeta[]>(loadMeta);

  useEffect(() => {
    saveMeta(documents);
  }, [documents]);

  const saveDocument = useCallback(async (blob: Blob, filename: string, meta: Omit<DocMeta, 'id' | 'date' | 'sizeByes' | 'filename'>) => {
    const id = crypto.randomUUID();
    const doc: DocMeta = {
      ...meta,
      id,
      filename,
      date: new Date().toISOString(),
      sizeByes: blob.size,
    };

    // Purge des plus anciens si dépassement quota
    const existing = loadMeta();
    let totalSize = existing.reduce((s, d) => s + d.sizeByes, 0) + blob.size;
    const sorted = [...existing].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
    const toDelete: string[] = [];
    while (totalSize > MAX_STORAGE_BYTES && sorted.length > 0) {
      const oldest = sorted.shift()!;
      toDelete.push(oldest.id);
      totalSize -= oldest.sizeByes;
    }
    for (const did of toDelete) {
      await idbDelete(did);
    }
    const filtered = existing.filter(d => !toDelete.includes(d.id));

    await idbSet(id, blob);
    const updated = [doc, ...filtered];
    setDocuments(updated);
    saveMeta(updated);
    return id;
  }, []);

  const getBlob = useCallback((id: string): Promise<Blob | undefined> => {
    return idbGet(id);
  }, []);

  const deleteDocument = useCallback(async (id: string) => {
    await idbDelete(id);
    setDocuments(prev => {
      const updated = prev.filter(d => d.id !== id);
      saveMeta(updated);
      return updated;
    });
  }, []);

  const clearAll = useCallback(async () => {
    const all = loadMeta();
    for (const d of all) await idbDelete(d.id);
    setDocuments([]);
    saveMeta([]);
  }, []);

  return { documents, saveDocument, getBlob, deleteDocument, clearAll };
}
