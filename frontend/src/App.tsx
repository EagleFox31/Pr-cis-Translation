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
import { SPLASH_ATTENDU } from './lib/splash';
import { pages, avecReprise } from './lib/routes';

// Fenêtres d'assistance et d'invitation : un seul hôte pour toute l'appli
// (accueil, administration, intégrations), chargé après le premier rendu.
const SupportModal = lazy(avecReprise(() => import('./components/support/SupportModal')));
const InviteModal = lazy(avecReprise(() => import('./components/invite/InviteModal')));

// Hors accueil, chaque page est chargée à sa première ouverture : un visiteur
// ne télécharge pas l'administration, la connexion ou la page carte d'office.
const LoginPage = lazy(pages.login);
const RegisterPage = lazy(pages.register);
const VerifyEmailPage = lazy(pages.verifyEmail);
const AdminLogsPage = lazy(pages.adminLogs);
const AdminUsersPage = lazy(pages.adminUsers);
const AdminSupportPage = lazy(pages.adminSupport);
const AdminDocumentsPage = lazy(pages.adminDocuments);
const CardPaymentPage = lazy(pages.cardPayment);
const AdminBetaPage = lazy(pages.adminBeta);
const BetaPage = lazy(pages.beta);
const LegalPage = lazy(pages.legal);
const ExtensionPage = lazy(pages.extension);
const ApiPage = lazy(pages.api);
const ExtensionAutoriserPage = lazy(pages.extensionAutoriser);
const ExtensionConnectePage = lazy(pages.extensionConnecte);
const NouveautesPage = lazy(pages.fonctionnalites);
const DesabonnementPage = lazy(pages.desabonnement);

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
  const [showSplash, setShowSplash] = useState(SPLASH_ATTENDU);

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
          <Route path="/fonctionnalites" element={<NouveautesPage />} />
          <Route path="/desabonnement" element={<DesabonnementPage />} />
          <Route path="/integrations/api" element={<ApiPage />} />
          <Route path="/mentions-legales" element={<LegalPage slug="mentions-legales" />} />
          <Route path="/conditions" element={<LegalPage slug="conditions" />} />
          <Route path="/confidentialite" element={<LegalPage slug="confidentialite" />} />
          <Route path="/cookies" element={<LegalPage slug="cookies" />} />
          <Route path="*" element={<Navigate to="/home" replace />} />
        </Routes>
        </Suspense>
        <Suspense fallback={null}><SupportModal /><InviteModal /></Suspense>
        <ToastContainer />
      </AuthProvider>
    </BrowserRouter>
    </GoogleOAuthProvider>
  );
}
