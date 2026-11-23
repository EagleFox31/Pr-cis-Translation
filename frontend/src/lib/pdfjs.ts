// pdf.js (≈ 300 Ko) n'est chargé qu'au premier besoin, et plus en <script>
// bloquant dans <head> : il retardait le premier affichage de toutes les pages.
const BASE = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.16.105/';
let chargement: Promise<any> | null = null;

export function chargerPdfjs(): Promise<any> {
  const w = window as any;
  if (w.pdfjsLib) return Promise.resolve(w.pdfjsLib);
  if (!chargement) {
    chargement = new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = BASE + 'pdf.min.js';
      s.async = true;
      const echec = () => {
        chargement = null;
        console.error('PDF.js non chargé');
        reject(new Error('PDF.js non chargé'));
      };
      s.onload = () => {
        if (!w.pdfjsLib?.GlobalWorkerOptions) { echec(); return; }
        w.pdfjsLib.GlobalWorkerOptions.workerSrc = BASE + 'pdf.worker.min.js';
        resolve(w.pdfjsLib);
      };
      s.onerror = echec;
      document.head.appendChild(s);
    });
  }
  return chargement;
}
