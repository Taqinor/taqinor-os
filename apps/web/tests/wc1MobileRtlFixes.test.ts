// WC1 — verification pass (2026-07-05) locking in the 2026-07-04 mobile/RTL
// fixes that previously had no guard test: header overflow at 375px (top-bar
// CTA hidden below `xl`), the Arabic wordmark rendering "TAQINOR" and never
// "ROTAQIN" (dir="ltr" + unicode-bidi:isolate escape hatch), the WhatsApp SVG
// glyph excluded from the generic RTL chevron-mirror rule (a filled brand
// glyph must never be flipped like a directional chevron), and the compact
// globe language dropdown replacing three inline chips on mobile. Lecture
// SOURCE en texte, sans build (même convention que rtlToggleWJ17.test.ts /
// mobilePerfWJ18.test.ts) : ces fixes de mise en page ne sont pas facilement
// montables sous vitest — on verrouille donc les invariants de câblage.
//
// W378 (26/08) — le seuil bureau↔hamburger est passé de `lg` (1024px) à
// `xl` (1280px) : mesure réelle (getBoundingClientRect en navigateur) montrant
// que la ligne d'en-tête (logo + nav + puces langue + téléphone + CTA) a
// besoin de ~1168px alors que `max-w-6xl` plafonne son contenu à 1120px sur
// TOUT viewport ≥1152px — le téléphone et "À propos" (les deux seuls libellés
// contenant un espace) se repliaient sur 2 lignes sur les résolutions de
// bureau ORDINAIRES, pas seulement une largeur intermédiaire rare. Le panneau
// mobile lui-même (markup/JS, cibles 44px variant="menu") reste inchangé à
// l'octet — seul le seuil qui y bascule a été relevé un cran plus haut.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const root = (rel: string) => fileURLToPath(new URL(rel, import.meta.url));
const read = (rel: string) => readFileSync(root(rel), 'utf-8');

const HEADER = read('../src/components/Header.astro');
const LOGO = read('../src/components/Logo.astro');
const LANGUAGE_SWITCHER = read('../src/components/LanguageSwitcher.astro');
const GLOBAL_CSS = read('../src/styles/global.css');

describe('WC1 — Logo.astro : le mot-marque latin reste "TAQINOR", jamais "ROTAQIN" sous RTL', () => {
  it('la racine du logo force dir="ltr" + unicode-bidi:isolate (échappe au contexte bidi RTL hérité)', () => {
    expect(LOGO).toContain('dir="ltr"');
    expect(LOGO).toContain('unicode-bidi:isolate');
  });

  it('le mot est bien décomposé TAQIN + soleil + R (jamais recomposé/inversé)', () => {
    expect(LOGO).toContain('>TAQIN<');
    expect(LOGO).toContain('>R<');
    expect(LOGO).toContain('aria-label="TAQINOR"');
  });
});

describe('WC1 — Header.astro : le CTA laiton de la barre supérieure ne déborde plus à 375px', () => {
  it('le CTA "cta.primary" de la barre supérieure est masqué sous `xl` (régime hamburger, W378)', () => {
    const ctaBlock = HEADER.slice(HEADER.indexOf("href={L(QUOTE_JOURNEY_PATH)}"));
    expect(ctaBlock.slice(0, 400)).toMatch(/class="glow hidden\b[^"]*xl:inline-block/);
  });

  it('le téléphone de la barre supérieure reste masqué sous `md` (même discipline anti-débordement)', () => {
    expect(HEADER).toMatch(/class="link-underline hidden\b[^"]*md:flex/);
  });
});

describe('WC1 — LanguageSwitcher.astro : menu déroulant globe compact sur mobile', () => {
  it('un <details> compact (variant "bar") rend le menu globe sous `xl` (W378), jamais de JS requis', () => {
    expect(LANGUAGE_SWITCHER).toContain('class="lang-compact relative xl:hidden"');
    expect(LANGUAGE_SWITCHER).toContain("variant === 'bar'");
  });

  it('les puces FR·EN·AR en ligne (ancien rendu) restent réservées au bureau (`xl:flex`, W378) en variant "bar"', () => {
    expect(LANGUAGE_SWITCHER).toContain("variant === 'bar' ? 'hidden xl:flex' : 'flex'");
  });

  it('la cible tactile du menu compact respecte les 44px minimum (WCAG)', () => {
    const detailsBlock = LANGUAGE_SWITCHER.slice(
      LANGUAGE_SWITCHER.indexOf('class="lang-compact'),
      LANGUAGE_SWITCHER.indexOf('</details>'),
    );
    expect(detailsBlock).toContain('min-h-[44px] min-w-[44px]');
  });
});

describe('W378 (26/08) — en-tête desktop : plus jamais de retour à la ligne', () => {
  it('les libellés de nav (dont "À propos", le seul avec un espace) portent whitespace-nowrap', () => {
    expect(HEADER).toContain(
      "'group/link whitespace-nowrap text-sm font-medium text-lune-soft transition-colors hover:text-white link-underline'",
    );
    expect(HEADER).toContain(
      "'group/link whitespace-nowrap text-sm font-medium text-white link-underline-active'",
    );
  });

  it('le numéro de téléphone de la barre supérieure porte whitespace-nowrap', () => {
    expect(HEADER).toMatch(/class="link-underline hidden items-center gap-1\.5 whitespace-nowrap\b[^"]*md:flex"/);
  });

  it('la nav desktop + la barre CTA/langue basculent toutes au MÊME seuil `xl` (jamais lg)', () => {
    expect(HEADER).not.toMatch(/\blg:(flex|hidden|inline-block|block)\b/);
    expect(HEADER).toContain('gap-6 xl:flex');
    expect(HEADER).toContain('xl:hidden'); // hamburger + panneau mobile
    expect(HEADER).toContain('xl:inline-block'); // CTA laiton
  });

  it('le panneau mobile ouvert (variant="menu") garde ses puces langue à ≥44px — INCHANGÉ', () => {
    expect(LANGUAGE_SWITCHER).toContain("variant === 'menu'");
    expect(LANGUAGE_SWITCHER).toContain(
      "'inline-flex items-center justify-center min-h-[44px] min-w-[44px] px-2'",
    );
  });

  it('les puces langue "bar" (bureau, souris, ≥xl) passent à une taille compacte — plus 44px', () => {
    expect(LANGUAGE_SWITCHER).toContain(": 'inline-flex h-8 items-center justify-center px-1.5',");
  });
});

describe('WC1 — global.css : le glyphe WhatsApp (fill plein) échappe au mirroir RTL générique', () => {
  it('la règle de mirroir RTL des SVG exclut explicitement les glyphes fill="currentColor" (WhatsApp, téléphone)', () => {
    expect(GLOBAL_CSS).toContain(':not([fill="currentColor"])');
  });
});
