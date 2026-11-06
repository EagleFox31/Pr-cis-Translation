// Archive à envoyer aux boutiques : build de production, contenu de dist/ à la racine du ZIP.
import { execFileSync } from "node:child_process";
import { copyFileSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { crc32, deflateRawSync } from "node:zlib";

process.chdir(dirname(fileURLToPath(import.meta.url)));
execFileSync(process.execPath, ["build.mjs", "--prod"], { stdio: "inherit" });

const fichiers = (dossier) =>
  readdirSync(dossier).flatMap((nom) => {
    const chemin = join(dossier, nom);
    return statSync(chemin).isDirectory() ? fichiers(chemin) : [chemin];
  });

// ZIP minimal (méthode deflate, sans dépendance).
const locaux = [];
const centraux = [];
let decalage = 0;
for (const chemin of fichiers("dist").sort()) {
  const nom = Buffer.from(relative("dist", chemin).split("\\").join("/"));
  const brut = readFileSync(chemin);
  const comprime = deflateRawSync(brut, { level: 9 });
  const crc = crc32(brut);
  const entete = Buffer.alloc(30);
  entete.writeUInt32LE(0x04034b50, 0);
  entete.writeUInt16LE(20, 4);
  entete.writeUInt16LE(0x0800, 6); // noms en UTF-8
  entete.writeUInt16LE(8, 8);
  entete.writeUInt32LE(0x00210000, 10); // 01/01/1980 : archive reproductible
  entete.writeUInt32LE(crc, 14);
  entete.writeUInt32LE(comprime.length, 18);
  entete.writeUInt32LE(brut.length, 22);
  entete.writeUInt16LE(nom.length, 26);
  const central = Buffer.alloc(46);
  central.writeUInt32LE(0x02014b50, 0);
  central.writeUInt16LE(20, 4);
  central.writeUInt16LE(20, 6);
  central.writeUInt16LE(0x0800, 8);
  central.writeUInt16LE(8, 10);
  central.writeUInt32LE(0x00210000, 12);
  central.writeUInt32LE(crc, 16);
  central.writeUInt32LE(comprime.length, 20);
  central.writeUInt32LE(brut.length, 24);
  central.writeUInt16LE(nom.length, 28);
  central.writeUInt32LE(decalage, 42);
  locaux.push(entete, nom, comprime);
  centraux.push(central, nom);
  decalage += entete.length + nom.length + comprime.length;
}
const tailleCentrale = centraux.reduce((t, b) => t + b.length, 0);
const fin = Buffer.alloc(22);
fin.writeUInt32LE(0x06054b50, 0);
fin.writeUInt16LE(centraux.length / 2, 8);
fin.writeUInt16LE(centraux.length / 2, 10);
fin.writeUInt32LE(tailleCentrale, 12);
fin.writeUInt32LE(decalage, 16);

const { version } = JSON.parse(readFileSync("dist/manifest.json", "utf8"));
const sortie = `precis-extension-${version}.zip`;
writeFileSync(sortie, Buffer.concat([...locaux, ...centraux, fin]));
console.log(`${sortie} : ${centraux.length / 2} fichiers`);

// Copie servie par le site (/extension) pour l'installation manuelle.
const site = join("..", "frontend", "public", "extension");
mkdirSync(site, { recursive: true });
copyFileSync(sortie, join(site, "precis-extension.zip"));
console.log(`copie : ${join(site, "precis-extension.zip")}`);
