// Identifiant de page pour les bornes du serveur (étude limites-page-extension).
// Un UUID par adresse visitée pendant ce chargement : l'adresse ne quitte pas le navigateur.
export function creerIdPages(alea: () => string = () => crypto.randomUUID()): (adresse: string) => string {
  const ids = new Map<string, string>();
  return (adresse) => {
    let id = ids.get(adresse);
    if (!id) {
      id = alea();
      ids.set(adresse, id);
    }
    return id;
  };
}

const idDe = creerIdPages();

export const idPage = (): string => idDe(location.href);
