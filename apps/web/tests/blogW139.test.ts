// W139 — Garde-fous du blog (W132–W138). Tests SOURCE + frontmatter (pas de build
// requis). Assertions :
//  1. la collection `blog` est définie (loader glob + schéma Zod) ;
//  2. chaque article publié a un frontmatter valide (title/description/pubDate) ;
//  3. /rss.xml émet un RSS 2.0 et n'inclut QUE les articles non-draft ;
//  4. l'index, la route [slug] et le RSS excluent tous les `draft:true` ;
//  5. la route [slug] porte BlogPosting + BreadcrumbList et un seul canonical
//     (via le Layout) ; aucune page blog n'émet de FAQPage ;
//  6. /blog n'est pas exclu du sitemap, /preview/ l'est ;
//  7. un fixture `draft:true` existe pour matérialiser l'exclusion.
import { describe, expect, it } from 'vitest';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const read = (rel: string) => readFileSync(resolve(here, rel), 'utf-8');
const BLOG_DIR = resolve(here, '../src/content/blog');

const DRAFT_FIXTURE = 'exemple-article-en-brouillon.md';

/** Parse minimal du frontmatter YAML (1 niveau) entre les deux `---`. */
function frontmatter(md: string): Record<string, string> {
  const m = md.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  const out: Record<string, string> = {};
  if (!m) return out;
  for (const line of m[1].split(/\r?\n/)) {
    const kv = line.match(/^([a-zA-Z]+):\s*(.*)$/);
    if (kv) out[kv[1]] = kv[2].trim();
  }
  return out;
}

const mdFiles = readdirSync(BLOG_DIR).filter((f) => f.endsWith('.md'));
const publishedFiles = mdFiles.filter((f) => f !== DRAFT_FIXTURE);

const sitemapExcluded = (page: string) =>
  /type-test|media-test|variants-test|craft-|\/preview\//.test(page);

describe('W139 — collection blog', () => {
  it('content.config.ts définit la collection blog (loader glob + schéma Zod)', () => {
    const cfg = read('../src/content.config.ts');
    expect(cfg).toContain('defineCollection');
    expect(cfg).toContain('glob(');
    expect(cfg).toMatch(/title:\s*z\.string\(\)/);
    expect(cfg).toMatch(/pubDate:\s*z\.coerce\.date\(\)/);
    expect(cfg).toMatch(/draft:\s*z\.boolean\(\)\.default\(false\)/);
  });

  it('au moins 6 articles publiés existent', () => {
    expect(publishedFiles.length).toBeGreaterThanOrEqual(6);
  });

  it('chaque article publié a un frontmatter valide et n’est pas un brouillon', () => {
    for (const f of publishedFiles) {
      const fm = frontmatter(read(`../src/content/blog/${f}`));
      expect(fm.title, f).toBeTruthy();
      expect(fm.description, f).toBeTruthy();
      expect(fm.pubDate, f).toMatch(/^\d{4}-\d{2}-\d{2}/);
      expect(fm.draft ?? 'false', f).not.toBe('true');
    }
  });
});

describe('W139 — exclusion des brouillons', () => {
  it('le fixture brouillon existe et porte draft: true', () => {
    expect(mdFiles).toContain(DRAFT_FIXTURE);
    const fm = frontmatter(read(`../src/content/blog/${DRAFT_FIXTURE}`));
    expect(fm.draft).toBe('true');
  });

  it('l’index /blog exclut les brouillons en prod', () => {
    const idx = read('../src/pages/blog/index.astro');
    expect(idx).toContain("getCollection('blog'");
    expect(idx).toMatch(/PROD\s*\?\s*!data\.draft\s*&&\s*data\.pubDate\.getTime\(\)\s*<=\s*Date\.now\(\)\s*:\s*true/);
  });

  it('la route [slug] exclut les brouillons (getStaticPaths)', () => {
    const slug = read('../src/pages/blog/[...slug].astro');
    expect(slug).toContain('getStaticPaths');
    expect(slug).toMatch(/PROD\s*\?\s*!data\.draft\s*&&\s*data\.pubDate\.getTime\(\)\s*<=\s*Date\.now\(\)\s*:\s*true/);
  });

  it('le RSS n’inclut QUE les articles non-draft', () => {
    const rss = read('../src/pages/rss.xml.ts');
    expect(rss).toMatch(/getCollection\('blog',\s*\(\{\s*data\s*\}\)\s*=>\s*!data\.draft\s*&&\s*data\.pubDate\.getTime\(\)\s*<=\s*Date\.now\(\)\)/);
  });
});

describe('W139 — /rss.xml valide', () => {
  const rss = read('../src/pages/rss.xml.ts');
  it('émet un RSS 2.0 avec channel + items et le bon Content-Type', () => {
    expect(rss).toContain('<rss version="2.0"');
    expect(rss).toContain('<channel>');
    expect(rss).toContain('<item>');
    expect(rss).toContain('application/rss+xml');
  });
  it('échappe les caractères réservés XML', () => {
    expect(rss).toContain('escapeXml');
    expect(rss).toContain('&amp;');
  });
});

describe('W139 — données structurées & canonical de la route [slug]', () => {
  const slug = read('../src/pages/blog/[...slug].astro');
  it('porte BlogPosting + BreadcrumbList', () => {
    expect(slug).toMatch(/['"]@type['"]:\s*['"]BlogPosting['"]/);
    expect(slug).toMatch(/['"]@type['"]:\s*['"]BreadcrumbList['"]/);
  });
  it('passe par le Layout (un seul canonical) et n’émet pas de canonical inline', () => {
    expect(slug).toContain('import Layout from');
    expect(slug).toContain('<Layout');
    expect(slug.match(/<link\s+rel="canonical"/g) ?? []).toHaveLength(0);
  });
  it('aucune page blog n’émet de FAQPage', () => {
    for (const f of ['../src/pages/blog/index.astro', '../src/pages/blog/[...slug].astro']) {
      expect(read(f), f).not.toMatch(/['"]@type['"]:\s*['"]FAQPage['"]/);
    }
  });
});

describe('W139 — sitemap', () => {
  it('/blog et les articles ne sont pas exclus, /preview/ l’est', () => {
    expect(sitemapExcluded('/blog')).toBe(false);
    expect(sitemapExcluded('/blog/prix-installation-solaire-maroc-2026')).toBe(false);
    expect(sitemapExcluded('/preview/toiture-3d-pro-11')).toBe(true);
  });
});
