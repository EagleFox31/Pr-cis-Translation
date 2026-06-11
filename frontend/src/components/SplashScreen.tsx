import React, { useEffect } from 'react';
import { motion } from 'motion/react';
const logo = "/Logo.png";
const mascot = "/Identite Precis.png";

interface SplashScreenProps {
  onComplete: () => void;
}

export default function SplashScreen({ onComplete }: SplashScreenProps) {

  useEffect(() => {
    // Wait for 3 seconds (or you can click to skip)
    const timer = setTimeout(() => {
      onComplete();
    }, 3000);

    return () => clearTimeout(timer);
  }, [onComplete]);

  return (
    <motion.div
      initial={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 1, ease: "easeInOut" }}
      className="fixed inset-0 z-[9999] flex flex-col items-center justify-center font-['DM_Sans']"
      style={{ background: '#FFFFFF' }} // White Background
    >
      {/* Subtle Background Glow */}
      <div 
        className="absolute inset-0 opacity-[0.03]"
        style={{ 
          background: 'radial-gradient(circle at 50% 50%, #1a4dc7 0%, transparent 70%)' 
        }}
      />

      {/* Grid Pattern Overlay */}
      <div 
        className="absolute inset-0 opacity-[0.02]"
        style={{ 
          backgroundImage: 'linear-gradient(#000 1px, transparent 1px), linear-gradient(90deg, #000 1px, transparent 1px)',
          backgroundSize: '40px 40px'
        }}
      />

      <div className="relative z-10 flex flex-col items-center gap-10 max-w-2xl w-full px-8">
        
        {/* Central Card with Soft Shadow */}
        <motion.div 
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 1, ease: "easeOut" }}
          className="bg-white rounded-[24px] py-14 px-6 sm:p-10 md:p-[60px_40px] border border-black/5 shadow-[0_20px_40px_rgba(13,27,62,0.06)] w-[85%] sm:w-full flex flex-col items-center justify-center gap-[30px] min-h-[180px] sm:min-h-0"
        >
          {/* Horizontal Layout (Always) */}
          <div className="flex flex-row items-center justify-center gap-3 sm:gap-6 md:gap-[35px] w-full">
            {/* Mascot */}
            <motion.div
              animate={{ y: [0, -5, 0] }}
              transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
              className="flex-shrink-0"
            >
              <img 
                src={mascot} 
                alt="Mascotte Précis" 
                className="w-10 sm:w-20 md:w-[110px] h-auto"
              />
            </motion.div>
            
            {/* Elegant Vertical Divider */}
            <div className="w-[1px] h-8 sm:h-16 md:h-[80px] bg-black/10"></div>
            
            {/* Logo and Animated Text */}
            <div className="flex flex-col items-start">
              <div className="flex items-center gap-3">
                <img src={logo} alt="Logo Précis" className="h-6 sm:h-12 md:h-[64px] w-auto" />
                <span className="animated-logo-text text-2xl sm:text-5xl md:text-[64px]">
                  <span style={{ animationDelay: '0.0s' }}>r</span>
                  <span style={{ animationDelay: '0.1s' }}>é</span>
                  <span style={{ animationDelay: '0.2s' }}>c</span>
                  <span style={{ animationDelay: '0.3s' }}>i</span>
                  <span style={{ animationDelay: '0.4s' }}>s</span>
                </span>
              </div>
            </div>
          </div>
        </motion.div>
      </div>

      {/* Signature */}
      <motion.div 
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
        className="absolute bottom-6 sm:bottom-12 flex justify-center"
      >
        <div className="flex items-center gap-2 text-slate-500">
          <span className="font-bold tracking-widest text-[#0d1b3e] text-lg">PRÉCIS</span>
          <span className="font-['Pinyon_Script'] text-2xl text-[#1a4dc7] italic pt-0.5">by</span>
          <span className="font-bold text-slate-600 tracking-tight text-sm">Trigenys Group</span>
        </div>
      </motion.div>

    </motion.div>
  );
}
