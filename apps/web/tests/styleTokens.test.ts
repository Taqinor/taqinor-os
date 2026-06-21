// W177 — Design token & utility guard.
// Asserts that the canonical CSS tokens and utilities defined in the design
// system (STYLE.md §7) are present in global.css — so an accidental deletion
// breaks CI immediately rather than silently degrading the site's visual system.
//
// Philosophy:
//   • We ONLY assert presence of tokens/utilities we defined. We do NOT scan
//     the whole repo for arbitrary values (that would be too brittle).
//   • The test is additive: add a new assertion when you add a new token.
//   • It never fails on existing arbitrary values in component files.

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const read = (rel: string) =>
  readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

const css = read('../src/styles/global.css');

describe('W177 — design tokens: color palette', () => {
  // Night canvas
  it('--color-nuit is defined', () => expect(css).toContain('--color-nuit:'));
  it('--color-nuit-800 is defined', () => expect(css).toContain('--color-nuit-800:'));
  it('--color-nuit-700 is defined', () => expect(css).toContain('--color-nuit-700:'));

  // Moon inks
  it('--color-lune is defined', () => expect(css).toContain('--color-lune:'));
  it('--color-lune-soft is defined', () => expect(css).toContain('--color-lune-soft:'));
  it('--color-lune-faint is defined', () => expect(css).toContain('--color-lune-faint:'));

  // Azur
  it('--color-azur-600 is defined', () => expect(css).toContain('--color-azur-600:'));
  it('--color-azur-700 is defined', () => expect(css).toContain('--color-azur-700:'));

  // Brass
  it('--color-brass-300 is defined', () => expect(css).toContain('--color-brass-300:'));
  it('--color-brass-400 is defined', () => expect(css).toContain('--color-brass-400:'));

  // White architectural
  it('--color-blanc is defined', () => expect(css).toContain('--color-blanc:'));
  it('--color-blanc-azur is defined', () => expect(css).toContain('--color-blanc-azur:'));
});

describe('W177 — design tokens: typography utilities', () => {
  it('.display utility is defined', () => expect(css).toContain('.display {'));
  it('.fig utility is defined', () => expect(css).toContain('.fig {'));
  it('.fig-xl utility is defined', () => expect(css).toContain('.fig-xl {'));
  it('.fig-lg utility is defined', () => expect(css).toContain('.fig-lg {'));
  it('.fig-md utility is defined', () => expect(css).toContain('.fig-md {'));
  it('.v2-body utility is defined', () => expect(css).toContain('.v2-body {'));
  it('.tech-label utility is defined', () => expect(css).toContain('.tech-label {'));
  it('.lum utility is defined', () => expect(css).toContain('.lum {'));
});

describe('W177 — design tokens: layout utilities', () => {
  it('.section utility is defined', () => expect(css).toContain('.section {'));
  it('.section-lg utility is defined', () => expect(css).toContain('.section-lg {'));
  it('.section-tight utility is defined', () => expect(css).toContain('.section-tight {'));
});

describe('W177 — design tokens: component utilities', () => {
  it('.cine-card utility is defined', () => expect(css).toContain('.cine-card {'));
  it('.btn-pill utility is defined', () => expect(css).toContain('.btn-pill {'));
  it('.hero-scrim utility is defined', () => expect(css).toContain('.hero-scrim {'));
  it('.eyebrow-light utility is defined', () => expect(css).toContain('.eyebrow-light {'));
  it('.glow utility is defined', () => expect(css).toContain('.glow {'));
  it('.shadow-premium utility is defined', () => expect(css).toContain('.shadow-premium {'));
  it('.rule-brass utility is defined', () => expect(css).toContain('.rule-brass {'));
  it('.cine-in utility is defined', () => expect(css).toContain('.cine-in {'));
});

describe('W177 — accessibility features', () => {
  it('scroll-padding-top is set on html (W202 sticky-header offset)', () =>
    expect(css).toContain('scroll-padding-top'));
  it('color-scheme: dark is set (W217)', () => expect(css).toContain('color-scheme: dark'));
  it('::selection rule is present (W217)', () => expect(css).toContain('::selection {'));
  it('focus-visible brass ring is present (W209)', () =>
    expect(css).toContain(':focus-visible'));
  it('prefers-contrast: more block is present (W221)', () =>
    expect(css).toContain('prefers-contrast: more'));
  it('forced-colors: active block is present (W221)', () =>
    expect(css).toContain('forced-colors: active'));
});

describe('W177 — dead code removed: .reveal/.emerge (W207)', () => {
  // These classes were confirmed unused across all .astro/.tsx/.ts/.js files.
  // They were removed as dead code; this test prevents accidental re-addition
  // of a dead .reveal rule (the active utility is .cine-in).
  it('.reveal class is not present (removed as dead code in W207)', () =>
    expect(css).not.toMatch(/^\s*\.reveal\s*\{/m));
  it('.emerge class is not present (removed as dead code in W207)', () =>
    expect(css).not.toMatch(/^\s*\.emerge\s*\{/m));
});
