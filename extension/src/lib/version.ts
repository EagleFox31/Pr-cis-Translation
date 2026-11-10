// Comparaison de versions « 1.2.3 » (manifest Chrome : 1 à 4 nombres).
export function plusRecente(distante: string, locale: string): boolean {
  const a = distante.split(".").map(Number);
  const b = locale.split(".").map(Number);
  if ([...a, ...b].some((n) => !Number.isInteger(n) || n < 0)) return false;
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    const x = a[i] ?? 0;
    const y = b[i] ?? 0;
    if (x !== y) return x > y;
  }
  return false;
}
