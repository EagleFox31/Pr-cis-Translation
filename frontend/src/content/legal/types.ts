export type LegalDoc = {
  slug: 'mentions-legales' | 'conditions' | 'confidentialite' | 'cookies';
  title: string;
  intro: string;
  sections: { heading: string; paragraphs: string[]; list?: string[] }[];
};
