/**
 * Le décor de fond : quatre bandes de mots qui défilent en sens alternés.
 *
 * Il occupait SOIXANTE-DIX lignes au milieu de `Home`, entre l'ouverture de la
 * bibliothèque et le rendu des sections — quatre blocs `[1, 2, 3].map(...)`
 * identiques au style près, chacun listant ses mots à la main en `<span>`.
 * Chercher la logique de la page voulait dire traverser un dictionnaire.
 *
 * C'est du CONTENU, pas de la structure : il vit donc dans un tableau, et le
 * composant ne fait que le dérouler.
 *
 * POURQUOI TROIS RÉPÉTITIONS
 * --------------------------
 * L'animation translate la bande de -50 % : il faut donc que la seconde moitié
 * soit identique à la première pour que la boucle ne saute pas. Trois copies
 * couvrent les écrans larges sans laisser de vide en fin de course.
 *
 * Rien à traduire ici — c'est justement la démonstration : les mots restent
 * dans leur langue, c'est tout le propos.
 *
 * DEUX VARIANTES, UN SEUL COMPOSANT
 * ---------------------------------
 * `page` (défaut) — le fond fixe des sections CLAIRES : texte navy à 12 %,
 * couvre tout le défilement. C'est l'usage d'origine.
 *
 * `hero` — le même motif dans l'en-tête, qui a un fond SOMBRE. Le navig y était
 * invisible (navy sur navy) : la variante hero peint donc en BLANC, et plus
 * DISCRÈTEMENT encore (~5 %), pour rester un décor derrière le titre et la
 * démo, jamais un concurrent.
 */
import { Fragment } from 'react';

interface LanguageMarqueeProps {
  variant?: 'page' | 'hero';
}

const BANDES: readonly (readonly string[])[] = [
  ['Translation', 'Traduction', 'Traducción', 'Übersetzung', 'Traduzione',
   'Overzetting', '翻訳', '번역', '翻译', 'ترجمة', 'Перевод'],
  ['Documents', 'Actes', 'Certificats', 'Contrats', 'Diplômes',
   '書類', '문서', '文档', 'عقود', 'Справки'],
  ['Precision', 'Précision', 'Precisión', 'Präzision', 'Precisione',
   'Precisie', '精度', '정밀도', '精确', 'دقة', 'Точность'],
  ['AI & Human', 'IA & Humain', 'IA y Humano', 'KI & Mensch', 'IA & Umano',
   'AI & Mens', 'AI & 人間', 'AI & 인간', 'AI & 人类', 'ذكاء بشري واصطناعي'],
];

const REPETITIONS = 3;

export default function LanguageMarquee({ variant = 'page' }: LanguageMarqueeProps) {
  return (
    // `aria-hidden` : c'est un décor. Sans lui, un lecteur d'écran énonce cent
    // vingt mots sans rapport avant d'atteindre le contenu de la page.
    <div
      className={variant === 'hero' ? 'hero-lang-marquee' : 'page-bg-lang-lines'}
      aria-hidden
    >
      <div className="hero-lang-lines">
        {BANDES.map((mots, bande) => (
          <div
            key={bande}
            className={`lang-line lang-line-${bande % 2 === 0 ? 'left' : 'right'}`}
          >
            {Array.from({ length: REPETITIONS }, (_, n) => (
              <span key={n} className="lang-line__groupe">
                {/* Fragment, et surtout PAS un <span> englobant : le groupe est
                    un `inline-flex` à gouttière de 30 px, et ses enfants directs
                    sont les mots ET les puces. Les emballer par paire ferait
                    onze éléments au lieu de vingt-deux — la puce se collerait à
                    son mot et l'espacement de toute la bande changerait. */}
                {mots.map((mot) => (
                  <Fragment key={mot}>
                    <span>{mot}</span><span>•</span>
                  </Fragment>
                ))}
              </span>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
