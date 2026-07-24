/**
 * Menu déroulant « Administration » — partagé entre la barre de la landing
 * (`Navbar`) et l'en-tête des pages admin (`AdminShell`). Un seul endroit décide
 * de ses entrées : ajouter un outil d'admin se fait ici, pas à deux endroits.
 *
 * Ne s'affiche que pour un compte `admin` (il se rend `null` sinon), donc les
 * appelants peuvent l'inclure sans re-tester le plan.
 */
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';

export default function AdminMenu() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointer = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  if (user?.plan !== 'admin') return null;

  const go = (path: string) => { setOpen(false); navigate(path); };

  return (
    <div ref={ref} style={{ position: 'relative', flexShrink: 0 }}>
      <button
        onClick={() => setOpen((v) => !v)}
        title={t('admin.menu', 'Administration')}
        aria-haspopup="menu"
        aria-expanded={open}
        style={{
          height: '34px', padding: '0 12px', borderRadius: '8px',
          display: 'flex', alignItems: 'center', gap: '6px',
          background: open ? 'var(--gray-100)' : 'transparent',
          color: 'var(--gray-700)', border: '1.5px solid var(--gray-200)',
          fontWeight: 600, fontSize: '12px', cursor: 'pointer',
          fontFamily: 'inherit', whiteSpace: 'nowrap',
        }}
      >
        {t('admin.menu', 'Administration')}
        <span style={{
          fontSize: '9px', lineHeight: 1,
          transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s',
        }}>▼</span>
      </button>
      {open && (
        <div role="menu" style={{
          position: 'absolute', top: 'calc(100% + 6px)', right: 0, minWidth: '190px',
          background: '#fff', border: '1px solid var(--gray-200)', borderRadius: '10px',
          boxShadow: '0 12px 32px rgba(13,27,62,0.14)', padding: '6px', zIndex: 1002,
        }}>
          <button role="menuitem" onClick={() => go('/admin/users')} style={itemStyle}
            onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--gray-100)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}>
            {t('admin_users.nav_full', 'Comptes utilisateurs')}
          </button>
          <button role="menuitem" onClick={() => go('/admin/logs')} style={itemStyle}
            onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--gray-100)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}>
            {t('logs.title', 'Journal des erreurs')}
          </button>
        </div>
      )}
    </div>
  );
}

const itemStyle: React.CSSProperties = {
  display: 'block', width: '100%', textAlign: 'left',
  padding: '9px 12px', borderRadius: '7px', border: 'none',
  background: 'transparent', color: 'var(--gray-700)',
  fontWeight: 600, fontSize: '13px', cursor: 'pointer',
  fontFamily: 'inherit', whiteSpace: 'nowrap',
};
