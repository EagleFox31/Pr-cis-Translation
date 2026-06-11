import { useRef, useState } from 'react';

interface RippleButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  style?: React.CSSProperties;
  className?: string;
  disabled?: boolean;
}

export default function RippleButton({
  children,
  onClick,
  style,
  className,
  disabled,
}: RippleButtonProps) {
  const [ripples, setRipples] = useState<Array<{ x: number; y: number; id: number }>>([]);
  const ref = useRef<HTMLButtonElement>(null);
  const idRef = useRef(0);

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    const rect = ref.current?.getBoundingClientRect();
    if (!rect) return;

    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const id = idRef.current++;

    setRipples((prev) => [...prev, { x, y, id }]);
    setTimeout(() => {
      setRipples((prev) => prev.filter((r) => r.id !== id));
    }, 600);

    onClick?.();
  };

  return (
    <button
      ref={ref}
      className={className}
      onClick={handleClick}
      disabled={disabled}
      style={{
        position: 'relative',
        overflow: 'hidden',
        ...style,
      }}
    >
      {children}
      {ripples.map((r) => (
        <span
          key={r.id}
          style={{
            position: 'absolute',
            left: r.x - 10,
            top: r.y - 10,
            width: '20px',
            height: '20px',
            borderRadius: '50%',
            background: 'rgba(255,255,255,0.35)',
            transform: 'scale(0)',
            animation: 'ripple-effect 0.6s ease-out forwards',
            pointerEvents: 'none',
          }}
        />
      ))}
    </button>
  );
}
