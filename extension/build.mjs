import { build } from "esbuild";
import { cpSync, mkdirSync, rmSync } from "node:fs";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

process.chdir(dirname(fileURLToPath(import.meta.url)));

rmSync("dist", { recursive: true, force: true });
mkdirSync("dist");

const commun = { bundle: true, target: "chrome120", logLevel: "warning" };

await build({ ...commun, entryPoints: ["src/background.ts"], format: "esm", outfile: "dist/background.js" });
await build({ ...commun, entryPoints: ["src/content.ts", "src/popup.ts"], format: "iife", outdir: "dist" });

cpSync("manifest.json", "dist/manifest.json");
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
