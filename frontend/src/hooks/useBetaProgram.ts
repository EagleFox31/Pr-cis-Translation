import { useCallback, useEffect, useRef, useState } from 'react';
import type { BetaLimits } from './useBeta';
import api from '../services/api';

export interface BetaProgram {
  name: string; capacity: number; first_wave_capacity: number; access_days: number;
  limits: BetaLimits; availability: 'open' | 'closed' | 'full' | 'ended'; applications_open: boolean;
}

export function useBetaProgram() {
  const [program, setProgram] = useState<BetaProgram | null>(null);
  const [error, setError] = useState(false);
  const requestId = useRef(0);
  const refresh = useCallback(async () => {
    const id = ++requestId.current;
    try {
      const result = await api.get('/api/beta/program');
      if (requestId.current !== id) return;
      if (result.ok) { setProgram(result.data as BetaProgram); setError(false); }
      else setError(true);
    } catch { if (requestId.current === id) setError(true); }
  }, []);
  useEffect(() => { void refresh(); return () => { requestId.current++; }; }, [refresh]);
  return { program, error, refresh };
}
