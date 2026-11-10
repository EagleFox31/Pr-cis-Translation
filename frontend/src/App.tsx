import { lazy, Suspense, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useSearchParams } from 'react-router-dom';
import { AnimatePresence } from 'motion/react';
import { GoogleOAuthProvider } from '@react-oauth/google';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import SplashScreen from './components/SplashScreen';
import Home from './pages/Home';
import './beta.css';
import ToastContainer from './components/ui/Toast';
import { authReturnTo } from './lib/authReturn';
import { splashAttendu } from './lib/splash';

// Hors accueil, chaque page est chargée à sa première ouverture : un visiteur
// ne télécharge pas l'administration, la connexion ou la page carte d'office.
const LoginPage = lazy(() => import('./pages/LoginPage'));
const RegisterPage = lazy(() => import('./pages/RegisterPage'));
const VerifyEmailPage = lazy(() => import('./pages/VerifyEmailPage'));
const AdminLogsPage = lazy(() => import('./pages/AdminLogsPage'));
const AdminUsersPage = lazy(() => import('./pages/AdminUsersPage'));
const AdminSupportPage = lazy(() => import('./pages/AdminSupportPage'));
const AdminDocumentsPage = lazy(() => import('./pages/AdminDocumentsPage'));
const CardPaymentPage = lazy(() => import('./pages/CardPaymentPage'));

const AdminBetaPage = lazy(() => import('./pages/AdminBetaPage'));
const BetaPage = lazy(() => import('./pages/BetaPage'));
const LegalPage = lazy(() => import('./pages/LegalPage'));
const ExtensionPage = lazy(() => import('./pages/ExtensionPage'));
const ApiPage = lazy(() => import('./pages/ApiPage'));
const ExtensionAutoriserPage = lazy(() => import('./pages/ExtensionAutoriserPage'));
const ExtensionConnectePage = lazy(() => import('./pages/ExtensionConnectePage'));

/** Redirige vers /home si déjà connecté ( pages auth ). */
function GuestRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const [params] = useSearchParams();
  if (loading) return null;
  if (user) return <Navigate to={authReturnTo(params)} replace />;
  return <>{children}</>;
}

/** Réserve une page aux comptes admin. Le frontend ne PROTÈGE rien (le backend
 *  refuse via `require_admin`) : il évite juste d'afficher une page vide de
 *  données 403 à qui n'y a pas droit. */
function AdminRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user?.plan !== 'admin') return <Navigate to="/home" replace />;
  return <>{children}</>;
}

const GOOGLE_CLIENT_ID = (import.meta as any).env.VITE_GOOGLE_CLIENT_ID || '';

export default function App() {
  // La page carte s'affiche dans le cadre de la fenêtre de paiement : hors
  // AuthProvider, pour qu'une seconde instance ne dispute pas le jeton de
  // rafraîchissement à l'application qui l'héberge.
  if (window.location.pathname === '/paiement/carte') return <Suspense fallback={null}><CardPaymentPage /></Suspense>;
  return <MainApp />;
}

function MainApp() {
  const [showSplash, setShowSplash] = useState(splashAttendu);

  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
    <BrowserRouter>
      <AuthProvider>
        <AnimatePresence mode="wait">
          {showSplash && (
            <SplashScreen key="splash" onComplete={() => setShowSplash(false)} />
          )}
        </AnimatePresence>
        <Suspense fallback={null}>
        <Routes>
          {/* Accès visiteur : la page d'accueil est ouverte à tous */}
          <Route path="/home" element={<Home />} />
          <Route path="/login" element={<GuestRoute><LoginPage /></GuestRoute>} />
          <Route path="/register" element={<GuestRoute><RegisterPage /></GuestRoute>} />
          <Route path="/verify-email" element={<VerifyEmailPage />} />
          <Route path="/admin/logs" element={<AdminRoute><AdminLogsPage /></AdminRoute>} />
          <Route path="/admin/users" element={<AdminRoute><AdminUsersPage /></AdminRoute>} />
          <Route path="/admin/documents" element={<AdminRoute><AdminDocumentsPage /></AdminRoute>} />
          <Route path="/admin/support" element={<AdminRoute><AdminSupportPage /></AdminRoute>} />
          <Route path="/admin/beta" element={<AdminRoute><AdminBetaPage /></AdminRoute>} />
          <Route path="/beta" element={<BetaPage />} />
          <Route path="/extension" element={<ExtensionPage />} />
          <Route path="/extension/autoriser" element={<ExtensionAutoriserPage />} />
          <Route path="/extension/connecte" element={<ExtensionConnectePage />} />
          <Route path="/integrations/api" element={<ApiPage />} />
          <Route path="/mentions-legales" element={<LegalPage slug="mentions-legales" />} />
          <Route path="/conditions" element={<LegalPage slug="conditions" />} />
          <Route path="/confidentialite" element={<LegalPage slug="confidentialite" />} />
          <Route path="/cookies" element={<LegalPage slug="cookies" />} />
          <Route path="*" element={<Navigate to="/home" replace />} />
        </Routes>
        </Suspense>
        <ToastContainer />
      </AuthProvider>
    </BrowserRouter>
    </GoogleOAuthProvider>
  );
}
