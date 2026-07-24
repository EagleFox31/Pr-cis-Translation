/**
 * Filet des erreurs de RENDU React.
 *
 * Une exception pendant le rendu d'un composant démonte tout l'arbre et laisse
 * un écran blanc. Ce garde-fou l'attrape, la remonte au journal central, et
 * affiche un repli sobre plutôt que le vide — l'utilisateur voit qu'il s'est
 * passé quelque chose et peut recharger.
 */
import { Component, type ErrorInfo, type ReactNode } from 'react';
import { reportClientError } from '../lib/errorReporting';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    reportClientError(error.message || 'Erreur de rendu React', {
      stack: error.stack,
      component: 'ErrorBoundary',
      context: { componentStack: info.componentStack?.slice(0, 4000) },
    });
  }

  handleReload = (): void => {
    if (typeof location !== 'undefined') location.reload();
  };

  render(): ReactNode {
    if (!this.state.hasError) return this.props.children;
    if (this.props.fallback) return this.props.fallback;

    return (
      <div style={{
        minHeight: '100vh', display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', gap: '16px',
        padding: '24px', textAlign: 'center', background: 'var(--white, #fff)',
      }}>
        <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--navy, #0d1b3e)' }}>
          Une erreur est survenue.
        </div>
        <div style={{ fontSize: '13px', color: 'var(--gray-600, #6b7280)', maxWidth: '380px' }}>
          Elle a été enregistrée. Vous pouvez recharger la page.
        </div>
        <button
          onClick={this.handleReload}
          style={{
            padding: '9px 18px', borderRadius: '8px', border: 'none',
            background: 'var(--blue, #1a4dc7)', color: '#fff', fontWeight: 600,
            fontSize: '13px', cursor: 'pointer',
          }}
        >
          Recharger
        </button>
      </div>
    );
  }
}
