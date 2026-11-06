// Protocole de messages entre popup, content script et background.

export type ErreurConnexion = "identifiants" | "non_verifie" | "indisponible";
export type ErreurSegments = "credits" | "deconnecte" | "indisponible" | "trop";
export type ErreurImage = "credits" | "refusee" | "illisible" | "indisponible" | "deconnecte";

export interface BlocImage {
  texte: string;
  traduction: string;
  boite: [number, number, number, number];
  remplace: boolean;
}

export interface ReponseImage {
  remplacee: boolean;
  pages: number;
  mime: string;
  image: string | null;
  blocs: BlocImage[];
}

// popup / content -> background
export type MsgConnexion = { type: "connexion"; email: string; motDePasse: string };
export type MsgDeconnexion = { type: "deconnexion" };
export type MsgEtat = { type: "etat" };
export type MsgSegments = {
  type: "segments";
  textes: string[];
  langue: string;
  titre: string;
  contexte: string[];
};
export type MsgImage = {
  type: "image";
  langue: string;
  src?: string;
  donnees?: string;
  mime?: string;
  /** Images de vidéo : chaque arrêt sur image est différent, inutile de les garder. */
  sansMemoire?: boolean;
};
export type MsgMemoireEtat = { type: "memoire_etat" };
export type MsgMemoireEffacer = { type: "memoire_effacer" };

export type VersBackground =
  | MsgConnexion
  | MsgDeconnexion
  | MsgEtat
  | MsgSegments
  | MsgImage
  | MsgMemoireEtat
  | MsgMemoireEffacer;

export type ReponseConnexion = { ok: true; email: string } | { ok: false; erreur: ErreurConnexion };
export type ReponseEtat = { connecte: boolean; email?: string };
export type ReponseSegments =
  | { ok: true; traductions: string[] }
  | { ok: false; erreur: ErreurSegments };
export type ReponseImageBg =
  | { ok: true; reponse: ReponseImage }
  | { ok: false; erreur: ErreurImage };
export type ReponseMemoire = { traductions: number };

export interface ReponsesBackground {
  connexion: ReponseConnexion;
  deconnexion: { ok: true };
  etat: ReponseEtat;
  segments: ReponseSegments;
  image: ReponseImageBg;
  memoire_etat: ReponseMemoire;
  memoire_effacer: ReponseMemoire;
}

export type ReponseDe<M extends VersBackground> = ReponsesBackground[M["type"]];

// popup -> content (tous les cadres de l'onglet)
export type MsgTraduire = { type: "traduire"; langue: string };
export type MsgOriginal = { type: "original" };
export type VersContent = MsgTraduire | MsgOriginal;
