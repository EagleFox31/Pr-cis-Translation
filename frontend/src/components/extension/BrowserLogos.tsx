// Logos simplifiés des navigateurs pris en charge, pour les cartes d'installation.

type Props = { size?: number };

export function ChromeLogo({ size = 48 }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" aria-hidden="true" focusable="false">
      <path d="M50 50 L8.43 26 A48 48 0 0 1 91.57 26 Z" fill="#DB4437" />
      <path d="M50 50 L91.57 26 A48 48 0 0 1 50 98 Z" fill="#F4B400" />
      <path d="M50 50 L50 98 A48 48 0 0 1 8.43 26 Z" fill="#0F9D58" />
      <circle cx="50" cy="50" r="22" fill="#fff" />
      <circle cx="50" cy="50" r="17" fill="#4285F4" />
    </svg>
  );
}

export function EdgeLogo({ size = 48 }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="edge-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#0C59A4" />
          <stop offset="0.5" stopColor="#2FB5D8" />
          <stop offset="1" stopColor="#5AD36B" />
        </linearGradient>
      </defs>
      <circle cx="50" cy="50" r="48" fill="url(#edge-g)" />
      <path d="M10 60 C14 88 50 100 76 84 C52 90 30 78 32 58 Z" fill="#0A3F87" />
      <ellipse cx="57" cy="55" rx="19" ry="13" fill="#fff" />
    </svg>
  );
}
