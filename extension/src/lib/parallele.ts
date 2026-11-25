/**
 * `n` traitements simultanés sur une file : chacun reprend `prendre()` (le
 * plus prioritaire à cet instant) dès qu'il a fini. `traiter` renvoie vrai
 * pour tout arrêter : les autres finissent leur élément puis s'arrêtent.
 * Une exception dans `traiter` arrête aussi tout, puis est relancée.
 */
export async function enParallele<T>(
  n: number,
  prendre: () => T | undefined,
  traiter: (element: T) => Promise<boolean>,
): Promise<void> {
  let arret = false;
  const travailleur = async (): Promise<void> => {
    while (!arret) {
      const element = prendre();
      if (element === undefined) return;
      try {
        if (await traiter(element)) arret = true;
      } catch (e) {
        arret = true;
        throw e;
      }
    }
  };
  await Promise.all(Array.from({ length: Math.max(1, n) }, travailleur));
}
