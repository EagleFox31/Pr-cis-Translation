import { useState } from 'react';
import type { FormatOptions } from '../components/upload/TranslationSection';

const API_KEY = import.meta.env.VITE_API_KEY || 'precis_frontend_secure_key_2026_xK9mP2vL';
const API_BASE = import.meta.env.VITE_API_BASE || '';

export interface TranslationResult {
  blob: Blob;
  filename: string;
}

export function useTranslation() {
  const [isTranslating, setIsTranslating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const translateFile = async (file: File, targetLang: string, formatOptions?: FormatOptions): Promise<TranslationResult> => {
    setIsTranslating(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('target_lang', targetLang);
      if (formatOptions) {
        formData.append('format_options', JSON.stringify(formatOptions));
      }

      const response = await fetch(`${API_BASE}/api/translate`, {
        method: 'POST',
        headers: {
          'X-API-Key': API_KEY,
        },
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || errorData.error || 'Translation failed');
      }

      const blob = await response.blob();
      const filename = file.name.replace(/\.[^/.]+$/, "") + "_TRADUIT." + file.name.split('.').pop();

      return { blob, filename };
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(message);
      throw err;
    } finally {
      setIsTranslating(false);
    }
  };

  return { translateFile, isTranslating, error };
}