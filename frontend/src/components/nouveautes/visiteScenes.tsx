import type { CSSProperties } from 'react';
import { useTranslation } from 'react-i18next';

type Lang = 'fr' | 'en' | 'es' | 'de';

interface TxProps {
  /** Texte du document dans chaque langue (contenu de la scène : jamais traduit par l'interface). */
  l: Partial<Record<Lang, string>>;
  /** Langue affichée au départ. */
  init?: Lang;
  className?: string;
  style?: CSSProperties;
}

/** Texte de scène : la langue affichée est changée par l'animation (`useVisite`). */
function Tx({ l, init = 'fr', className = 'vst-t', style }: TxProps) {
  return (
    <span
      className={className}
      style={style}
      data-fr={l.fr} data-en={l.en} data-es={l.es} data-de={l.de}
    >
      {l[init]}
    </span>
  );
}

const SVG_ILLU = { width: 200, height: 112 };

/** Photo d'un luminaire, identique sur l'original et la traduction. */
function Luminaires() {
  return (
    <svg viewBox={`0 0 ${SVG_ILLU.width} ${SVG_ILLU.height}`} preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <rect width="200" height="112" fill="#e9dcc0" />
      <rect y="88" width="200" height="24" fill="#b88f4a" />
      <rect y="88" width="200" height="3" fill="#9c7638" />
      <path d="M60 0 V34 M140 0 V22" stroke="#3a3326" strokeWidth="1.5" />
      <path d="M60 38 L48 88 H72 Z M140 26 L126 88 H154 Z" fill="#fff6dc" opacity=".55" />
      <path d="M42 50 Q60 26 78 50 Z" fill="#0d1b3e" />
      <path d="M120 38 Q140 10 160 38 Z" fill="#c9a84c" />
      <circle cx="60" cy="51" r="4" fill="#fff6dc" />
      <circle cx="140" cy="39" r="4" fill="#fff6dc" />
      <rect x="88" y="66" width="10" height="22" rx="4" fill="#5b6f5a" />
      <path d="M93 66 C90 56 84 52 80 50 M93 66 C96 56 102 52 106 50" stroke="#4d7a52" strokeWidth="2" fill="none" />
    </svg>
  );
}

const Curseur = () => (
  <svg className="vst-cur"><use href="#vst-cur" /></svg>
);

/**
 * Les cinq scènes (illustration de gauche). Tout est monté d'emblée ; seule
 * la diapositive courante est visible et animée. Les puces d'interface sont
 * traduites ; le contenu des documents ne l'est jamais.
 */
export default function VisiteScenes({ courant }: { courant: number }) {
  const { t } = useTranslation();
  const s = (cle: string) => t(`nouveautes.visite.scene.${cle}`);
  const on = (n: number) => `vst-slot${courant === n ? ' vst-on' : ''}`;

  return (
    <>
      <svg width="0" height="0" style={{ position: 'absolute' }} aria-hidden="true">
        <symbol id="vst-cur" viewBox="0 0 24 24">
          <path d="M4 2l15 11-7 1-3 7z" fill="#fff" stroke="#0d1b3e" strokeWidth="1.6" strokeLinejoin="round" />
        </symbol>
      </svg>

      {/* 1 — Traduction */}
      <div className={on(0)}><div className="vst-scene vst-s1">
        <div className="vst-file"><i>PDF</i>rapport-annuel.pdf</div>
        <div className="vst-paper vst-page">
          <span className="vst-sweep" />
          <h4><Tx l={{ fr: 'Rapport annuel 2025', en: 'Annual Report 2025', es: 'Informe anual 2025', de: 'Jahresbericht 2025' }} /></h4>
          <p><Tx l={{ fr: 'Une croissance portée par nos nouveaux marchés, en Europe comme en Afrique.', en: 'Growth driven by our new markets, in Europe and in Africa alike.', es: 'Un crecimiento impulsado por nuestros nuevos mercados, en Europa y en África.', de: 'Wachstum dank unserer neuen Märkte, in Europa wie in Afrika.' }} /></p>
          <table>
            <tbody>
              <tr>
                <th><Tx l={{ fr: 'Région', en: 'Region', es: 'Región', de: 'Region' }} /></th>
                <th><Tx l={{ fr: 'Ventes', en: 'Sales', es: 'Ventas', de: 'Umsatz' }} /></th>
              </tr>
              <tr><td><Tx l={{ fr: 'Europe', en: 'Europe', es: 'Europa', de: 'Europa' }} /></td><td>42 %</td></tr>
              <tr><td><Tx l={{ fr: 'Afrique', en: 'Africa', es: 'África', de: 'Afrika' }} /></td><td>31 %</td></tr>
            </tbody>
          </table>
          <div className="vst-fig">
            <div className="vst-bars"><i style={{ height: '38%' }} /><i style={{ height: '62%' }} /><i style={{ height: '90%' }} /></div>
            <Tx l={{ fr: 'Figure 1 — Croissance par région', en: 'Figure 1 — Growth by region', es: 'Figura 1 — Crecimiento por región', de: 'Abbildung 1 — Wachstum nach Region' }} />
          </div>
        </div>
        <span className="vst-lp">FR</span>
        <span className="vst-chip vst-gold vst-keep">{s('keep')}</span>
      </div></div>

      {/* 2 — Scans et images */}
      <div className={on(1)}><div className="vst-scene vst-s2">
        <div className="vst-paper vst-scan">
          <span className="vst-sweep" />
          <h4><Tx l={{ fr: 'Schéma de l’installation', en: 'Installation diagram', es: 'Esquema de la instalación', de: 'Anlagenschema' }} /></h4>
          <div className="vst-sub">SCAN_0042.JPG · 300 DPI</div>
          <div className="vst-dia">
            <svg viewBox="0 0 358 270" fill="none" stroke="#2b2a26" strokeWidth="2">
              <rect x="14" y="70" width="70" height="110" rx="6" />
              <path d="M14 120h70" strokeDasharray="4 4" />
              <path d="M84 150h70" />
              <circle cx="180" cy="150" r="26" />
              <path d="M168 138l24 12-24 12z" fill="#2b2a26" />
              <path d="M206 150h50" />
              <path d="M256 136v28l30-28v28z" />
              <path d="M286 150h60" />
              <path d="M340 140l10 10-10 10" />
              <path d="M180 124V70h80" />
              <circle cx="276" cy="70" r="15" />
              <path d="M276 70l8-7" />
            </svg>
            <Tx className="vst-lbl vst-t" style={{ left: 4, top: 194 }} l={{ fr: 'Réservoir', en: 'Tank', es: 'Depósito', de: 'Behälter' }} />
            <Tx className="vst-lbl vst-t" style={{ left: 150, top: 190 }} l={{ fr: 'Pompe', en: 'Pump', es: 'Bomba', de: 'Pumpe' }} />
            <Tx className="vst-lbl vst-t" style={{ left: 244, top: 180 }} l={{ fr: 'Vanne', en: 'Valve', es: 'Válvula', de: 'Ventil' }} />
            <Tx className="vst-lbl vst-t" style={{ left: 206, top: 26 }} l={{ fr: 'Manomètre', en: 'Pressure gauge', es: 'Manómetro', de: 'Manometer' }} />
          </div>
          <div className="vst-note"><Tx l={{ fr: 'Pression max. : 6 bar — vérifier chaque mois', en: 'Max. pressure: 6 bar — check monthly', es: 'Presión máx.: 6 bar — revisar cada mes', de: 'Max. Druck: 6 bar — monatlich prüfen' }} /></div>
        </div>
        <span className="vst-lp">FR</span>
        <span className="vst-chip vst-white vst-found">{s('found')}</span>
      </div></div>

      {/* 3 — Extension */}
      <div className={on(2)}><div className="vst-scene vst-s3">
        <span className="vst-lp">EN</span>
        <div className="vst-paper vst-win">
          <div className="vst-bar"><b /><b /><b /><span className="vst-url">globalnews.com/climate</span><span className="vst-ext">P</span></div>
          <div className="vst-art">
            <div>
              <small><Tx init="en" l={{ en: 'Environment', fr: 'Environnement' }} /></small>
              <h4><Tx init="en" l={{ en: 'Climate summit reaches a historic agreement', fr: 'Le sommet sur le climat aboutit à un accord historique' }} /></h4>
              <p><Tx init="en" l={{ en: 'Delegates from 190 countries agreed on new targets to cut emissions by 2035.', fr: 'Les délégués de 190 pays ont adopté de nouveaux objectifs de réduction des émissions d’ici 2035.' }} /></p>
            </div>
            <div className="vst-img">
              <svg viewBox="0 0 150 170" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
                <defs>
                  <linearGradient id="vst-sky3" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0" stopColor="#e8743b" />
                    <stop offset=".6" stopColor="#f6c27a" />
                  </linearGradient>
                </defs>
                <rect width="150" height="170" fill="url(#vst-sky3)" />
                <circle cx="104" cy="44" r="17" fill="#fff1c9" />
                <path d="M0 104 L34 70 L52 86 L78 56 L112 92 L132 78 L150 92 V170 H0Z" fill="#7b5a4a" />
                <path d="M78 56 L88 67 L82 66 L76 72 L70 64Z M34 70 L41 77 L36 76 L30 79Z" fill="#fff" />
                <path d="M0 118 C30 112 60 124 90 116 C115 110 135 118 150 114 V170 H0Z" fill="#2f6fae" />
                <path d="M14 128 h22 M58 134 h30 M104 126 h24" stroke="#9cc3e6" strokeWidth="2" strokeLinecap="round" />
              </svg>
              <Tx init="en" className="vst-cap vst-ti" l={{ en: 'Global warming limit: +1.5 °C', fr: 'Limite du réchauffement : +1,5 °C' }} />
            </div>
          </div>
          <div className="vst-pop"><b>Précis</b>{s('popup_text')}<div className="vst-sel">{s('popup_lang')}</div><div className="vst-go">{s('popup_go')}</div></div>
        </div>
        <span className="vst-chip vst-gold vst-imgok">{s('image_ok')}</span>
        <span className="vst-chip vst-gold vst-quota">{s('quota')}</span>
        <Curseur />
      </div></div>

      {/* 4 — API */}
      <div className={on(3)}><div className="vst-scene vst-s4">
        <div className="vst-code">
          <header>{s('app')}</header>
          <div className="vst-ln vst-a"><span className="vst-k">POST</span> /documents</div>
          <div className="vst-ln vst-a">fichier: <span className="vst-s">"contrat.pdf"</span></div>
          <div className="vst-ln vst-a">langue: <span className="vst-s">"de"</span></div>
          <div className="vst-ln vst-r">→ <span className="vst-k">200</span> statut: <span className="vst-s">"traduit"</span></div>
        </div>
        <div className="vst-wire"><i /></div>
        <div className="vst-node">P</div><div className="vst-lab">PRÉCIS</div>
        <div className="vst-paper vst-doc">
          <h5><Tx l={{ fr: 'Contrat de prestation', de: 'Dienstleistungs­vertrag' }} /></h5>
          <i /><i style={{ width: '85%' }} /><i /><i style={{ width: '70%' }} /><i /><i style={{ width: '60%' }} />
          <div className="vst-sig">
            <Tx l={{ fr: 'Le client', de: 'Der Kunde' }} />
            <Tx l={{ fr: 'Le prestataire', de: 'Der Anbieter' }} />
          </div>
        </div>
        <div className="vst-fname">contrat-de.pdf · FR → <span style={{ color: 'var(--gold-light)' }}>DE</span></div>
        <span className="vst-chip vst-gold vst-soonc">{s('soon')}</span>
      </div></div>

      {/* 5 — Visionneuse */}
      <div className={on(4)}><div className="vst-scene vst-s5">
        <div className="vst-vw">
          <div className="vst-tb"><span>‹ {s('page')} ›</span><span>{s('zoom')}</span></div>
          <div className="vst-heads"><span>{s('original')}</span><span>{s('translation')}</span></div>
          <div className="vst-pages">
            <div className="vst-paper vst-pp">
              <div className="vst-logo">Maison Lumière</div>
              <h5>Notre collection</h5>
              <p>Des luminaires dessinés et fabriqués à la main, dans notre atelier lyonnais.</p>
              <div className="vst-ph"><Luminaires /></div>
            </div>
            <div className="vst-paper vst-pp vst-tr">
              <div className="vst-logo"><Tx init="en" className="vst-ti" l={{ en: 'House of Light', fr: 'Maison Lumière' }} /></div>
              <h5>Our collection</h5>
              <p>Lamps designed and handmade in our Lyon workshop.<span className="vst-caret" /></p>
              <div className="vst-ph"><Luminaires /></div>
              <span className="vst-chip vst-white vst-tool">{s('restore')}</span>
              <span className="vst-chip vst-gold vst-okc">{s('restored')}</span>
              <span className="vst-chip vst-white vst-edit">{s('edit')}</span>
            </div>
          </div>
        </div>
        <Curseur />
      </div></div>
    </>
  );
}
