import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { CheckCircle2, XCircle, Info, AlertTriangle, X } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

type ToastType = 'success' | 'error' | 'info' | 'warning';

export interface ToastAction {
  label: string;
  onClick: () => void;
}

interface ToastMessage {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
  action?: ToastAction;
  duration: number;
}

let toastListeners: Array<(t: ToastMessage) => void> = [];

export function showToast(type: ToastType, title: string, message?: string, action?: ToastAction) {
  const duration = type === 'error' ? 6000 : 4000;
  const toast: ToastMessage = { id: Date.now().toString(), type, title, message, action, duration };
  toastListeners.forEach((fn) => fn(toast));
}

const icons: Record<ToastType, LucideIcon> = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
  warning: AlertTriangle,
};

const colors: Record<ToastType, { bg: string; border: string; icon: string }> = {
  success: { bg: '#f0fdf4', border: '#86efac', icon: '#16a34a' },
  error: { bg: '#fef2f2', border: '#fecaca', icon: '#dc2626' },
  info: { bg: '#eff6ff', border: '#93c5fd', icon: '#2563eb' },
  warning: { bg: '#fffbeb', border: '#fde68a', icon: '#d97706' },
};

function ToastItem({ toast, onDone }: { toast: ToastMessage; onDone: (id: string) => void }) {
  const c = colors[toast.type];

  useEffect(() => {
    const timer = setTimeout(() => onDone(toast.id), toast.duration);
    return () => clearTimeout(timer);
  }, [toast.id, toast.duration, onDone]);

  return (
    <motion.div
      initial={{ opacity: 0, x: 80, scale: 0.95 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 80, scale: 0.95 }}
      transition={{ type: 'spring', damping: 20, stiffness: 300 }}
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '10px',
        padding: '12px 16px',
        borderRadius: '12px',
        border: `1px solid ${c.border}`,
        background: c.bg,
        boxShadow: '0 8px 24px rgba(0,0,0,0.08), 0 2px 6px rgba(0,0,0,0.04)',
        maxWidth: '380px',
        pointerEvents: 'auto',
        backdropFilter: 'blur(8px)',
      }}
    >
      <span
        style={{
          color: c.icon,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          marginTop: '1px',
        }}
      >
        {(() => { const Icon = icons[toast.type]; return <Icon size={19} strokeWidth={2.2} />; })()}
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: '13px', fontWeight: 600, color: '#0d1b3e' }}>{toast.title}</div>
        {toast.message && (
          <div style={{ fontSize: '12px', color: '#64748b', marginTop: '2px', lineHeight: 1.4 }}>
            {toast.message}
          </div>
        )}
        {toast.action && (
          <button
            onClick={() => { toast.action!.onClick(); onDone(toast.id); }}
            style={{
              marginTop: '8px',
              background: 'none',
              border: `1px solid ${c.icon}`,
              color: c.icon,
              borderRadius: '6px',
              padding: '4px 10px',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
              fontFamily: 'inherit',
            }}
          >
            {toast.action.label}
          </button>
        )}
      </div>
      <button
        onClick={() => onDone(toast.id)}
        style={{
          background: 'none',
          border: 'none',
          color: '#94a3b8',
          cursor: 'pointer',
          padding: '2px',
          lineHeight: 1,
          display: 'flex',
          alignItems: 'center',
        }}
        aria-label="Fermer"
      >
        <X size={15} strokeWidth={2.2} />
      </button>
    </motion.div>
  );
}

export default function ToastContainer() {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const addToast = useCallback((t: ToastMessage) => {
    setToasts((prev) => [...prev, t]);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  useEffect(() => {
    toastListeners.push(addToast);
    return () => {
      toastListeners = toastListeners.filter((fn) => fn !== addToast);
    };
  }, [addToast]);

  return (
    <div
      style={{
        position: 'fixed',
        top: '84px',
        right: '20px',
        zIndex: 9999,
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
        pointerEvents: 'none',
      }}
    >
      <AnimatePresence>
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onDone={removeToast} />
        ))}
      </AnimatePresence>
    </div>
  );
}
