import { useState } from 'react';
import Home from './pages/Home';
import SplashScreen from './components/SplashScreen';
import { AnimatePresence } from 'motion/react';

export default function App() {
  const [showSplash, setShowSplash] = useState(true);

  return (
    <>
      <AnimatePresence mode="wait">
        {showSplash && (
          <SplashScreen key="splash" onComplete={() => setShowSplash(false)} />
        )}
      </AnimatePresence>
      <Home />
    </>
  );
}
