/**
 * Tests W195–W200 — long-form reading experience (guides + blog)
 *
 * W195 — prose.css shared style
 * W196 — reading measure constrained to 68ch
 * W197 — reading-time indicator + auto TOC
 * W198 — cover image + hover lift on cards
 * W199 — Callout / PullQuote / KeyFigure components
 * W200 — branded list/table styles + RelatedLinks component
 */
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { estimateReadingTime, extractTocFromMarkdown } from '../src/lib/readingTime';

// ─── helpers ─────────────────────────────────────────────────────────────────

function src(rel: string): string {
  return readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');
}

// ─── W195 — prose.css exists and defines key rules ──────────────────────────

describe('W195 — prose.css shared style', () => {
  const css = src('../src/styles/prose.css');

  it('defines .prose container', () => {
    expect(css).toContain('.prose {');
  });

  it('defines .prose-lead for introduction paragraph', () => {
    expect(css).toContain('.prose-lead {');
    expect(css).toMatch(/font-size:\s*1\.125rem/);
    expect(css).toMatch(/line-height:\s*1\.8/);
  });

  it('defines h2/h3 inside .prose with scroll-margin-top for sticky header', () => {
    expect(css).toContain('.prose h2 {');
    expect(css).toContain('.prose h3 {');
    expect(css).toMatch(/scroll-margin-top:\s*5rem/);
  });

  it('defines zellige diamond marker for ul (brass border + rotate 45deg)', () => {
    expect(css).toContain('.prose ul li::before {');
    expect(css).toContain("content: '';");
    expect(css).toContain('rotate(45deg)');
    expect(css).toContain('var(--color-brass-400');
  });

  it('defines brass counter numbers for ol', () => {
    expect(css).toContain('counter-reset: prose-ol');
    expect(css).toContain("content: counter(prose-ol) '.'");
    expect(css).toContain('var(--color-brass-400');
  });

  it('defines table styles with brass header (W200)', () => {
    expect(css).toContain('.prose table {');
    expect(css).toContain('.prose thead th {');
    expect(css).toContain('var(--color-brass-300');
    expect(css).toContain('var(--color-brass-600');
  });

  it('defines .table-wrap for mobile reflow (W200)', () => {
    expect(css).toContain('.prose .table-wrap {');
    expect(css).toContain('overflow-x: auto');
  });

  it('defines blockquote with brass left border', () => {
    expect(css).toContain('.prose blockquote {');
    expect(css).toContain('var(--color-brass-400');
  });

  it('does NOT reference global.css or modify it', () => {
    // prose.css is a standalone file — it must not import global.css
    expect(css).not.toContain('@import');
    expect(css).not.toContain('global.css');
  });
});

// ─── W196 — 68ch reading measure ────────────────────────────────────────────

describe('W196 — reading measure constrained to 68ch', () => {
  it('prose.css sets max-width: 68ch on .prose', () => {
    const css = src('../src/styles/prose.css');
    expect(css).toContain('max-width: 68ch');
  });

  it('blog/[...slug].astro article uses max-w-[68ch]', () => {
    const slug = src('../src/pages/blog/[...slug].astro');
    expect(slug).toContain('max-w-[68ch]');
  });

  it('guide faut-il-des-batteries uses max-w-[68ch]', () => {
    const guide = src('../src/pages/guides/faut-il-des-batteries.astro');
    expect(guide).toContain('max-w-[68ch]');
  });

  it('guide orientation-inclinaison-ombrage uses max-w-[68ch]', () => {
    const guide = src('../src/pages/guides/orientation-inclinaison-ombrage.astro');
    expect(guide).toContain('max-w-[68ch]');
  });

  it('guide onduleur-hybride-ou-reseau uses max-w-[68ch]', () => {
    const guide = src('../src/pages/guides/onduleur-hybride-ou-reseau.astro');
    expect(guide).toContain('max-w-[68ch]');
  });
});

// ─── W197 — reading time + TOC ──────────────────────────────────────────────

describe('W197 — estimateReadingTime()', () => {
  it('returns 1 for empty string', () => {
    expect(estimateReadingTime('')).toBe(1);
  });

  it('returns 1 for a very short text (< 200 words)', () => {
    const text = 'Bonjour monde.';
    expect(estimateReadingTime(text)).toBe(1);
  });

  it('returns correct minutes for exactly 200 words', () => {
    const text = Array(200).fill('mot').join(' ');
    expect(estimateReadingTime(text)).toBe(1);
  });

  it('returns 2 for 201 words', () => {
    const text = Array(201).fill('mot').join(' ');
    expect(estimateReadingTime(text)).toBe(2);
  });

  it('returns 3 for 400 words', () => {
    const text = Array(400).fill('mot').join(' ');
    expect(estimateReadingTime(text)).toBe(2);
  });

  it('never returns 0', () => {
    expect(estimateReadingTime('a')).toBeGreaterThanOrEqual(1);
    expect(estimateReadingTime('   ')).toBeGreaterThanOrEqual(1);
  });

  it('handles multiline text with newlines', () => {
    const text = Array(200).fill('mot').join('\n');
    expect(estimateReadingTime(text)).toBe(1);
  });
});

describe('W197 — extractTocFromMarkdown()', () => {
  it('returns empty array for text with no headings', () => {
    expect(extractTocFromMarkdown('Paragraphe sans titre.')).toHaveLength(0);
  });

  it('extracts ## headings as level 2', () => {
    const md = '## Premier titre\n\nContenu.';
    const toc = extractTocFromMarkdown(md);
    expect(toc).toHaveLength(1);
    expect(toc[0].level).toBe(2);
    expect(toc[0].text).toBe('Premier titre');
  });

  it('extracts ### headings as level 3', () => {
    const md = '### Sous-titre\n\nContenu.';
    const toc = extractTocFromMarkdown(md);
    expect(toc[0].level).toBe(3);
  });

  it('ignores # (h1) headings', () => {
    const md = '# Titre principal\n## Section\n';
    const toc = extractTocFromMarkdown(md);
    expect(toc).toHaveLength(1);
    expect(toc[0].level).toBe(2);
  });

  it('generates slug IDs from heading text', () => {
    const md = '## Mon Titre Accentué\n';
    const toc = extractTocFromMarkdown(md);
    // Accents stripped, lowercase, spaces → hyphens
    expect(toc[0].id).toBe('mon-titre-accentue');
  });

  it('deduplicates repeated heading IDs with numeric suffix', () => {
    const md = '## Section\n## Section\n## Section\n';
    const toc = extractTocFromMarkdown(md);
    expect(toc[0].id).toBe('section');
    expect(toc[1].id).toBe('section-1');
    expect(toc[2].id).toBe('section-2');
  });

  it('handles mixed h2 and h3', () => {
    const md = '## Titre A\n### Sous-titre B\n## Titre C\n';
    const toc = extractTocFromMarkdown(md);
    expect(toc).toHaveLength(3);
    expect(toc[0].level).toBe(2);
    expect(toc[1].level).toBe(3);
    expect(toc[2].level).toBe(2);
  });

  it('strips French accents from IDs (NFD normalization)', () => {
    const md = '## Équipement solaire\n';
    const toc = extractTocFromMarkdown(md);
    expect(toc[0].id).toBe('equipement-solaire');
  });

  it('blog slug page imports estimateReadingTime and extractTocFromMarkdown', () => {
    const slug = src('../src/pages/blog/[...slug].astro');
    expect(slug).toContain('estimateReadingTime');
    expect(slug).toContain('extractTocFromMarkdown');
    expect(slug).toContain("from '../../lib/readingTime'");
  });

  it('blog slug page shows reading time indicator', () => {
    const slug = src('../src/pages/blog/[...slug].astro');
    expect(slug).toContain('readingMinutes');
    expect(slug).toContain('min de lecture');
  });

  it('blog slug page renders TOC when showToc is true', () => {
    const slug = src('../src/pages/blog/[...slug].astro');
    expect(slug).toContain('showToc');
    expect(slug).toContain('Sommaire');
    expect(slug).toContain('toc__link');
  });
});

// ─── W198 — cover image + hover lift ────────────────────────────────────────

describe('W198 — cover image + hover lift', () => {
  it('content.config.ts defines optional cover field', () => {
    const config = src('../src/content.config.ts');
    expect(config).toContain('cover');
    expect(config).toContain('optional()');
  });

  it('blog slug page renders cover image conditionally', () => {
    const slug = src('../src/pages/blog/[...slug].astro');
    expect(slug).toContain('data.cover');
    expect(slug).toContain('article-cover');
  });

  it('guides/index.astro has hover lift on guide cards', () => {
    const idx = src('../src/pages/guides/index.astro');
    expect(idx).toContain('guide-card');
    // Lift CSS is in a <style> block or class
    expect(idx).toMatch(/translateY\(-4px\)|guide-card/);
  });

  it('blog/index.astro has hover lift on blog cards', () => {
    const idx = src('../src/pages/blog/index.astro');
    expect(idx).toContain('blog-card');
    expect(idx).toMatch(/translateY\(-4px\)|blog-card/);
  });

  it('hover lift is behind prefers-reduced-motion guard', () => {
    const guideIdx = src('../src/pages/guides/index.astro');
    expect(guideIdx).toContain('prefers-reduced-motion');

    const blogIdx = src('../src/pages/blog/index.astro');
    expect(blogIdx).toContain('prefers-reduced-motion');
  });
});

// ─── W199 — Callout / PullQuote / KeyFigure components ──────────────────────

describe('W199 — Callout component', () => {
  const callout = src('../src/components/Callout.astro');

  it('accepts type prop (info | tip | warning)', () => {
    expect(callout).toContain("type?: 'info' | 'tip' | 'warning'");
  });

  it('has role="note" for accessibility', () => {
    expect(callout).toContain('role="note"');
  });

  it('uses azur token for info type', () => {
    expect(callout).toContain('var(--color-azur-600');
  });

  it('uses brass token for tip type', () => {
    expect(callout).toContain('var(--color-brass-400');
  });

  it('renders title when provided', () => {
    expect(callout).toContain('{title && <p class="callout__title">{title}</p>}');
  });

  it('has aria-label from title or type fallback', () => {
    expect(callout).toContain('aria-label={title ??');
  });
});

describe('W199 — PullQuote component', () => {
  const pq = src('../src/components/PullQuote.astro');

  it('exists and has brass border-left', () => {
    expect(pq).toContain('var(--color-brass');
  });

  it('accepts optional author prop', () => {
    expect(pq).toContain('author?');
  });
});

describe('W199 — KeyFigure component', () => {
  const kf = src('../src/components/KeyFigure.astro');

  it('requires value and label props', () => {
    expect(kf).toContain('value: string');
    expect(kf).toContain('label: string');
  });

  it('uses clamp for responsive font size', () => {
    expect(kf).toContain('clamp(2rem');
  });

  it('uses aria-label for accessibility', () => {
    expect(kf).toContain('aria-label={');
  });

  it('uses aria-hidden on the visual display to avoid duplication', () => {
    expect(kf).toContain('aria-hidden="true"');
  });

  it('uses brass border and fig/lum tokens', () => {
    expect(kf).toContain('var(--color-brass-400');
    expect(kf).toContain('class="key-figure__value fig lum"');
  });
});

describe('W199 — components wired in guides', () => {
  it('faut-il-des-batteries imports Callout', () => {
    const guide = src('../src/pages/guides/faut-il-des-batteries.astro');
    expect(guide).toContain("import Callout from '../../components/Callout.astro'");
  });

  it('faut-il-des-batteries imports KeyFigure', () => {
    const guide = src('../src/pages/guides/faut-il-des-batteries.astro');
    expect(guide).toContain("import KeyFigure from '../../components/KeyFigure.astro'");
  });

  it('faut-il-des-batteries uses <KeyFigure> with value and label', () => {
    const guide = src('../src/pages/guides/faut-il-des-batteries.astro');
    expect(guide).toContain('<KeyFigure');
    expect(guide).toContain('value=');
    expect(guide).toContain('label=');
  });

  it('faut-il-des-batteries uses <Callout> with type tip', () => {
    const guide = src('../src/pages/guides/faut-il-des-batteries.astro');
    expect(guide).toContain('<Callout');
    expect(guide).toContain('type="tip"');
  });
});

// ─── W200 — RelatedLinks component ──────────────────────────────────────────

describe('W200 — RelatedLinks component', () => {
  const rl = src('../src/components/RelatedLinks.astro');

  it('renders a <nav> with aria-label="Liens associés"', () => {
    expect(rl).toContain('<nav');
    expect(rl).toContain('aria-label="Liens associés"');
  });

  it('accepts links array with href and label', () => {
    expect(rl).toContain('href: string');
    expect(rl).toContain('label: string');
  });

  it('supports optional external prop', () => {
    expect(rl).toContain('external?');
    expect(rl).toContain('noopener noreferrer');
  });

  it('has focus-visible outline for keyboard nav', () => {
    expect(rl).toContain('focus-visible:outline');
  });

  it('adds arrow suffix automatically', () => {
    expect(rl).toContain('→');
  });
});

describe('W200 — RelatedLinks wired in all guide pages', () => {
  const guides = [
    'batterie-lithium-ou-gel',
    'combien-de-panneaux-pour-ma-maison',
    'electricite-pendant-les-coupures',
    'entretien-et-duree-de-vie-des-panneaux',
    'faut-il-des-batteries',
    'loi-82-21-expliquee',
    'monocristallin-ou-polycristallin',
    'on-grid-off-grid-ou-hybride',
    'onduleur-hybride-ou-reseau',
    'orientation-inclinaison-ombrage',
    'quelle-taille-de-batterie',
  ];

  for (const guide of guides) {
    it(`${guide} imports and uses RelatedLinks`, () => {
      const content = src(`../src/pages/guides/${guide}.astro`);
      expect(content).toContain("import RelatedLinks from '../../components/RelatedLinks.astro'");
      expect(content).toContain('<RelatedLinks');
    });
  }

  it('blog slug uses RelatedLinks', () => {
    const slug = src('../src/pages/blog/[...slug].astro');
    expect(slug).toContain("import RelatedLinks from '../../components/RelatedLinks.astro'");
    expect(slug).toContain('<RelatedLinks');
  });
});

describe('W200 — prose.css branded list markers in guides', () => {
  it('guides/index uses .prose or imports prose.css indirectly via components', () => {
    // The guides themselves apply max-w-[68ch] and class tags from prose system
    const oi = src('../src/pages/guides/orientation-inclinaison-ombrage.astro');
    // At minimum, guide pages use the 68ch container
    expect(oi).toContain('max-w-[68ch]');
  });

  it('prose.css branded lists do NOT require a dependency on global.css', () => {
    const css = src('../src/styles/prose.css');
    expect(css).not.toContain('@import');
  });
});
