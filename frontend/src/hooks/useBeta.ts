import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import api from '../services/api';

export type BetaFormat = 'pdf' | 'pptx' | 'docx' | 'xlsx';
export type BetaLimits = Record<BetaFormat | 'xlsx_words', number>;
export interface BetaAllowance {
  unit: 'pages' | 'slides' | 'words' | 'sheets';
  limit: number; used: number; remaining: number;
  word_limit?: number; words_used?: number; words_remaining?: number;
}
export interface BetaEnrollment {
  id: string; email: string; primary_format: BetaFormat;
  state: 'invited' | 'active' | 'expired' | 'revoked';
  invited_at: string; activated_at: string | null; expires_at: string | null;
  limits: BetaLimits; formats: Record<BetaFormat, BetaAllowance>;
}
export interface BetaMe {
  enrollment: BetaEnrollment | null; campaign_name: string | null;
  can_activate: boolean; email_verified: boolean;
  access_days: number | null;
}

export function useBeta(refreshKey?: unknown) {
  const { user } = useAuth();
  const [data, setData] = useState<BetaMe | null>(null);
  const [error, setError] = useState(false);
  const requestId = useRef(0);
  const userId = user?.id;
  const refresh = useCallback(async () => {
    const id = ++requestId.current;
    if (!userId) { setData(null); return; }
    try {
      const result = await api.get('/api/beta/me');
      if (id !== requestId.current) return;
      if (result.ok) { setData(result.data as BetaMe); setError(false); }
      else setError(true);
    } catch { if (id === requestId.current) setError(true); }
  }, [userId]);
  useEffect(() => {
    setData(null); void refresh();
    return () => { requestId.current++; };
  }, [refresh, refreshKey]);
  return { data, error, refresh };
}
