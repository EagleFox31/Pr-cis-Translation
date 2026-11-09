// Prérendu des pages publiques, lancé après `vite build`.
//
// Source unique : `seo/site.json`. Pour chaque page publique, ce script écrit
// `dist/<chemin>.html` avec un <head> propre (titre, description, canonical,
// Open Graph, JSON-LD) et un contenu lisible sans JavaScript dans #root. React
// remplace ce contenu au démarrage. Il génère aussi `sitemap.xml` et `llms.txt`
// à partir de la même liste, pour que les trois ne puissent pas diverger.
//
// Idempotent : relancé sur le même `dist`, il produit les mêmes fichiers.

import { readFile, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const DIST = resolve(ROOT, process.argv[2] ?? "dist");

const site = JSON.parse(await readFile(join(ROOT, 'seo/site.json'), 'utf8'));
const i18n = JSON.parse(await readFile(join(ROOT, 'src/locales/fr/translation.json'), 'utf8'));
const legal = await importTs(join(ROOT, 'src/content/legal/fr.ts'));
const template = await readFile(join(DIST, 'index.html'), 'utf8');

const MAIN_STYLE =
  'max-width:960px;margin:4rem auto;padding:2rem;font-family:system-ui,sans-serif;line-height:1.7;color:#12213a';
const NAV_START = '<!-- seo:public-nav -->';
const NAV_END = '<!-- /seo:public-nav -->';

async function importTs(file) {
  try {
    return await import(pathToFileURL(file).href);
  } catch (error) {
    if (error?.code === 'ERR_UNKNOWN_FILE_EXTENSION') {
      throw new Error(
        `Node ${process.version} ne sait pas charger ${file}. ` +
          'Le prérendu exige Node 22.18 ou plus récent (types TypeScript retirés nativement).',
      );
    }
    throw error;
  }
}

const esc = (s) =>
  String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

const url = (path) => site.origin + path;

function clip(text, max = 160) {
  const clean = text.replace(/\s+/g, ' ').trim();
  if (clean.length <= max) return clean;
  const cut = clean.slice(0, max - 1);
  return cut.slice(0, cut.lastIndexOf(' ')) + '…';
}

const MONTHS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août',
  'septembre', 'octobre', 'novembre', 'décembre'];

function isoDate(french) {
  const m = /^(\d{1,2}) (\S+) (\d{4})$/.exec(french ?? '');
  const month = m ? MONTHS.indexOf(m[2]) + 1 : 0;
  if (!month) throw new Error(`Date de mise à jour illisible : « ${french} »`);
  return `${m[3]}-${String(month).padStart(2, '0')}-${m[1].padStart(2, '0')}`;
}

function replaceOnce(html, pattern, replacement, what) {
  if (!pattern.test(html)) throw new Error(`Gabarit dist/index.html : ${what} introuvable.`);
  return html.replace(pattern, replacement);
}

function meta(html, attr, key, value) {
  const pattern = new RegExp(`<meta ${attr}="${key}" content="[^"]*"\\s*/?>`);
  return replaceOnce(html, pattern, `<meta ${attr}="${key}" content="${esc(value)}" />`, `meta ${key}`);
}

function readMeta(html, attr, key) {
  const m = new RegExp(`<meta ${attr}="${key}" content="([^"]*)"`).exec(html);
  if (!m) throw new Error(`Gabarit dist/index.html : meta ${key} introuvable.`);
  return m[1].replace(/&quot;/g, '"').replace(/&amp;/g, '&');
}

const JSONLD = /<script type="application\/ld\+json">([\s\S]*?)<\/script>/;
const baseGraph = JSON.parse(JSONLD.exec(template)?.[1] ?? 'null')?.['@graph'];
if (!baseGraph) throw new Error('Gabarit dist/index.html : JSON-LD @graph introuvable.');
const sharedNodes = baseGraph.filter((n) => ['Organization', 'WebSite'].includes(n['@type']));
const websiteId = sharedNodes.find((n) => n['@type'] === 'WebSite')?.['@id'];

const legalBySlug = new Map(legal.LEGAL_FR.map((doc) => [doc.slug, doc]));
const legalUpdated = isoDate(legal.LEGAL_UPDATED);
const ext = i18n.extension_page;
const faqPairs = Object.keys(ext.faq)
  .filter((k) => k.endsWith('_q') && ext.faq[k.replace(/_q$/, '_a')])
  .map((k) => ({ q: ext.faq[k], a: ext.faq[k.replace(/_q$/, '_a')] }));

// ── Contenu de chaque page ──────────────────────────────────────────────────
function describe(route) {
  if (route.source === 'home') {
    return {
      label: 'Accueil',
      title: /<title>([^<]*)<\/title>/.exec(template)?.[1],
      description: readMeta(template, 'name', 'description'),
    };
  }
  if (route.source === 'extension') {
    const steps = ['add', 'pin', 'use']
      .map((k) => `<li><strong>${esc(ext.how[`${k}_title`])}</strong> : ${esc(ext.how[`${k}_text`])}</li>`)
      .join('');
    const perms = ['storage', 'tab', 'sites', 'send', 'sale']
      .map((k) => `<li>${esc(ext.permissions[k])}</li>`)
      .join('');
    const faq = faqPairs.map(({ q, a }) => `<h3>${esc(q)}</h3><p>${esc(a)}</p>`).join('');
    return {
      label: ext.footer_link,
      title: route.title,
      description: route.description,
      body:
        `<h1>${esc(ext.title)}</h1><p>${esc(ext.lead)}</p>` +
        `<h2>${esc(ext.how.title)}</h2><ol>${steps}</ol>` +
        `<h2>${esc(ext.permissions.title)}</h2><ul>${perms}</ul>` +
        `<h2>${esc(ext.faq.title)}</h2>${faq}`,
      extraNodes: [
        {
          '@type': 'FAQPage',
          '@id': url(route.path) + '#faq',
          mainEntity: faqPairs.map(({ q, a }) => ({
            '@type': 'Question',
            name: q,
            acceptedAnswer: { '@type': 'Answer', text: a },
          })),
        },
      ],
    };
  }
  if (route.source === 'legal') {
    const doc = legalBySlug.get(route.slug);
    if (!doc) throw new Error(`Document légal inconnu : ${route.slug}`);
    const sections = doc.sections
      .map(
        (s) =>
          `<h2>${esc(s.heading)}</h2>` +
          s.paragraphs.map((p) => `<p>${esc(p)}</p>`).join('') +
          (s.list ? `<ul>${s.list.map((li) => `<li>${esc(li)}</li>`).join('')}</ul>` : ''),
      )
      .join('');
    return {
      label: doc.title,
      title: `${doc.title} · ${site.name}`,
      description: clip(doc.intro),
      dateModified: legalUpdated,
      body:
        `<h1>${esc(doc.title)}</h1><p>Mise à jour : ${esc(legal.LEGAL_UPDATED)}</p>` +
        `<p>${esc(doc.intro)}</p>${sections}`,
    };
  }
  if (route.source === 'content') return describeContent(route, contentBySlug.get(route.page));
  throw new Error(`Source inconnue pour ${route.path} : ${route.source}`);
}

// ── Pages éditoriales (`seo/pages/<page>.json`) ─────────────────────────────
// Aucune route React ne leur correspond : elles sont servies en HTML statique,
// sans le bundle de l'application, sinon React remplacerait leur contenu par
// une page introuvable.
const contentBySlug = new Map();
for (const route of site.routes.filter((r) => r.source === 'content')) {
  contentBySlug.set(route.page, JSON.parse(await readFile(join(ROOT, `seo/pages/${route.page}.json`), 'utf8')));
}

function money(minor, currency) {
  const decimals = currency === 'XAF' ? 0 : 2;
  const value = (minor / 10 ** decimals).toLocaleString('fr-FR', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).replace(/ | /g, ' ');
  return `${value} ${{ XAF: 'FCFA', EUR: '€', USD: '$' }[currency]}`;
}

function pricingTable(pricing) {
  const head = ['Zone', 'Gratuit', 'Starter', 'Pro', 'Page à l’unité'];
  const rows = pricing.zones.map((z) => [
    z.name,
    `${pricing.monthly_pages.free} pages/mois`,
    `${money(z.starter.monthly, z.currency)}/mois (${money(z.starter.annual, z.currency)} en annuel) · ${pricing.monthly_pages.starter} pages`,
    `${money(z.pro.monthly, z.currency)}/mois (${money(z.pro.annual, z.currency)} en annuel) · ${pricing.monthly_pages.pro} pages`,
    money(z.page, z.currency),
  ]);
  return { caption: pricing.caption, head, rows };
}

function renderSection(s) {
  const tag = s.ordered ? 'ol' : 'ul';
  return (
    (s.heading ? `<h2>${esc(s.heading)}</h2>` : '') +
    (s.paragraphs ?? []).map((p) => `<p>${esc(p)}</p>`).join('') +
    (s.list ? `<${tag}>${s.list.map((li) => `<li>${esc(li)}</li>`).join('')}</${tag}>` : '') +
    (s.links ? `<ul>${s.links.map((l) => `<li><a href="${esc(l.href)}">${esc(l.label)}</a></li>`).join('')}</ul>` : '')
  );
}

function renderTable(t) {
  return (
    `<table><caption>${esc(t.caption)}</caption>` +
    `<thead><tr>${t.head.map((h) => `<th scope="col">${esc(h)}</th>`).join('')}</tr></thead><tbody>` +
    t.rows.map((r) => `<tr><th scope="row">${esc(r[0])}</th>${r.slice(1).map((c) => `<td>${esc(c)}</td>`).join('')}</tr>`).join('') +
    '</tbody></table>'
  );
}

function describeContent(route, c) {
  if (!c) throw new Error(`seo/pages/${route.page}.json introuvable pour ${route.path}.`);
  for (const key of ['label', 'title', 'description', 'h1', 'answer', 'verified']) {
    if (!c[key]) throw new Error(`seo/pages/${route.page}.json : champ « ${key} » manquant.`);
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(c.verified)) throw new Error(`seo/pages/${route.page}.json : « verified » doit être AAAA-MM-JJ.`);
  const sections = (c.sections ?? []).map((s) => {
    if (typeof s === 'string') {
      const block = site.blocks?.[s];
      if (!block) throw new Error(`seo/pages/${route.page}.json : bloc partagé « ${s} » inconnu.`);
      return block;
    }
    return s;
  });
  const tables = [...(c.table ? [c.table] : []), ...(c.pricing ? [pricingTable(c.pricing)] : [])];
  const faq = c.faq ?? [];
  const cta = `<p><a class="cta" href="${esc(site.cta.href)}">${esc(site.cta.label)}</a></p>`;
  return {
    label: c.label,
    title: c.title,
    description: c.description,
    dateModified: c.verified,
    standalone: true,
    body:
      `<h1>${esc(c.h1)}</h1><p class="answer">${esc(c.answer)}</p>${cta}` +
      tables.map(renderTable).join('') +
      sections.map(renderSection).join('') +
      (faq.length ? `<h2>Questions fréquentes</h2>${faq.map(({ q, a }) => `<h3>${esc(q)}</h3><p>${esc(a)}</p>`).join('')}` : '') +
      (c.sources?.length
        ? `<h2>Sources</h2><ul>${c.sources.map((s) => `<li><a href="${esc(s.url)}" rel="nofollow noopener">${esc(s.label)}</a></li>`).join('')}</ul>`
        : '') +
      `<p><small>Informations vérifiées le ${esc(frenchDate(c.verified))}.</small></p>${cta}`,
    extraNodes: faq.length
      ? [
          {
            '@type': 'FAQPage',
            '@id': url(route.path) + '#faq',
            mainEntity: faq.map(({ q, a }) => ({ '@type': 'Question', name: q, acceptedAnswer: { '@type': 'Answer', text: a } })),
          },
        ]
      : [],
    faq,
  };
}

function frenchDate(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  return `${d} ${MONTHS[m - 1]} ${y}`;
}

const pages = site.routes.map((route) => ({ route, ...describe(route) }));

const publicNav =
  `${NAV_START}<nav aria-label="Pages publiques">` +
  pages.map((p) => `<a href="${p.route.path}">${esc(p.label)}</a>`).join(' · ') +
  `</nav>${NAV_END}`;

function withNav(html) {
  const cleaned = html.replace(new RegExp(`${NAV_START}[\\s\\S]*?${NAV_END}`), '');
  return replaceOnce(cleaned, /<\/main>(\s*<\/div>)/, `${publicNav}</main>$1`, 'fin du <main> statique');
}

function render(page) {
  const { route } = page;
  const pageUrl = url(route.path);
  let html = template;
  html = replaceOnce(html, /<title>[^<]*<\/title>/, `<title>${esc(page.title)}</title>`, '<title>');
  html = meta(html, 'name', 'description', page.description);
  html = replaceOnce(html, /<link rel="canonical" href="[^"]*"\s*\/?>/, `<link rel="canonical" href="${pageUrl}" />`, 'canonical');
  html = meta(html, 'property', 'og:url', pageUrl);
  html = meta(html, 'property', 'og:title', page.title);
  html = meta(html, 'property', 'og:description', page.description);
  html = meta(html, 'name', 'twitter:title', page.title);
  html = meta(html, 'name', 'twitter:description', page.description);

  const home = pages[0];
  const graph = [
    ...sharedNodes,
    {
      '@type': 'WebPage',
      '@id': pageUrl + '#webpage',
      url: pageUrl,
      name: page.title,
      description: page.description,
      inLanguage: 'fr',
      ...(websiteId && { isPartOf: { '@id': websiteId } }),
      ...(page.dateModified && { dateModified: page.dateModified }),
    },
    {
      '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: home.label, item: url(home.route.path) },
        { '@type': 'ListItem', position: 2, name: page.label, item: pageUrl },
      ],
    },
    ...(page.extraNodes ?? []),
  ];
  const jsonld = JSON.stringify({ '@context': 'https://schema.org', '@graph': graph }).replace(/</g, '\\u003c');
  html = replaceOnce(html, JSONLD, `<script type="application/ld+json">${jsonld}</script>`, 'JSON-LD');

  const main =
    `<main style="${MAIN_STYLE}">` +
    `<p><a href="${home.route.path}">${esc(site.name)}</a> · ${esc(site.publisher)}</p>` +
    `${page.body}</main>`;
  html = replaceOnce(html, /<main[\s\S]*?<\/main>/, main, '<main> statique');
  return withNav(page.standalone ? standalone(html) : html);
}

// Page sans application : on retire le bundle, ses feuilles de style et le
// script qui masque le contenu statique ; il reste le <head> SEO et le texte.
const STANDALONE_STYLE =
  '<style>body{margin:0;background:#fff}table{border-collapse:collapse;width:100%;margin:1.5rem 0;font-size:.95rem}' +
  'caption{text-align:left;font-weight:600;margin-bottom:.5rem;position:sticky;left:0;max-width:calc(100vw - 2rem)}th,td{border:1px solid #d6dbe4;padding:.5rem;vertical-align:top;text-align:left}' +
  'thead th{background:#f3f5f9}.answer{font-size:1.15rem}.cta{display:inline-block;background:#12213a;color:#fff;padding:.7rem 1.2rem;border-radius:6px;text-decoration:none}' +
  'nav{margin-top:3rem;font-size:.9rem}@media (max-width:640px){main{margin:1rem auto!important;padding:1rem!important}table{display:block;overflow-x:auto}}</style>';

function standalone(html) {
  const stripped = html
    .replace(/<script(?![^>]*application\/ld\+json)[^>]*>[\s\S]*?<\/script>\s*/g, '')
    .replace(/<link rel="(?:stylesheet|preconnect|modulepreload)"[^>]*>\s*/g, '')
    .replace(/<link href="[^"]*" rel="stylesheet"[^>]*>\s*/g, '')
    .replace(/<link rel="stylesheet"[^>]*>\s*/g, '')
    .replace(/<style>[\s\S]*?<\/style>\s*/g, '');
  if (/<script(?![^>]*application\/ld\+json)/.test(stripped) || /rel="stylesheet"/.test(stripped)) {
    throw new Error('Page statique : un script ou une feuille de style de l’application subsiste.');
  }
  return replaceOnce(stripped, /<\/head>/, `${STANDALONE_STYLE}</head>`, '</head>');
}

// ── Écriture ────────────────────────────────────────────────────────────────
if (pages[0].route.source !== 'home') throw new Error('seo/site.json : la première route doit être la page d’accueil.');
const canonical = /<link rel="canonical" href="([^"]*)"/.exec(template)?.[1];
if (canonical !== url(pages[0].route.path)) {
  throw new Error(`index.html déclare le canonical ${canonical}, seo/site.json attend ${url(pages[0].route.path)}.`);
}

await writeFile(join(DIST, 'index.html'), withNav(template));
for (const page of pages.slice(1)) {
  await writeFile(join(DIST, `${page.route.path.slice(1)}.html`), render(page));
}

const sitemap =
  '<?xml version="1.0" encoding="UTF-8"?>\n' +
  '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
  pages
    .map(
      (p) =>
        `  <url><loc>${url(p.route.path)}</loc>` +
        (p.dateModified ? `<lastmod>${p.dateModified}</lastmod>` : '') +
        (p.route.changefreq ? `<changefreq>${p.route.changefreq}</changefreq>` : '') +
        (p.route.priority ? `<priority>${p.route.priority}</priority>` : '') +
        '</url>',
    )
    .join('\n') +
  '\n</urlset>\n';
await writeFile(join(DIST, 'sitemap.xml'), sitemap);

const line = (p) => `- [${p.label}](${url(p.route.path)}): ${p.description}`;
const llms =
  `# ${site.name}\n\n> ${site.summary}\n\n` +
  site.facts.map((f) => `- ${f}`).join('\n') +
  '\n\n## Pages\n\n' +
  pages.filter((p) => !['legal', 'content'].includes(p.route.source)).map(line).join('\n') +
  '\n\n## Guides, tarifs et comparatif\n\n' +
  pages.filter((p) => p.route.source === 'content').map(line).join('\n') +
  '\n\n## Questions fréquentes (extension navigateur)\n\n' +
  faqPairs.map(({ q, a }) => `- ${q} ${a}`).join('\n') +
  '\n\n## Informations légales\n\n' +
  pages.filter((p) => p.route.source === 'legal').map(line).join('\n') +
  '\n';
await writeFile(join(DIST, 'llms.txt'), llms);

console.log(`Prérendu : ${pages.length} pages publiques, sitemap.xml et llms.txt écrits dans ${DIST}.`);
