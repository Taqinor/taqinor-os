// WC1 — verification pass (2026-07-05) locking in the 2026-07-04 mobile/RTL
// fixes that previously had no guard test: header overflow at 375px (top-bar
// CTA hidden below `lg`), the Arabic wordmark rendering "TAQINOR" and never
// "ROTAQIN" (dir="ltr" + unicode-bidi:isolate escape hatch), the WhatsApp SVG
// glyph excluded from the generic RTL chevron-mirror rule (a filled brand
// glyph must never be flipped like a directional chevron), and the compact
// globe language dropdown replacing three inline chips on mobile. Lecture
// SOURCE en texte, sans build (même convention que rtlToggleWJ17.test.ts /
// mobilePerfWJ18.test.ts) : ces fixes de mise en page ne sont pas facilement
// montables sous vitest — on verrouille donc les invariants de câblage.
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
  it('le CTA "cta.primary" de la barre supérieure est masqué sous `lg` (régime hamburger)', () => {
    const ctaBlock = HEADER.slice(HEADER.indexOf("href={L(QUOTE_JOURNEY_PATH)}"));
    expect(ctaBlock.slice(0, 400)).toMatch(/class="glow hidden\b[^"]*lg:inline-block/);
  });

  it('le téléphone de la barre supérieure reste masqué sous `md` (même discipline anti-débordement)', () => {
    expect(HEADER).toMatch(/class="link-underline hidden\b[^"]*md:flex/);
  });
});

describe('WC1 — LanguageSwitcher.astro : menu déroulant globe compact sur mobile', () => {
  it('un <details> compact (variant "bar") rend le menu globe sous `lg`, jamais de JS requis', () => {
    expect(LANGUAGE_SWITCHER).toContain('class="lang-compact relative lg:hidden"');
    expect(LANGUAGE_SWITCHER).toContain("variant === 'bar'");
  });

  it('les puces FR·EN·AR en ligne (ancien rendu) restent réservées au bureau (`lg:flex`) en variant "bar"', () => {
    expect(LANGUAGE_SWITCHER).toContain("variant === 'bar' ? 'hidden lg:flex' : 'flex'");
  });

  it('la cible tactile du menu compact respecte les 44px minimum (WCAG)', () => {
    const detailsBlock = LANGUAGE_SWITCHER.slice(
      LANGUAGE_SWITCHER.indexOf('class="lang-compact'),
      LANGUAGE_SWITCHER.indexOf('</details>'),
    );
    expect(detailsBlock).toContain('min-h-[44px] min-w-[44px]');
  });
});

describe('WC1 — global.css : le glyphe WhatsApp (fill plein) échappe au mirroir RTL générique', () => {
  it('la règle de mirroir RTL des SVG exclut explicitement les glyphes fill="currentColor" (WhatsApp, téléphone)', () => {
    expect(GLOBAL_CSS).toContain(':not([fill="currentColor"])');
  });
});
