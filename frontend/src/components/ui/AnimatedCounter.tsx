import { useEffect, useState, useRef } from 'react';

interface AnimatedCounterProps {
  value: string;
  suffix?: string;
  duration?: number;
}

export default function AnimatedCounter({ value, suffix = '', duration = 2000 }: AnimatedCounterProps) {
  const [display, setDisplay] = useState('0');
  const ref = useRef<HTMLDivElement>(null);
  const hasAnimated = useRef(false);

  // Parse numeric part from value like "99%" or "50+"
  const numMatch = value.match(/^(\d+)/);
  const numValue = numMatch ? parseInt(numMatch[1]) : 0;
  const prefix = value.replace(/^\d+/, ''); // e.g. "50+" → prefix "+"

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !hasAnimated.current) {
          hasAnimated.current = true;
          const startTime = Date.now();

          const tick = () => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);
            // Ease out cubic
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = Math.round(eased * numValue);
            setDisplay(`${current}${prefix}${suffix}`);

            if (progress < 1) {
              requestAnimationFrame(tick);
            } else {
              setDisplay(value);
            }
          };

          requestAnimationFrame(tick);
        }
      },
      { threshold: 0.3 }
    );

    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [numValue, prefix, suffix, duration, value]);

  return <div ref={ref}>{display}</div>;
}
