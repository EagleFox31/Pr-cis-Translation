// Jetons de la charte du site (frontend/src/index.css, :root), recopiés : les surfaces
// injectées vivent dans un Shadow DOM et ne voient pas les feuilles du site.
// Toute évolution de la charte se reporte ici et dans popup.html.
export const THEME = `
  :host {
    --navy: #0d1b3e;
    --blue: #1a4dc7;
    --blue-bright: #2563eb;
    --gold-light: #f0d98a;
    --white: #ffffff;
    --police: "DM Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  }
  button { font-family: var(--police); }
  button:focus-visible { outline: 2px solid var(--gold-light); outline-offset: 2px; }
`;
