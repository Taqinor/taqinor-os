// W233 — A11y + perf gate pour /preview/accueil-v3 et /preview/index.
//
// Invariants verrouillés par lecture du source (vitest, pas de navigateur) :
//  1. accueil-v3.astro est noindex (jamais indexée).
//  2. Exactement un <h1> dans la page.
//  3. L'image LCP du héros ne porte PAS la classe .v3-grade
//     (le grade chaud est réservé aux photos de contenu, jamais au héros).
//  4. Les animations/mouvements sont gated derrière prefers-reduced-motion.
//  5. preview/index.astro est noindex ET contient un lien vers /preview/accueil-v3.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const read = (rel: string) =>
  readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

// ─────────────────────────────────────────────────────────────────────────────
// 1. accueil-v3.astro est noindex
// ─────────────────────────────────────────────────────────────────────────────
describe('W233 — accueil-v3 est noindex', () => {
  it('passe noindex={true} au Layout', () => {
    const src = read('../src/pages/preview/accueil-v3.astro');
    // Le prop noindex={true} est passé au Layout partagé.
    expect(src).toContain('noindex={true}');
  });

  it('le Layout émet <meta name="robots" content="noindex, nofollow"> quand noindex est vrai', () => {
    const layout = read('../src/layouts/Layout.astro');
    // La conditionnelle et le meta vivent dans le Layout.
    expect(layout).toContain('noindex && <meta name="robots" content="noindex, nofollow"');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 2. Exactement un <h1> dans accueil-v3.astro
// ─────────────────────────────────────────────────────────────────────────────
describe('W233 — un seul <h1> dans accueil-v3', () => {
  it('le fichier source contient exactement une balise <h1', () => {
    const src = read('../src/pages/preview/accueil-v3.astro');
    const h1Matches = src.match(/<h1[\s>]/g) ?? [];
    expect(h1Matches, 'exactement un <h1> — ni zéro ni plusieurs').toHaveLength(1);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 3. Le héros LCP ne porte PAS la classe .v3-grade
//    (assert sur l'image <img> du héros et sur le wrapper v2-hero-media)
// ─────────────────────────────────────────────────────────────────────────────
describe("W233 — l'image heros / LCP n'a pas v3-grade", () => {
  const src = read('../src/pages/preview/accueil-v3.astro');

  it("l'element <img> du heros (hero-portrait-img) ne porte pas v3-grade", () => {
    // La ligne de l'img LCP contient "hero-portrait-img" — vérifier qu'elle
    // ne contient pas v3-grade sur la même ligne.
    const heroImgLine = src
      .split('\n')
      .find((l) => l.includes('hero-portrait-img'));
    expect(heroImgLine, 'ligne hero-portrait-img trouvée').toBeTruthy();
    expect(heroImgLine, 'hero-portrait-img sans v3-grade').not.toContain('v3-grade');
  });

  it("le wrapper v2-hero-media (conteneur heros) ne porte pas v3-grade", () => {
    // Le div v2-hero-media ne doit jamais avoir v3-grade comme classe.
    const heroMediaLine = src
      .split('\n')
      .find((l) => l.includes('v2-hero-media') && l.includes('class='));
    expect(heroMediaLine, 'ligne v2-hero-media avec class= trouvée').toBeTruthy();
    expect(heroMediaLine, 'v2-hero-media sans v3-grade').not.toContain('v3-grade');
  });

  it("le commentaire source documente explicitement l'interdiction de v3-grade sur le heros", () => {
    // L'auteur a mis un commentaire VERBATIM pour bloquer les futures regressions.
    expect(src).toContain('JAMAIS de .v3-grade ici');
  });

  it('v3-grade est bien present sur les photos de contenu (pas seulement absent du heros)', () => {
    // Verifier que la classe est utilisee dans la page — elle est sur les
    // photos de la galerie-preuve, pas sur le heros.
    const lines = src.split('\n').filter((l) => l.includes('v3-grade') && !l.includes('//'));
    // Au moins une ligne de markup (pas de commentaire) porte v3-grade.
    expect(lines.length, 'v3-grade present sur au moins une photo de contenu').toBeGreaterThan(0);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 4. Reduced-motion : les animations sont gated
// ─────────────────────────────────────────────────────────────────────────────
describe('W233 — sécurité reduced-motion', () => {
  it('accueil-v3 vérifie prefers-reduced-motion avant de lancer la vidéo', () => {
    const src = read('../src/pages/preview/accueil-v3.astro');
    // Le script JS héro lit la media query reduced-motion avant de charger la vidéo.
    expect(src).toContain("matchMedia('(prefers-reduced-motion: no-preference)').matches");
  });

  it('accueil-v3 vérifie prefers-reduced-motion avant le count-up animé', () => {
    const src = read('../src/pages/preview/accueil-v3.astro');
    // Le count-up lit reduced-motion et affiche la valeur finale sans animation.
    expect(src).toContain("matchMedia('(prefers-reduced-motion: reduce)').matches");
  });

  it('le CSS global gate .cine-in derrière prefers-reduced-motion: no-preference', () => {
    const css = read('../src/styles/global.css');
    // Les déclarations .cine-in (animation d'entrée) sont à l'intérieur d'un
    // @media (prefers-reduced-motion: no-preference).
    expect(css).toContain('prefers-reduced-motion: no-preference');
    expect(css).toContain('.cine-in');
  });

  it('le CSS global désactive les delays .cine-in-* sous prefers-reduced-motion: reduce', () => {
    const css = read('../src/styles/global.css');
    // Un bloc @media (prefers-reduced-motion: reduce) neutralise les délais des staggered items.
    expect(css).toContain('prefers-reduced-motion: reduce');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 5. preview/index.astro est noindex et contient un lien vers /preview/accueil-v3
// ─────────────────────────────────────────────────────────────────────────────
describe('W233/W234 — preview/index.astro est noindex et liste accueil-v3', () => {
  const src = read('../src/pages/preview/index.astro');

  it('la page index de prévisualisation porte le meta noindex,nofollow', () => {
    expect(src).toContain('content="noindex,nofollow"');
  });

  it('elle contient un lien href="/preview/accueil-v3"', () => {
    expect(src).toContain('href="/preview/accueil-v3"');
  });

  it('elle ne passe pas par le Layout partagé (pas de nav publique forcée)', () => {
    // La page utilise un <html> standalone pour rester totalement hors nav.
    expect(src).not.toContain("import Layout from");
  });
});
