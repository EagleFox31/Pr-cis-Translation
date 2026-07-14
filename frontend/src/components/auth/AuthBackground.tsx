import { useEffect, useRef } from 'react';

/**
 * Fond animé : mots traduits en plusieurs langues qui flottent doucement.
 *
 * Chaque mot apparaît, dérive légèrement, puis s'estompe. L'effet est subtil
 * et renforce le thème « traduction » sans distraire du formulaire.
 */

interface FloatingWord {
  text: string;
  x: number;       // % de la largeur
  y: number;       // % de la hauteur
  delay: number;   // secondes avant apparition
  duration: number; // secondes de vie
  fontSize: number; // px
  opacity: number;  // 0..1
}

const WORDS: FloatingWord[] = [
  { text: 'Hello', x: 8, y: 12, delay: 0, duration: 7, fontSize: 18, opacity: 0.12 },
  { text: 'Bonjour', x: 85, y: 8, delay: 1.2, duration: 8, fontSize: 16, opacity: 0.10 },
  { text: 'Hola', x: 15, y: 75, delay: 2.5, duration: 7, fontSize: 15, opacity: 0.11 },
  { text: 'Ciao', x: 78, y: 82, delay: 0.8, duration: 9, fontSize: 17, opacity: 0.09 },
  { text: 'Hallo', x: 5, y: 45, delay: 3.2, duration: 8, fontSize: 14, opacity: 0.10 },
  { text: 'Olá', x: 90, y: 38, delay: 1.8, duration: 7, fontSize: 16, opacity: 0.11 },
  { text: '你好', x: 40, y: 15, delay: 4.0, duration: 7, fontSize: 20, opacity: 0.08 },
  { text: 'Привет', x: 60, y: 88, delay: 2.0, duration: 8, fontSize: 18, opacity: 0.09 },
  { text: 'Hello', x: 22, y: 55, delay: 5.5, duration: 6, fontSize: 13, opacity: 0.11 },
  { text: 'Salut', x: 72, y: 22, delay: 3.8, duration: 7, fontSize: 15, opacity: 0.10 },
  { text: 'Merhaba', x: 48, y: 68, delay: 1.0, duration: 9, fontSize: 15, opacity: 0.09 },
  { text: 'こんにちは', x: 12, y: 30, delay: 6.0, duration: 7, fontSize: 19, opacity: 0.07 },
  { text: 'Translate', x: 82, y: 55, delay: 0.3, duration: 8, fontSize: 14, opacity: 0.10 },
  { text: 'Precis', x: 35, y: 85, delay: 4.5, duration: 6, fontSize: 13, opacity: 0.12 },
  { text: 'Traduire', x: 55, y: 42, delay: 2.8, duration: 7, fontSize: 16, opacity: 0.10 },
];

export default function AuthBackground() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    // Animation subtile de drift vertical
    const interval = setInterval(() => {
      const spans = el.querySelectorAll<HTMLSpanElement>('.auth-bg-word');
      spans.forEach((span) => {
        const currentY = parseFloat(span.style.top || '0');
        const drift = (Math.random() - 0.5) * 0.3;
        span.style.top = `${Math.max(0, Math.min(100, currentY + drift))}%`;
      });
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div
      ref={ref}
      style={{
        position: 'fixed', inset: 0, pointerEvents: 'none', overflow: 'hidden',
        zIndex: 0, userSelect: 'none',
      }}
    >
      <style>{`
        @keyframes authWordFade {
          0%   { opacity: 0; transform: translateY(4px); }
          10%  { opacity: var(--aw-opacity); transform: translateY(0); }
          80%  { opacity: var(--aw-opacity); transform: translateY(-3px); }
          100% { opacity: 0; transform: translateY(-8px); }
        }
      `}</style>
      {WORDS.map((w, i) => (
        <span
          key={i}
          className="auth-bg-word"
          style={{
            position: 'absolute',
            left: `${w.x}%`,
            top: `${w.y}%`,
            fontSize: `${w.fontSize}px`,
            fontWeight: 500,
            color: 'var(--blue)',
            opacity: 0,
            animation: `authWordFade ${w.duration}s ease-in-out ${w.delay}s infinite`,
            '--aw-opacity': w.opacity,
            fontFamily: 'inherit',
            whiteSpace: 'nowrap',
          } as React.CSSProperties}
        >
          {w.text}
        </span>
      ))}
    </div>
  );
}
