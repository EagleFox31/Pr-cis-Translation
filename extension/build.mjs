import { build } from "esbuild";
import { cpSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

process.chdir(dirname(fileURLToPath(import.meta.url)));

rmSync("dist", { recursive: true, force: true });
mkdirSync("dist");

// `--prod` : adresses publiques et manifest sans localhost, prêt pour les boutiques.
const PROD = process.argv.includes("--prod");
const API = PROD ? "https://precis-translator.com" : "http://localhost:8000";
const SITE = PROD ? "https://precis-translator.com" : "http://localhost:3000";

const commun = {
  bundle: true,
  target: "chrome120",
  logLevel: "warning",
  minifySyntax: true, // retire les adresses locales restées en branche morte ; code toujours lisible
  define: { __PRECIS_API__: JSON.stringify(API), __PRECIS_SITE__: JSON.stringify(SITE) },
};

await build({ ...commun, entryPoints: ["src/background.ts"], format: "esm", outfile: "dist/background.js" });
await build({ ...commun, entryPoints: ["src/content.ts", "src/popup.ts"], format: "iife", outdir: "dist" });

const manifest = JSON.parse(readFileSync("manifest.json", "utf8"));
if (PROD) {
  manifest.host_permissions = manifest.host_permissions.filter((h) => !h.includes("localhost"));
  manifest.externally_connectable = { matches: [`${SITE}/*`] };
}
writeFileSync("dist/manifest.json", JSON.stringify(manifest, null, 2) + "\n");
cpSync("assets/icones", "dist/icones", { recursive: true });
cpSync("src/popup.html", "dist/popup.html");
cpSync("assets/logo.png", "dist/logo.png");

// Polices de la fenêtre, embarquées : aucune requête vers un service tiers.
mkdirSync("dist/polices");
for (const fichier of [
  "dm-sans/files/dm-sans-latin-400-normal.woff2",
  "dm-sans/files/dm-sans-latin-500-normal.woff2",
  "dm-sans/files/dm-sans-latin-600-normal.woff2",
  "pinyon-script/files/pinyon-script-latin-400-normal.woff2",
]) {
  cpSync(`node_modules/@fontsource/${fichier}`, `dist/polices/${fichier.split("/").pop()}`);
}
